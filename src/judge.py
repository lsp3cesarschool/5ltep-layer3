"""Stage 2 of 5L-TEP Layer 3: LLM-as-a-Judge.

A local model served by Ollama reads each candidate anomaly in context and
assigns one category of the profile's taxonomy. Each anomaly is judged
LLM_RUNS times with fixed seeds; the majority label is kept and the share of
runs that agree with it is the label consistency C. Judgments are cached per
profile, so a run only spends inference time on anomalies that have no
judgment yet for the current model and prompt version.
"""

import json
import logging
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

from src import config
from src.profile import Profile

logger = logging.getLogger(__name__)

DETECTOR_NAMES = ("zscore", "mad", "iforest", "lstm_ed")

SYSTEM_PROMPT = """You are a data-quality analyst reviewing open government data.
{domain}

A statistical ensemble flagged one month of a monthly time series built from these
{records} as anomalous. Decide which category best explains the anomaly:

{categories}

Think step by step, using only the evidence given: compare the value with the same
calendar month in other years (seasonality), with the months just before and after,
with the other series, and with the listed events. A change that is abrupt, confined to
the records themselves (for example a jump in volume with no matching event, or a burst
of {excluded} or of records without an identifier) or that looks like a change of
information system points to a data-quality explanation. A seasonal explanation needs
the same calendar month to deviate in the same direction in most years. A policy
explanation needs a listed event whose timing fits.

Answer in JSON with: "reasoning" (at most 120 words, step by step), "category" (one of
{codes}) and "confidence" (0 to 1)."""


def response_schema(profile: Profile) -> dict:
    return {
        "type": "object",
        "properties": {
            "reasoning": {"type": "string"},
            "category": {"type": "string", "enum": list(profile.categories)},
            "confidence": {"type": "number"},
        },
        "required": ["reasoning", "category", "confidence"],
    }


def system_prompt(profile: Profile) -> str:
    rule = profile.get("exclude")
    return SYSTEM_PROMPT.format(
        domain=profile["domain"],
        records=profile["record_label"],
        categories="\n".join(f"- {k}: {v}" for k, v in profile.categories.items()),
        excluded=rule["description"] if rule else "excluded records",
        codes=", ".join(profile.categories),
    )


def _fmt(v: float) -> str:
    return f"{v / 1e6:,.1f}M" if abs(v) >= 1e6 else f"{v:,.0f}"


def seasonal_index(values: pd.Series) -> dict[int, float]:
    """Median ratio of each calendar month to its trailing 12-month median."""
    base = values.shift(1).rolling(12, min_periods=12).median()
    ratio = (values / base.replace(0, np.nan)).dropna()
    by_month = ratio.groupby(ratio.index.month).median()
    return {int(k): round(float(v), 2) for k, v in by_month.items()}


def events_near(events: list[dict], month: pd.Period, window: int) -> list[dict]:
    near = []
    for ev in events:
        gap = (pd.Period(ev["month"], freq="M") - month).n
        if abs(gap) <= window:
            near.append({**ev, "offset_months": gap})
    return near


def build_prompt(profile: Profile, series_name: str, month: pd.Period, monthly: pd.DataFrame,
                 det_row: pd.Series, other_flagged: list[str], events: list[dict]) -> str:
    """User prompt with the evidence for one anomaly."""
    k = config.CONTEXT_MONTHS
    window = monthly[(monthly.index >= month - k) & (monthly.index <= month + k)]
    col = monthly[series_name]
    baseline = col[(col.index >= month - 12) & (col.index < month)]
    value = float(col.loc[month])
    base_med = float(baseline.median()) if len(baseline) else float("nan")
    change = f"{(value / base_med - 1) * 100:+.0f}%" if base_med else "n/a"
    seas = seasonal_index(col).get(month.month)
    votes = [d for d in DETECTOR_NAMES if det_row[f"{d}_vote"]]
    rule = profile.get("exclude")
    excluded_label = rule["label"] if rule else "excluded"
    series_cols = list(profile.series)

    lines = [
        f"Series: {series_name} - {profile.series[series_name]['description']}.",
        f"Anomalous month: {month} (calendar month {month.month}).",
        f"Value: {_fmt(value)}; median of the previous 12 months: {_fmt(base_med)} ({change}).",
        f"Typical ratio of calendar month {month.month} to its trailing 12-month median, over all "
        f"years: {seas if seas is not None else 'n/a'} (1.00 = no seasonal effect).",
        f"Detectors that flagged it: {', '.join(votes)} ({int(det_row['votes'])} of 4); "
        f"ensemble score {float(det_row['ensemble_score']):.2f} (0.5 = at threshold).",
        "A Page-Hinkley test found a sustained level shift within "
        f"{config.DRIFT_TOLERANCE_MONTHS} months: " + ("yes." if det_row["near_drift"] else "no."),
        "Other series flagged in the same month: " + (", ".join(other_flagged) if other_flagged else "none") + ".",
        "",
        f"Monthly context (+-{k} months). {excluded_label} = {rule['description'] if rule else 'excluded records'}; "
        "no_id = records without an identifier.",
        "month   | " + " | ".join(series_cols) + f" | {excluded_label} | no_id",
    ]
    for m, row in window.iterrows():
        cells = [_fmt(float(row[c])) for c in series_cols]
        mark = "  <== anomaly" if m == month else ""
        lines.append(f"{m} | " + " | ".join(cells) + f" | {int(row['excluded'])} | {int(row['missing_key'])}{mark}")
    near = events_near(events, month, config.EVENT_WINDOW_MONTHS)
    lines.append("")
    if near:
        lines.append(f"Known events within +-{config.EVENT_WINDOW_MONTHS} months:")
        lines += [f"- {e['month']} ({e['offset_months']:+d} months, {e['kind']}): {e['label']}" for e in near]
    else:
        lines.append(f"No known events within +-{config.EVENT_WINDOW_MONTHS} months.")
    return "\n".join(lines)


class OllamaClient:
    def __init__(self, url: str = config.OLLAMA_URL, model: str = config.LLM_MODEL):
        self.url = url.rstrip("/")
        self.model = model

    def info(self) -> dict:
        """Model digest and server version, recorded for provenance."""
        out = {"model": self.model}
        try:
            out["ollama_version"] = requests.get(f"{self.url}/api/version", timeout=10).json().get("version")
            for t in requests.get(f"{self.url}/api/tags", timeout=10).json().get("models", []):
                if self.model in (t.get("name"), t.get("model")):
                    out["model_digest"] = t.get("digest")
                    out["quantization"] = t.get("details", {}).get("quantization_level")
        except requests.RequestException as exc:
            logger.warning("Could not read Ollama info: %s", exc)
        return out

    def generate(self, system: str, prompt: str, seed: int, schema: dict) -> tuple[str, float]:
        payload = {
            "model": self.model,
            "system": system,
            "prompt": prompt,
            "stream": False,
            "format": schema,
            "options": {
                "temperature": config.LLM_TEMPERATURE,
                "seed": seed,
                "num_predict": config.LLM_NUM_PREDICT,
                "num_ctx": config.LLM_NUM_CTX,
            },
        }
        t0 = time.monotonic()
        resp = requests.post(f"{self.url}/api/generate", json=payload, timeout=config.LLM_TIMEOUT_S)
        resp.raise_for_status()
        return resp.json()["response"], time.monotonic() - t0


def parse_response(text: str, categories: dict) -> dict:
    """Parse one model answer; invalid answers are kept and labelled INVALID."""
    try:
        data = json.loads(text)
        cat = str(data.get("category", "")).strip().upper()
        if cat not in categories:
            raise ValueError(f"unknown category {cat!r}")
        conf = float(data.get("confidence", 0))
        return {"category": cat, "confidence": round(min(max(conf, 0.0), 1.0), 3),
                "reasoning": str(data.get("reasoning", "")).strip()}
    except (ValueError, TypeError, AttributeError) as exc:
        return {"category": "INVALID", "confidence": 0.0, "reasoning": f"Unparseable answer ({exc}): {text[:300]}"}


def aggregate_runs(runs: list[dict]) -> dict:
    """Majority vote over runs; ties go to the label with higher mean confidence."""
    valid = [r for r in runs if r["category"] != "INVALID"]
    if not valid:
        return {"category": "INVALID", "consistency": 0.0}
    counts = Counter(r["category"] for r in valid)
    top = max(counts.values())
    tied = [c for c, n in counts.items() if n == top]
    winner = max(tied, key=lambda c: np.mean([r["confidence"] for r in valid if r["category"] == c]))
    return {"category": winner, "consistency": round(top / len(runs), 3)}


def review_level(category: str, consistency: float) -> str:
    """HitL protocol (dissertation, Sec. 4.8.5): DQE is always reviewed."""
    if category in ("DQE", "INVALID"):
        return "mandatory"
    if consistency < config.ADVISORY_CONSISTENCY:
        return "advisory"
    return "none"


def anomaly_id(series_name: str, month) -> str:
    return f"{series_name}:{month}"


def load_judgments(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_judgments(judgments: dict, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(dict(sorted(judgments.items())), ensure_ascii=False, indent=1), encoding="utf-8")


def is_current(entry: dict | None, model: str = config.LLM_MODEL) -> bool:
    return bool(entry) and entry.get("model") == model and entry.get("prompt_version") == config.PROMPT_VERSION


def judge_pending(profile: Profile, monthly: pd.DataFrame, detections: pd.DataFrame, client,
                  max_judgments: int = config.MAX_JUDGMENTS,
                  max_minutes: float = config.MAX_JUDGE_MINUTES) -> dict:
    """Judge flagged anomalies without a current judgment, most recent first."""
    path = profile.paths.judgments
    judgments = load_judgments(path)
    model_info = client.info()
    events = profile.events()
    system = system_prompt(profile)
    schema = response_schema(profile)
    flagged = detections[detections["anomaly"]]
    flagged_by_month: dict = {}
    for m, s in zip(flagged.index, flagged["series"]):
        flagged_by_month.setdefault(m, []).append(s)
    pending = [(m, row) for m, row in flagged.iterrows()
               if not is_current(judgments.get(anomaly_id(row["series"], m)), client.model)]
    pending.sort(key=lambda item: item[0], reverse=True)
    logger.info("%d anomalies flagged, %d pending judgment", len(flagged), len(pending))

    deadline = time.monotonic() + max_minutes * 60
    done = 0
    for month, row in pending:
        if done >= max_judgments or time.monotonic() > deadline:
            break
        others = [s for s in flagged_by_month[month] if s != row["series"]]
        prompt = build_prompt(profile, row["series"], month, monthly, row, others, events)
        runs = []
        for seed in config.LLM_SEEDS[: config.LLM_RUNS]:
            try:
                text, latency = client.generate(system, prompt, seed, schema)
                parsed = parse_response(text, profile.categories)
            except requests.RequestException as exc:
                latency, parsed = 0.0, {"category": "INVALID", "confidence": 0.0, "reasoning": f"Request failed: {exc}"}
            parsed.update({"seed": seed, "latency_s": round(latency, 1)})
            runs.append(parsed)
        vote = aggregate_runs(runs)
        aid = anomaly_id(row["series"], month)
        judgments[aid] = {
            "series": row["series"],
            "month": str(month),
            "category": vote["category"],
            "consistency": vote["consistency"],
            "review_level": review_level(vote["category"], vote["consistency"]),
            "ensemble_score": float(row["ensemble_score"]),
            "votes": int(row["votes"]),
            "near_drift": bool(row["near_drift"]),
            "runs": runs,
            "prompt": prompt,
            "model": client.model,
            "model_digest": model_info.get("model_digest"),
            "ollama_version": model_info.get("ollama_version"),
            "temperature": config.LLM_TEMPERATURE,
            "prompt_version": config.PROMPT_VERSION,
            "judged_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        done += 1
        save_judgments(judgments, path)  # persist after each anomaly: a timeout loses nothing
        logger.info("[%d] %s -> %s (C=%.2f)", done, aid, vote["category"], vote["consistency"])
    return {"judged_now": done, "pending_before": len(pending), "model": model_info}
