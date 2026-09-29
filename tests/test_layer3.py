"""Unit and integration tests. No network access and no real LLM: the CKAN
resource is a synthetic zip and Ollama is replaced by a fake client."""

import copy
import json
import zipfile

import numpy as np
import pandas as pd
import pytest

from src import aggregate, config, detectors, judge, report, review
from src import profile as profiles
from src.profile import Paths, Profile

BASE_PROFILE = {
    "id": "test-profile",
    "title": "Synthetic notices",
    "source": {"portal_url": "https://example.org", "dataset_id": "d", "resource_name": "r"},
    "file": {"compression": "zip", "member_pattern": "*.csv", "sep": ";", "encoding": "utf-8"},
    "columns": {"date": "DATA", "key": "ID"},
    "exclude": {"column": "CANCELADO", "equals": "S", "label": "cancelled", "description": "cancelled notices"},
    "filters": [],
    "sparse_min_records": 3,
    "series": [
        {"name": "notices", "kind": "count", "description": "Notices per month"},
        {"name": "fines", "kind": "sum", "column": "VALOR", "number_format": "br", "description": "Fines"},
    ],
    "domain": "Synthetic domain.",
    "record_label": "notices",
    "categories": {"PDC": "Policy", "SP": "Seasonal", "DQE": "Data quality", "GES": "Genuine shift"},
}


def make_profile(tmp_path, **overrides) -> Profile:
    raw = copy.deepcopy(BASE_PROFILE)
    raw.update(overrides)
    p = Profile(raw)
    p.paths = Paths.for_profile(p.id, tmp_path)
    return p


def write_zip(path, rows_by_file: dict[str, list[str]]):
    header = "ID;DATA;VALOR;CANCELADO;UF;NOME_INFRATOR;CPF_CNPJ_INFRATOR"
    with zipfile.ZipFile(path, "w") as zf:
        for name, rows in rows_by_file.items():
            zf.writestr(name, "\n".join([header, *rows]) + "\n")
    return path


def synthetic_rows(months: int = 60, per_month: int = 10, start: str = "2020-01") -> list[str]:
    rows, seq = [], 0
    for i, month in enumerate(pd.period_range(start, periods=months, freq="M")):
        for d in range(per_month):
            seq += 1
            rows.append(f"{seq};{month.start_time.date()} 10:00:00;1.000,50;N;PA;Fulano {seq};000.000.000-{seq % 100:02d}")
    return rows


# --- profiles ----------------------------------------------------------------

def test_shipped_profiles_are_valid():
    ps = profiles.available()
    assert {"ibama-autos-infracao", "ibama-autos-infracao-amazonia-legal"} <= {p.id for p in ps}
    for p in ps:
        assert p.events(), p.id
        for ev in p.events():
            pd.Period(ev["month"], freq="M")
            assert ev["source"]


@pytest.mark.parametrize("breakage", [
    {"series": [{"name": "x", "kind": "median", "description": ""}]},
    {"series": [{"name": "x", "kind": "sum", "description": ""}]},
    {"columns": {"key": "ID"}},
    {"filters": [{"column": "UF"}]},
    {"categories": {"INVALID": "reserved"}},
])
def test_invalid_profiles_are_rejected(breakage):
    raw = copy.deepcopy(BASE_PROFILE)
    raw.update(breakage)
    with pytest.raises(ValueError):
        Profile(raw)


# --- aggregation -------------------------------------------------------------

def test_parse_number_br_and_plain():
    s = pd.Series(["1.234,56", "1500,00", "", None, "abc", "12.5"])
    br = aggregate.parse_number(s, "br")
    assert br.iloc[0] == pytest.approx(1234.56)
    assert br.iloc[1] == 1500.0
    assert br.iloc[2:5].isna().all()
    assert aggregate.parse_number(pd.Series(["12.5"]), "plain").iloc[0] == 12.5


def test_monthly_series_counts_excludes_and_drops_current_month(tmp_path):
    p = make_profile(tmp_path)
    rows = [
        "1;2024-01-05;100,00;N;PA;A;1",
        "2;2024-01-20;50,50;S;PA;B;2",       # cancelled: excluded
        ";2024-01-21;10,00;N;PA;C;3",         # no key: counted, flagged
        "3;2024-03-02;1.000,00;N;SP;D;4",
        "3;2024-03-02;1.000,00;N;SP;D;4",     # duplicate key: dropped
        "4;2024-04-10;5,00;N;SP;E;5",         # current month: dropped
    ]
    zp = write_zip(tmp_path / "r.zip", {"a_2024.csv": rows})
    monthly, stats = aggregate.monthly_series(aggregate.load_records(zp, p), p, pd.Timestamp("2024-04-15"))
    assert list(monthly.index.astype(str)) == ["2024-01", "2024-02", "2024-03"]
    assert monthly.loc["2024-01", "notices"] == 2
    assert monthly.loc["2024-01", "fines"] == pytest.approx(110.0)
    assert monthly.loc["2024-01", "excluded"] == 1
    assert monthly.loc["2024-01", "missing_key"] == 1
    assert monthly.loc["2024-02", "notices"] == 0
    assert monthly.loc["2024-03", "fines"] == 1000.0
    assert stats["rows_duplicate_key_dropped"] == 1
    assert stats["rows_missing_key"] == 1


def test_personal_data_never_read_nor_saved(tmp_path):
    p = make_profile(tmp_path)
    zp = write_zip(tmp_path / "r.zip", {"a.csv": synthetic_rows(40)})
    records = aggregate.load_records(zp, p)
    assert "NOME_INFRATOR" not in records.columns and "CPF_CNPJ_INFRATOR" not in records.columns
    monthly, _ = aggregate.monthly_series(records, p, pd.Timestamp("2030-01-01"))
    aggregate.save_series(monthly, p.paths.series)
    text = p.paths.series.read_text()
    assert "Fulano" not in text and "000.000.000" not in text


def test_filters_define_a_data_cut(tmp_path):
    p = make_profile(tmp_path, filters=[{"column": "UF", "in": ["SP"]}])
    rows = ["1;2024-01-05;1,00;N;PA;A;1", "2;2024-01-06;1,00;N;SP;B;2", "3;2024-02-06;1,00;N;SP;C;3"]
    zp = write_zip(tmp_path / "r.zip", {"a.csv": rows})
    monthly, stats = aggregate.monthly_series(aggregate.load_records(zp, p), p, pd.Timestamp("2024-03-15"))
    assert stats["rows_after_filters"] == 2
    assert monthly["notices"].tolist() == [1, 1]


def test_analysis_window_drops_sparse_start_and_applies_period(tmp_path):
    p = make_profile(tmp_path)
    idx = pd.period_range("2000-01", periods=60, freq="M")
    monthly = pd.DataFrame({"notices": [1, 2] + [10] * 58, "fines": 1.0, "excluded": 0, "missing_key": 0}, index=idx)
    assert aggregate.analysis_window(monthly, p).index.min() == pd.Period("2000-03", freq="M")
    p2 = make_profile(tmp_path, period={"start": "2001-01", "end": None})
    assert aggregate.analysis_window(monthly, p2).index.min() == pd.Period("2001-01", freq="M")
    with pytest.raises(ValueError):
        aggregate.analysis_window(monthly.iloc[:30], p)


def test_plain_csv_resource(tmp_path):
    p = make_profile(tmp_path, file={"compression": "none", "sep": ";", "encoding": "utf-8"})
    csv = tmp_path / "r.csv"
    csv.write_text("ID;DATA;VALOR;CANCELADO;UF\n1;2024-01-05;2,00;N;PA\n", encoding="utf-8")
    assert len(aggregate.load_records(csv, p)) == 1


# --- detectors ---------------------------------------------------------------

def seasonal_series(n=180, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(n)
    values = 1000 * (1 + 0.1 * np.sin(2 * np.pi * t / 12)) * rng.lognormal(0, 0.03, n)
    return pd.Series(values, index=pd.period_range("2005-01", periods=n, freq="M"))


def test_point_spike_is_flagged_by_ensemble():
    s = seasonal_series()
    s.iloc[120] *= 6
    det, _ = detectors.run_detectors(s)
    assert det["anomaly"].iloc[120]
    assert det["votes"].iloc[120] >= 3
    assert det["anomaly"].sum() <= 0.1 * len(s)


def test_detectors_are_deterministic():
    s = seasonal_series()
    s.iloc[100] *= 0.2
    a, _ = detectors.run_detectors(s)
    b, _ = detectors.run_detectors(s)
    pd.testing.assert_frame_equal(a, b)


def test_page_hinkley_finds_level_shift_but_not_noise():
    s = seasonal_series(seed=3)
    x = np.log1p(s.to_numpy())
    assert detectors.page_hinkley(x, config.PH_DELTA, config.PH_LAMBDA) == []
    x_shift = x.copy()
    x_shift[90:] += np.log(5)
    points = detectors.page_hinkley(x_shift, config.PH_DELTA, config.PH_LAMBDA)
    assert any(90 <= p["alarm_index"] <= 92 and p["index"] <= 90 and p["direction"] == "up" for p in points)


def test_lstm_scores_spike_highest():
    pytest.importorskip("torch")
    s = seasonal_series()
    s.iloc[130] *= 8
    err, thr = detectors.lstm_autoencoder(np.log1p(s.to_numpy()), 12, 16, 0.2, 30, 99.0, 42)
    assert int(np.argmax(err)) in range(128, 133)
    assert err[130] > thr


# --- LLM-as-a-Judge ----------------------------------------------------------

class FakeClient:
    model = config.LLM_MODEL

    def __init__(self, answers):
        self.answers = list(answers)
        self.prompts = []

    def info(self):
        return {"model": self.model, "model_digest": "sha256:fake", "ollama_version": "0.0-test"}

    def generate(self, system, prompt, seed, schema):
        self.prompts.append((system, prompt, seed, schema))
        return self.answers.pop(0), 0.1


def answer(cat, conf=0.8):
    return json.dumps({"reasoning": f"because {cat}", "category": cat, "confidence": conf})


def test_parse_response_rejects_unknown_labels():
    cats = BASE_PROFILE["categories"]
    assert judge.parse_response(answer("SP"), cats)["category"] == "SP"
    assert judge.parse_response(answer("XYZ"), cats)["category"] == "INVALID"
    assert judge.parse_response("not json", cats)["category"] == "INVALID"


def test_majority_consistency_and_review_levels():
    runs = [{"category": c, "confidence": 0.5} for c in ("GES", "GES", "SP")]
    assert judge.aggregate_runs(runs) == {"category": "GES", "consistency": 0.667}
    split = [{"category": "PDC", "confidence": 0.9}, {"category": "SP", "confidence": 0.4},
             {"category": "GES", "confidence": 0.5}]
    assert judge.aggregate_runs(split) == {"category": "PDC", "consistency": 0.333}
    assert judge.review_level("DQE", 1.0) == "mandatory"
    assert judge.review_level("PDC", 0.333) == "advisory"
    assert judge.review_level("GES", 0.667) == "none"


def pipeline_inputs(tmp_path):
    p = make_profile(tmp_path)
    s = seasonal_series()
    s.iloc[-3] *= 6
    monthly = pd.DataFrame({"notices": s.round(), "fines": s * 100, "excluded": 1, "missing_key": 0})
    det, drift = detectors.detect_all(monthly, list(p.series))
    return p, monthly, det, drift


def test_judge_caches_and_respects_budget(tmp_path):
    p, monthly, det, _ = pipeline_inputs(tmp_path)
    n_flagged = int(det["anomaly"].sum())
    assert n_flagged >= 2
    client = FakeClient([answer("DQE")] * 3 + [answer("SP"), answer("SP"), answer("GES")] * 50)
    res = judge.judge_pending(p, monthly, det, client, max_judgments=1)
    assert res["judged_now"] == 1
    saved = judge.load_judgments(p.paths.judgments)
    (entry,) = saved.values()
    assert entry["category"] == "DQE" and entry["review_level"] == "mandatory"
    assert entry["month"] == str(det[det["anomaly"]].index.max())  # most recent first
    assert entry["model_digest"] == "sha256:fake"
    system, prompt, seed, schema = client.prompts[0]
    assert "Synthetic domain." in system and "<== anomaly" in prompt
    assert schema["properties"]["category"]["enum"] == list(BASE_PROFILE["categories"])
    assert [x[2] for x in client.prompts] == config.LLM_SEEDS[:3]
    res2 = judge.judge_pending(p, monthly, det, client, max_judgments=100)
    assert res2["pending_before"] == n_flagged - 1
    assert len(judge.load_judgments(p.paths.judgments)) == n_flagged


def test_events_near_window():
    evs = [{"month": "2020-03", "kind": "external", "label": "x", "source": "s"}]
    assert judge.events_near(evs, pd.Period("2020-08", freq="M"), 6)[0]["offset_months"] == -5
    assert judge.events_near(evs, pd.Period("2020-10", freq="M"), 6) == []


# --- human-in-the-loop -------------------------------------------------------

def test_issue_marker_roundtrip_and_steward_decision(tmp_path):
    p = make_profile(tmp_path)
    j = {"series": "notices", "month": "2020-01", "category": "DQE", "consistency": 1.0,
         "review_level": "mandatory", "votes": 3, "ensemble_score": 0.7, "near_drift": False,
         "model": "m", "temperature": 0.7, "prompt": "evidence",
         "runs": [{"category": "DQE", "confidence": 0.9, "reasoning": "a | b"}] * 3}
    body = review.issue_body(p, "notices:2020-01", j, "https://x")
    issue = {"number": 7, "html_url": "u", "state": "closed", "body": body, "closed_at": "t", "updated_at": "t",
             "labels": [{"name": "layer3"}, {"name": "review:mandatory"}, {"name": "steward:SP"}]}
    r = review.parse_review(issue, p.categories)
    assert r["profile"] == "test-profile" and r["anomaly_id"] == "notices:2020-01"
    assert r["status"] == "decided" and r["steward_category"] == "SP"
    issue["state"] = "open"
    assert review.parse_review(issue, p.categories)["status"] == "pending"
    issue["labels"].append({"name": "steward:GES"})
    assert review.parse_review(issue, p.categories)["status"] == "conflicting_labels"


class FakeGitHub:
    repo = "owner/repo"

    def __init__(self):
        self.created, self.labels = [], set()

    def ensure_labels(self, wanted):
        self.labels |= set(wanted)

    def issues(self):
        return [{"number": i + 1, "body": c["body"], "labels": [], "state": "open", "html_url": ""}
                for i, c in enumerate(self.created)]

    def create_issue(self, title, body, labels):
        self.created.append({"title": title, "body": body, "labels": labels})
        return {"number": len(self.created)}


def test_open_review_issues_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.setattr(review.time, "sleep", lambda s: None)
    p = make_profile(tmp_path)
    base = {"series": "notices", "consistency": 1.0, "votes": 2, "ensemble_score": 0.6, "near_drift": False,
            "model": "m", "temperature": 0.7, "prompt": "e", "runs": []}
    judgments = {
        "notices:2020-01": {**base, "month": "2020-01", "category": "DQE", "review_level": "mandatory"},
        "notices:2020-02": {**base, "month": "2020-02", "category": "SP", "review_level": "none"},
        "notices:2020-03": {**base, "month": "2020-03", "category": "GES", "review_level": "advisory"},
    }
    gh = FakeGitHub()
    res = review.open_review_issues(p, judgments, set(judgments), gh, "https://x")
    assert [c["anomaly_id"] for c in res["created"]] == ["notices:2020-01", "notices:2020-03"]
    assert "steward:DQE" in gh.labels and "profile:test-profile" in gh.labels
    again = review.open_review_issues(p, judgments, set(judgments), gh, "https://x")
    assert again["created"] == []


# --- Layer 3 summary ---------------------------------------------------------

def test_layer3_score_rules(tmp_path):
    idx = pd.period_range("2024-01", periods=12, freq="M")
    det = pd.DataFrame({"series": "notices", "anomaly": False}, index=idx)
    det.loc[pd.Period("2024-05", freq="M"), "anomaly"] = True
    det.loc[pd.Period("2024-09", freq="M"), "anomaly"] = True
    j = {"model": config.LLM_MODEL, "prompt_version": config.PROMPT_VERSION}
    judgments = {"notices:2024-05": {**j, "category": "SP", "review_level": "none"},
                 "notices:2024-09": {**j, "category": "DQE", "review_level": "mandatory"}}
    s = report.layer3_score(det, judgments, {})
    assert s["pairs_evaluated"] == 12 and s["l3_rate"] == pytest.approx(11 / 12, abs=1e-3) and not s["l3_pass"]
    reviews = {"notices:2024-09": {"status": "decided", "steward_category": "SP"}}
    s2 = report.layer3_score(det, judgments, reviews)
    assert s2["l3_pass"] and s2["l3_rate"] == 1.0
    assert {f["period"] for f in s2["anomaly_flags"]} == {"2024-05", "2024-09"}


def test_end_to_end_without_llm(tmp_path, monkeypatch):
    """detect -> report through main.py on a synthetic zip, all outputs in tmp."""
    import main

    monkeypatch.setattr(config, "ROOT", tmp_path)
    (tmp_path / "profiles").mkdir()
    raw = copy.deepcopy(BASE_PROFILE)
    (tmp_path / "profiles" / "test-profile.json").write_text(json.dumps(raw), encoding="utf-8")
    monkeypatch.setattr(config, "PROFILES_DIR", tmp_path / "profiles")
    rows = synthetic_rows(months=72, per_month=20)
    rows += [f"{9000 + i};2024-06-15;10,00;N;PA;X;Y" for i in range(200)]  # spike in 2024-06
    zp = write_zip(tmp_path / "r.zip", {"a.csv": rows})
    main.main(["run", "--profile", str(tmp_path / "profiles" / "test-profile.json"), "--skip-llm",
               "--input", str(zp), "--as-of", "2026-01-15"])
    summary = json.loads((tmp_path / "results" / "test-profile" / "layer3_summary.json").read_text())
    assert summary["anomalies"]["flagged"] >= 1
    assert summary["source"]["aggregation"]["rows_read"] == len(rows)
    assert summary["environment"]["packages"]["pandas"]
    dash = json.loads((tmp_path / "docs" / "data" / "test-profile.json").read_text())
    assert any(a["month"] == "2024-06" and a["series"] == "notices" for a in dash["anomalies"])
    index = json.loads((tmp_path / "docs" / "data" / "index.json").read_text())
    assert index["profiles"] == [{"id": "test-profile", "title": "Synthetic notices"}]
