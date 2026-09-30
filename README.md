# 5LTEP-L3: 5L-TEP Layer 3 Anomaly Detection Toolkit

**English** · [Português](LEIAME.md)

**Ensemble anomaly detection + local LLM-as-a-Judge + human-in-the-loop review for CKAN-based Open Government Data portals.**

[![Tests](https://github.com/lsp3cesarschool/5ltep-layer3/actions/workflows/tests.yml/badge.svg)](https://github.com/lsp3cesarschool/5ltep-layer3/actions/workflows/tests.yml)
[![Layer 3](https://github.com/lsp3cesarschool/5ltep-layer3/actions/workflows/layer3.yml/badge.svg)](https://github.com/lsp3cesarschool/5ltep-layer3/actions/workflows/layer3.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

📊 **Dashboard:** <https://lsp3cesarschool.github.io/5ltep-layer3/> (anomalies, LLM labels, steward decisions, provenance of every result)
🧑‍⚖️ **Review queue:** [open `layer3` issues](https://github.com/lsp3cesarschool/5ltep-layer3/issues?q=is%3Aissue+is%3Aopen+label%3Alayer3)
🧪 **Which LLM judges, and why:** [5ltep-layer3-modeltest](https://github.com/lsp3cesarschool/5ltep-layer3-modeltest), the monthly model benchmark
🔁 **Control experiment on another portal:** [5ltep-layer3-aneel](https://github.com/lsp3cesarschool/5ltep-layer3-aneel) (ANEEL, same code)

> **Status: research demonstration.** This toolkit is part of a master's research project and is
> maintained by its author. It is not an official IBAMA (or ANEEL) service, and it does not assume that
> any agency will review its results or adopt it. The full flow, human review included, is working and
> ready to be adopted. The open review issues demonstrate that flow: no steward is assigned, and the
> author deliberately does not act as one, since labelling the tool's own output would be
> self-evaluation.

## Use case in one paragraph

Take a large open dataset, such as IBAMA's infraction notices, and suppose we want to fix what is
wrong in it, but do not know where to start. This layer finds the **periods** whose volume or values
depart from the usual pattern (for example, a month with three times the usual number of notices)
and uses AI to check which departures have a known explanation. A month with more notices in the dry
season, when the same happens every year, is **seasonal**; a drop that coincides with a new law is
**policy-driven**. What remains, and above all what looks like a **data problem** (a system migration,
a backlog, a burst of records without an identifier), is sent to people first. Instead of reviewing
records at random, the team starts with the periods that nothing explains, and the people who make
the manual corrections are allocated where they matter most. The AI only proposes; a data steward
confirms or corrects every decision that leads to action.

## Key terms

| Term | Meaning here |
|---|---|
| **Anomaly** | a month of a monthly series (e.g. number of notices, total of fines) that departs from its usual pattern, flagged by at least 2 of 4 statistical detectors |
| **Level shift** | a lasting change of level (not a one-month spike), detected by a Page-Hinkley test |
| **LLM-as-a-Judge** | a small language model, run locally and free of charge, that reads each anomaly with its context and says which of the four causes below explains it best |
| **Data steward** | the person who confirms or corrects the judge's label (through a GitHub Issue) before any action |

The four causes (categories) the judge chooses from, and why they matter:

| Code | Category | Example (IBAMA) | What it means for the team |
|---|---|---|---|
| **PDC** | Policy-Driven Change | notices change right after a new decree or a change of government | explained by a known event: document it |
| **SP** | Seasonal Pattern | January has fewer notices almost every year | expected behaviour: no action |
| **DQE** | Data-Quality Event | a month with almost no records in an active series; a burst of records without identifier | a **data problem**: always reviewed by a steward, first in line for correction |
| **GES** | Genuine Enforcement Shift | a gradual, lasting increase with no event, no seasonality and no data signs | a real change nobody has explained yet: worth investigating |

## Overview

This toolkit implements **Layer 3 (Anomaly Detection)** of the Five-Layer Trust Engineering Pyramid
(5L-TEP) for Open Government Data quality assurance (Pinheiro et al., SOFTENG 2026). Layer 3 watches
the *behaviour of the data over time*: unexpected drops, jumps and level shifts in aggregated series
that structural (Layer 1) and semantic (Layer 2) checks cannot anticipate.

It follows the two-stage protocol of the 5L-TEP paper:

1. **Automated statistical monitoring** flags candidate anomalies: an ensemble of four detectors
   votes on every month, and a Page-Hinkley test separates sustained drift from point anomalies.
2. **Interpretation and review**: a local LLM ([Ollama](https://ollama.com); currently `qwen3:4b`,
   chosen by the [model benchmark](https://github.com/lsp3cesarschool/5ltep-layer3-modeltest)) reads
   each candidate in context and proposes a cause; anomalies that point to a data-quality problem,
   or on which the LLM is inconsistent, go to a **data steward** as GitHub Issues. The steward's
   decision prevails.

The first deployment monitors IBAMA's **infraction notices** (*Autos de Infração*, 700k+ records
since 1977) from [dadosabertos.ibama.gov.br](https://dadosabertos.ibama.gov.br). Everything that
is specific to that dataset lives in one declarative **profile**, so the same code monitors other
datasets, other cuts of the data and other CKAN portals (see
[Adapting to other datasets, cuts and portals](#adapting-to-other-datasets-cuts-and-portals)).

> **Scope**: this repository contains **only** Layer 3. Layer 4 (Observability & Provenance) is
> [5ltep-layer4](https://github.com/lsp3cesarschool/5ltep-layer4); Layers 1, 2 and 5 are outside
> this implementation. Layer 3 exposes its result in the fields the 5L-TEP provenance record
> expects (`l3_pass`, `anomaly_flags`), ready for Layers 4 and 5.

### Architecture

```
┌────────────────────────────────────────────────────────────┐
│  GitHub Actions: monthly cron  +  "Run workflow" button    │
│  (public repo runner: 4 vCPU / 16 GB, no minute quota)     │
└─────────────────────────────┬──────────────────────────────┘
                              │ profile (profiles/*.json)
                              ▼
┌────────────────────────────────────────────────────────────┐
│ ① Source      CKAN package_show → resource URL → download  │
│               SHA-256 of the file, portal metadata         │
├────────────────────────────────────────────────────────────┤
│ ② Aggregate   only the needed columns (no personal data)   │
│               filters (data cut) → monthly series          │
├────────────────────────────────────────────────────────────┤
│ ③ Detect      Z-score · MAD · Isolation Forest · LSTM-ED   │
│   (stage 1)   ensemble vote ≥ 2 of 4  +  Page-Hinkley      │
├────────────────────────────────────────────────────────────┤
│ ④ Judge       Ollama + model chosen by the benchmark,      │
│   (stage 2)   3 seeded runs, CoT, JSON-schema answer       │
│               → majority + consistency                     │
├────────────────────────────────────────────────────────────┤
│ ⑤ Review      GitHub Issues: steward:<CATEGORY> + close    │
│   (HitL)      → results/<profile>/reviews.json             │
├────────────────────────────────────────────────────────────┤
│ ⑥ Report      layer3_summary.json (l3_rate, l3_pass,       │
│               anomaly_flags) + dashboard data (Pages)      │
└─────────────────────────────┬──────────────────────────────┘
                              ▼
         Git repository: every series, detection, judgment,
         review and summary is versioned (auditable history)
```

## Stage 1: statistical detection

Each series is analysed on a log scale (counts and fine totals are heavy-tailed: a single fine can
exceed R$ 4 billion). The log is scale-invariant, so converting old currencies only removes the
artificial steps of currency reforms; zeros get a floor of half the smallest positive value.

| Detector | What it scores | Flags when | Reference |
|---|---|---|---|
| Rolling Z-score | distance to the mean of the previous 12 months | \|z\| > 3 | SOFTENG 2026 (k = 3, 12-period baseline) |
| Rolling MAD | modified z-score against the previous 12 months' median | \|M\| > 3 | Iglewicz & Hoaglin (1993) |
| Isolation Forest | level, first difference, residual to rolling median | top 5% (contamination 0.05) | Liu et al. (2008) |
| LSTM encoder-decoder | reconstruction error over 12-month windows (64 units, dropout 0.2) | above the 99th percentile | Malhotra et al. (2016) |
| **Ensemble** | votes of the four detectors | **≥ 2 of 4** | majority vote |
| Page-Hinkley | cumulative deviation of the level (two-sided) | δ = 0.5, λ = 12 (noise units) | Page (1954); SOFTENG 2026 |

Page-Hinkley alarms do not vote: they mark **sustained level shifts** (drift), which the 5L-TEP
paper routes to a review of the data's structure rather than to remediation. Whether an anomaly is
near a drift point is part of the evidence given to the LLM.

All randomness is seeded (`RANDOM_SEED = 42`); two runs on the same series give the same flags.

## Stage 2: LLM-as-a-Judge

For every flagged month, the judge receives: the series description, the value against its
12-month median, the same calendar month in each of the previous 10 years and the years in which it
was also flagged (seasonality evidence), which detectors fired, the Page-Hinkley result, whether the
other series was flagged too, a ±12-month table with both series, excluded (cancelled) records and
records without an identifier, and the known events within ±6 months from the profile's
[event calendar](profiles/events/brazil-environmental-enforcement.json). It answers in JSON
constrained by a schema (Ollama structured outputs), with a step-by-step reasoning, one category (see
[Key terms](#key-terms)) and a confidence.

| Code | Category (IBAMA profile) | HitL |
|---|---|---|
| `PDC` | Policy-Driven Change: legislation, mandate, restructuring, political transition | advisory if inconsistent |
| `SP` | Seasonal Pattern: a recurring annual enforcement cycle | advisory if inconsistent |
| `DQE` | Data-Quality Event: reporting failure, system migration, backlog, retroactive correction | **always reviewed** |
| `GES` | Genuine Enforcement Shift: a real change not explained by the above | advisory if inconsistent |

**Three runs, fixed seeds, T = 0.7.** At temperature 0 the three runs would be identical by
construction and "consistency" would measure nothing. Sampling with fixed seeds (11, 22, 33) lets
the runs disagree, while every run remains reproducible with the same model digest. The majority
label is kept; the label consistency is *C = runs agreeing with the majority / 3*.

**Budget.** CPU inference on the Actions runner is slow, so each run judges at most
`MAX_JUDGMENTS` new anomalies (most recent first) within `MAX_JUDGE_MINUTES`, saving after each
one. A long history is back-filled over a few runs; after that, the monthly run only sees new months.

**Past anomalies are not judged again when their data are the same.** Each judgment stores a
fingerprint (SHA-256) of the data that make the month anomalous: that month and the 12 before it,
for every series. A later run skips the anomaly while the fingerprint matches, even though new
months keep arriving. It is judged again only when:

| Trigger | Why | What happens to the review |
|---|---|---|
| its data changed (automatic) | a retroactive correction in the portal altered that month or its 12-month baseline | the existing issue gets a comment with the old and new label |
| a steward asks for it | *Actions → Layer 3 → Run workflow* with `rejudge` = `stale` (only what an earlier model or prompt version judged) or `all`; also the **Re-judge** button of the dashboard | same |

A new model or prompt version does **not** re-judge the history by itself: each judgment records the
model and prompt version that produced it (shown on the dashboard), and the new model judges the new
anomalies. In every case the previous judgment is kept in the entry's `history`, never overwritten,
and no issue is ever duplicated. Events added to the calendar do not trigger new judgments either.

**Which model.** The model is chosen by measurement, not by feel: the
[model benchmark](https://github.com/lsp3cesarschool/5ltep-layer3-modeltest) runs every month on the
free runner, discovers new small models, tests them on the production prompt against a gold set whose
answers are known by construction, and publishes which model to use. By default (`LLM_MODEL=auto`)
every run of this repository reads that decision and judges with the approved model; the benchmark
switches only when a candidate beats the current model by a margin whose paired confidence interval
is above zero. To keep a fixed model instead, set the repository variable `LLM_MODEL` to a tag (and
`LLM_THINK` for models with a thinking mode); the monthly *Model check* then opens an issue when the
benchmark recommends another one. The first benchmark (30/09/2026) moved production from `gemma3:4b`
(macro-F1 0.50 on the gold set) to `qwen3:4b` with thinking off (0.81).

The LLM is a decision-support tool, not ground truth: every prompt and every reasoning is stored,
and the steward's decision replaces the LLM label wherever there is one.

## Human-in-the-loop review

Two levels of review:

- **Mandatory review**: LLM majority `DQE` (or no valid answer). No corrective action before a
  steward decides.
- **Advisory review**: label consistency *C* < 0.6 (the three runs all disagree).
- **Level-shift review**: the 5L-TEP paper routes confirmed drift to a review of the data's structure
  whatever its label. A permanent jump (e.g. IBAMA's notices multiplied by ~8 from January 1996 on)
  can be a change of information system even when the model calls it a genuine shift. Each
  Page-Hinkley alarm with flagged months around it becomes **one** issue listing those months and
  their LLM labels; the steward decides the cause once, and the decision applies to every month of
  the group that has no issue of its own (an anomaly issue always prevails).

Review levels are a policy applied to stored judgments, so changing them never requires calling the
LLM again. When a policy change makes an open issue unnecessary, it is closed with the label
`superseded` and a link to the issue that replaces it (issues a steward already started labelling are
left alone).

Each anomaly needing review becomes **one GitHub Issue** (idempotent: re-runs never duplicate it)
with the evidence, the three reasonings and instructions. The steward decides by **applying one
`steward:<CATEGORY>` label, commenting the justification and closing the issue**. GitHub records who
decided, when, and why; the [`reviews.yml`](.github/workflows/reviews.yml) workflow copies the
decision into `results/<profile>/reviews.json` and refreshes the dashboard within minutes.

Human-LLM agreement (`human_llm_agreement` in the summary), review time (issue opening to closing)
and the other review metrics are computed from these decisions and shown on the dashboard. They are
empty in this demonstration and fill in as soon as a steward records decisions; no code change is
needed.

## Layer 3 score and output for Layers 4-5

`results/<profile>/layer3_summary.json` carries the Layer 3 result. Over the last 12 complete
months, each (series, month) pair **passes** unless it was flagged by the ensemble and is either not
judged yet, classified `DQE` (by the steward, or by the LLM when no steward has decided), or waiting
for a mandatory review:

- `l3_rate` = passing pairs / all pairs: the *L3* term of the Global Quality Score
  *Qs = w₁L1 + w₂L2 + w₃L3 + w₄L4* (SOFTENG 2026, default *w₃ = 0.2*);
- `l3_pass` = no failing pair;
- `anomaly_flags` = the flagged column–period pairs with their category and who decided it.

`l3_pass` and `anomaly_flags` are the field names of the minimal provenance record in the 5L-TEP
paper, so Layer 4 can ingest them unchanged.

## Data handling and privacy

- The raw file is downloaded to a temporary directory and deleted at the end of the step; it is
  **never committed**. IBAMA's file carries offender names and CPF/CNPJ; the toolkit only ever
  **reads** the columns the profile needs (date, identifier, cancellation flag, fine value), so
  personal data is not even loaded. Only monthly aggregates are versioned.
- **Cancelled notices** are excluded from the series and counted separately (`excluded`).
- **Records without an identifier** (6,806 in IBAMA's file in Sept. 2026) are kept and counted
  (`missing_key`); true duplicates of a non-empty identifier would be dropped (none found).
- **The current month is never analysed**: it is still being filled in and would always look like a drop.
- **Sparse start**: the analysis starts at the first month from which the next 12 months have a
  median of at least 3 records (1980-11 for IBAMA). Only the beginning is trimmed: quiet months
  later on are kept, which matters for low-volume datasets.
- **Currency**: Brazil changed currency five times before the Real (July 1994). The reforms are in a
  hand-editable file, [`profiles/monetary/brazil-currency.json`](profiles/monetary/brazil-currency.json)
  (date, old and new currency, divisor, legal source). Series marked `"convert_currency": true` have
  each value converted to Reais at its own date, which removes the artificial /1,000 steps of the
  reforms; values are **not** adjusted for inflation. The reforms also reach the judge as events.
  When a new reform happens, add one entry to that file.

## Event calendar: curated by people, suggested by the LLM

The judge can only relate an anomaly to events it is told about. Each profile has an event calendar
(e.g. [`brazil-environmental-enforcement.json`](profiles/events/brazil-environmental-enforcement.json)),
where every event has a `status`:

| status | meaning | given to the judge |
|---|---|---|
| `verified` | checked by a steward, with a source | yes |
| `suggested` | proposed by the LLM, not checked yet | only if grounded on a quoted source, flagged *[unverified suggestion]* (profile option `events_include_suggested`); suggestions made from the model's memory never, until verified |
| `rejected` | checked and discarded | no (kept so it is not suggested again) |

**Filling it automatically.** `python main.py suggest-events` looks at the years with anomalies and,
for each one, fetches the "*year* in *country*" Wikipedia page (profile option `event_sources`; for
Brazil, `pt.wikipedia.org/wiki/2019_no_Brasil` and so on). The LLM selects the events that could
have affected the records and must **quote the sentence** each one comes from; suggestions whose
quote is not found in the page are discarded, which filters out invented events. With `--offline`,
the model answers from its own knowledge instead; those entries are marked `origin: llm-memory` and
are never given to the judge before a steward verifies them. This is not a theoretical precaution:
in a first run without grounding, Gemma 3 4B (the model then in use) proposed non-existent impeachments and decrees with
made-up numbers. Use offline mode only as a list of leads to check.

On GitHub, the dashboard's **Suggest events** button opens the
[`events.yml`](.github/workflows/events.yml) workflow, which runs the same command and opens a
**pull request** with the suggestions. The steward reviews the diff, sets each `status` to
`verified` or `rejected`, fixes labels if needed, and merges.

## FAIR principles and replicability

The toolkit is designed so that its *results* are FAIR (Wilkinson et al., 2016), and so that the
*method* can be re-applied elsewhere.

| Principle | How it is met |
|---|---|
| **F**indable | Public repository with a persistent URL, [`CITATION.cff`](CITATION.cff) (machine-readable citation), descriptive topics; every result has a stable path `results/<profile>/…` and a Git commit hash. Archiving a release in Zenodo adds a DOI. |
| **A**ccessible | Everything is retrievable over HTTPS with no login: code, series, detections, judgments, reviews and summaries in the repository; the dashboard on GitHub Pages; the source via the portal's open CKAN API. |
| **I**nteroperable | Open formats only (CSV, JSON); ISO 8601 dates; the source is addressed through the standard CKAN Action API; the summary uses the field names of the 5L-TEP provenance record consumed by Layer 4 (W3C PROV-DM based); categories and parameters are explicit in the files. |
| **R**eusable | MIT licence; rich provenance attached to every result (below); declarative profiles make the method reusable on other data without code changes; tests and an evaluation suite document expected behaviour. |

**What each run records** (`data/<profile>/source_manifest.json`, `results/<profile>/layer3_summary.json`, `run_log.jsonl`):

- the portal, dataset and resource URL, the portal's `metadata_modified`, and the **SHA-256 of the
  exact file analysed**;
- the **SHA-256 of the profile** used, and the aggregation statistics (rows read, filtered,
  excluded, without identifier, invalid dates);
- every **method parameter** (thresholds, windows, seeds, model, temperature, prompt version);
- the **environment**: Python and package versions;
- for each judgment: the full prompt, the three answers with seeds and latencies, the **model
  digest** and the Ollama version;
- the Git commit, which timestamps and makes tamper-evident all of the above.

**Reproducing a past result.** The portal's file changes every day, so it cannot be downloaded
again as it was. The monthly series of every run is versioned instead:

```bash
git checkout <commit-of-the-run>
python main.py detect --from-series --profile ibama-autos-infracao   # same flags, no download
python evaluation/judge_report.py --profile ibama-autos-infracao     # LLM statistics from the stored answers
```

Detection is deterministic on the same series. Re-running the judge needs the same model digest
(recorded) and gives the same answers for the same seeds on the same Ollama build; the stored answers
make the classification auditable even without re-running it. The SHA-256 lets anyone who kept a
copy of the source file prove it is the one that was analysed.

## Adapting to other datasets, cuts and portals

Everything that is specific to a dataset is in a **profile**: a JSON file in [`profiles/`](profiles/).
The code never changes. Outputs are kept per profile (`data/<id>/`, `results/<id>/`,
`docs/data/<id>.json`), so several profiles live side by side and the dashboard has a selector.

### Profile reference

| Field | Meaning |
|---|---|
| `id`, `title`, `country` | identifier (file name, output folder, issue label), human title, country of the publisher |
| `scheduled` | `true`: included in the monthly run; `false`: run on demand only |
| `source.portal_url`, `dataset_id`, `resource_name`, `resource_format` | the CKAN portal, the dataset slug and the resource (matched by name and format). The URL is looked up at every run, so moved files are followed. |
| `file.compression` (`zip`/`none`), `member_pattern`, `sep`, `encoding` | how to read the resource (a zip of CSVs or one CSV) |
| `columns.date`, `columns.key` | the date that places a record in a month; the record identifier (optional) |
| `exclude` | rows removed from the series but counted as context (e.g. cancelled notices) |
| `filters` | **the data cut**: a list of `{"column", "in" \| "not_in" \| "equals"}` |
| `period.start`, `period.end` | optional time window (`YYYY-MM`) |
| `sparse_min_records` | the analysis starts where the next 12 months have at least this median |
| `series` | the monthly series: `{"name", "kind": "count"}` or `{"name", "kind": "sum", "column", "number_format": "br" \| "plain", "convert_currency": true \| false}`, each with a `description` the LLM reads |
| `domain`, `record_label` | a paragraph describing the publisher and the records, for the LLM |
| `events_file` | the event calendar (`{"month", "kind", "label", "source", "status"}`) |
| `events_include_suggested` | give unverified LLM suggestions to the judge (flagged as such) |
| `event_sources` | where `suggest-events` looks, e.g. `{"wikipedia": {"lang": "pt", "title": "{year} no Brasil"}}` |
| `monetary_file` | currency reforms, for `convert_currency` and as events |
| `categories` | the taxonomy the LLM chooses from and the steward labels (`DQE` is always sent to review) |

### 1. Another cut of the same dataset

Copy the profile, give it a new `id` and add filters and/or a period. The repository ships an
example, [`ibama-autos-infracao-amazonia-legal.json`](profiles/ibama-autos-infracao-amazonia-legal.json),
which keeps only the nine Legal Amazon states from 1996 on:

```json
"filters": [{"column": "UF", "in": ["AC", "AM", "AP", "MA", "MT", "PA", "RO", "RR", "TO"]}],
"period": {"start": "1996-01", "end": null}
```

Other cuts follow the same pattern: an infraction type (`TIPO_INFRACAO`), a biome, a single state,
only fines above a value (a `sum` series over a filtered set), and so on.

### 2. Another dataset on the same portal

Point `source` to the dataset and resource, map `columns`, and declare the `series` that make sense
(e.g. seized items per month for *Termos de Apreensão*). Adjust `domain`, `record_label`, and, if
the causes differ, `categories` and the event calendar.

### 3. Another CKAN portal

Only `source.portal_url` and the dataset-specific fields change. Check the profile against the live
portal before the first run: it validates the profile, resolves and downloads the resource, reads
the columns and shows the analysis window:

```bash
python main.py check-profile profiles/my-portal-dataset.json
```

A second portal runs as a separate instance, set up by the author following the same steps another
agency would take to adopt the toolkit (ANEEL itself is not involved):
[**5ltep-layer3-aneel**](https://github.com/lsp3cesarschool/5ltep-layer3-aneel) monitors the
infraction notices of ANEEL, Brazil's electricity regulator, from
[dadosabertos.aneel.gov.br](https://dadosabertos.aneel.gov.br). It differs from IBAMA in every
dimension a profile covers: one plain CSV instead of a zip of yearly files, other column names, no
cancellation flag, ~1,600 records since 2018 instead of 700,000 since 1977, and a much shorter
event calendar, meant to be extended with `suggest-events`. That instance runs the same code as
this repository; only its profile, calendar and README differ. Running it exposed two assumptions
that held for IBAMA but not in general (sparse months only at the start of a series; a hard-coded
default profile); both were fixed here, in the shared code.

Portals that are not CKAN need a small source adapter in `src/ckan_source.py` (the rest of the
pipeline only needs a file on disk).

### Running your own instance (fork)

1. **Fork** this repository.
2. Add or edit profiles in `profiles/`; set `"scheduled": true` on those the monthly run must cover.
3. **Start with a clean history:** delete `data/`, `results/` and `docs/data/` and commit. They are
   recreated by the first run.
4. In the fork, enable the workflows in the **Actions** tab (GitHub disables them in forks) and
   GitHub Pages (*Settings → Pages → Deploy from a branch → `main` / `docs`*).
5. Keep the repository **public**: public repositories get the 16 GB runner the LLM needs, and no
   minute quota. (A private repository's 7 GB runner is tight for a 4B model.)
6. Run *Actions → 5L-TEP Layer 3 Anomaly Detection → Run workflow* once. It works through the
   whole history in batches of 25 judgments, each batch starting the next, until nothing is pending.
7. By default the model follows the [model benchmark](https://github.com/lsp3cesarschool/5ltep-layer3-modeltest)
   (`LLM_MODEL=auto`). To pin one, set the repository variable `LLM_MODEL` to an Ollama tag (and
   `LLM_THINK=false` for models with a thinking mode). Earlier judgments are kept either way; run the
   workflow with `rejudge` = `stale` or `all` if you want the history judged again.

Do not add other portals' profiles to *this* repository's scheduled runs without discussing it
first: its results feed the IBAMA case study.

## Quick start (local)

```bash
git clone https://github.com/lsp3cesarschool/5ltep-layer3.git
cd 5ltep-layer3
pip install -r requirements.txt          # CPU-only PyTorch

python main.py list-profiles
python main.py run --skip-llm            # download + detect + report, no LLM
pytest tests/ -v                          # no network, no LLM needed
```

With a local Ollama (`ollama serve` and `ollama pull qwen3:4b`):

```bash
python main.py judge --max-judgments 5
python main.py report
```

Then open `docs/index.html` through a local server (`python -m http.server -d docs`).

## GitHub Actions deployment

| Workflow | When | What |
|---|---|---|
| [`layer3.yml`](.github/workflows/layer3.yml) | 5th of every month, 06:00 UTC, and **manual** (*Run workflow*, with profile, batch size, "continue", "detectors only" and **`rejudge`** inputs; dashboard buttons *Run Layer 3 now* and *Re-judge*) | resolve the model → detect → judge a batch → open issues → report → commit → next batch, until nothing is pending |
| [`reviews.yml`](.github/workflows/reviews.yml) | whenever a `layer3` issue is labelled, closed or reopened | sync steward decisions, refresh the L3 score and dashboard |
| [`model-check.yml`](.github/workflows/model-check.yml) | 22nd of every month, and manual | only when `LLM_MODEL` is pinned: compare it with the model benchmark's recommendation; issue if a switch is recommended |
| [`events.yml`](.github/workflows/events.yml) | **manual** (dashboard button *Suggest events*), with profile, online/offline and years inputs | LLM suggestions for the event calendar → pull request for review |
| [`tests.yml`](.github/workflows/tests.yml) | push / pull request | test suite on Python 3.10–3.12 |

**Why monthly?** Layer 3 looks for changes in monthly series; running every six hours like the Layer 4
monitor would only re-analyse the same months. A steward who is about to take a publication
decision (Layer 5) triggers a run from the dashboard's **Run Layer 3 now** button, which opens the
workflow page: the run is authorised by the steward's own GitHub login, and no token is ever
embedded in the public page.

**Batches until done.** A month is plenty of time to judge every anomaly, but a single job is
limited to six hours. Each run therefore judges one batch (`max_judgments`, 25 by default,
about 45 minutes on the CPU runner), commits, so the dashboard shows progress, and starts the next
batch while anomalies or review issues are still pending (up to 60 batches per chain). Batches
after the first re-use the series committed by the first one, so the whole chain analyses the same
data even if the portal is updated in the meantime. After the initial back-fill, a monthly chain is
usually a single batch.

**Ollama in Actions.** The job installs Ollama, restores `~/.ollama/models` from `actions/cache`
(the 3.3 GB model is downloaded once), starts the server, waits for its health check and pulls the
model. Inference is CPU-only.

**Alerts cost nothing and need no mail server** (as in Layer 4): at the end of a chain, if
**mandatory** reviews are still open, the last batch (which has already committed everything) fails
on purpose, and GitHub e-mails the maintainer about the failed run. Open mandatory reviews therefore
produce one reminder per monthly run until a steward decides them. Enable
*Settings → Notifications → Actions* on your account.

## Evaluation

Scripts in [`evaluation/`](evaluation/) reproduce every number this repository reports; results are
saved in `evaluation/results/`. Only numbers produced by these scripts are reported.

- [`synthetic_injection.py`](evaluation/synthetic_injection.py): injects anomalies with known ground
  truth (spike, dip, two-month gap, level shift) into the real series and measures recall,
  precision and induced false alarms per detector and for the ensemble, plus Page-Hinkley recall on
  level shifts.
- [`judge_report.py`](evaluation/judge_report.py): category distribution, label consistency, invalid
  answers and latency of the LLM-as-a-Judge, and human-LLM agreement with a confusion matrix once
  stewards have decided.

## Project structure

```
5ltep-layer3/
├── main.py                        # pipeline CLI (detect, judge, issues, sync-reviews, report,
│                                  #   check-profile, suggest-events)
├── profiles/
│   ├── ibama-autos-infracao.json                 # IBAMA infraction notices, Brazil (scheduled)
│   ├── ibama-autos-infracao-amazonia-legal.json  # example data cut (on demand)
│   ├── events/                                   # event calendars (verified / suggested / rejected)
│   └── monetary/brazil-currency.json             # currency reforms (hand-editable)
├── src/
│   ├── config.py                  # method parameters (overridable by environment variables)
│   ├── profile.py                 # profile loading and validation, output paths
│   ├── ckan_source.py             # CKAN resource lookup and download (SHA-256)
│   ├── aggregate.py               # minimal-column reading, data cut, monthly series
│   ├── detectors.py               # Z-score, MAD, Isolation Forest, LSTM-ED, ensemble, Page-Hinkley
│   ├── judge.py                   # LLM-as-a-Judge (Ollama), majority vote, consistency, cache
│   ├── review.py                  # GitHub Issues review queue (HitL)
│   ├── events_suggest.py          # LLM suggestions for the event calendar, grounded on Wikipedia
│   ├── monetary.py                # currency conversion and reform events
│   └── report.py                  # Layer 3 score, summary, dashboard data
├── docs/                          # GitHub Pages dashboard (static; data/ written by the pipeline)
├── data/<profile>/                # monthly series + source manifest (committed by the bot)
├── results/<profile>/             # detections, drift, judgments, reviews, summary, run log
├── evaluation/                    # reproducible evaluation scripts and results
├── tests/                         # unit + integration tests (no network, fake LLM)
├── .github/workflows/             # layer3.yml, reviews.yml, events.yml, tests.yml
├── .github/actions/setup-ollama/  # shared step: install Ollama, cached model, start, pull
├── CITATION.cff
└── LICENSE
```

## Configuration

Method parameters are in [`src/config.py`](src/config.py); each can be overridden by an environment
variable of the same name (the values used are recorded in every summary). The most relevant:

| Variable | Default | Description |
|---|---|---|
| `PROFILE` | `ibama-autos-infracao` | profile used when `--profile` is not given |
| `BASELINE_WINDOW` | `12` | rolling baseline (months) for Z-score and MAD |
| `ZSCORE_K`, `MAD_K` | `3.0` | thresholds |
| `IF_CONTAMINATION` | `0.05` | Isolation Forest share of outliers |
| `LSTM_PERCENTILE` | `99.0` | LSTM-ED threshold on reconstruction errors |
| `ENSEMBLE_MIN_VOTES` | `2` | votes needed to flag a month |
| `PH_DELTA`, `PH_LAMBDA` | `0.5`, `12.0` | Page-Hinkley tolerance and threshold (noise units) |
| `LLM_MODEL` | `auto` | `auto`: the model approved by the [model benchmark](https://github.com/lsp3cesarschool/5ltep-layer3-modeltest), read at the start of each run; a tag (e.g. `qwen3:4b`) pins the model (in Actions: repository variable) |
| `LLM_THINK` | *(empty)* | `false` turns off the thinking mode of models that have one; empty: as the benchmark tested it (auto) or the model's default (pinned) |
| `FALLBACK_MODEL` | `qwen3:4b` | used in auto mode if the benchmark cannot be read |
| `LLM_TEMPERATURE`, `LLM_SEEDS` | `0.7`, `11,22,33` | sampling of the three runs |
| `MAX_JUDGMENTS`, `MAX_JUDGE_MINUTES` | `25`, `240` | LLM budget per run |
| `ADVISORY_CONSISTENCY` | `0.6` | below this, advisory review |
| `MAX_NEW_ISSUES` | `15` | review issues opened per run |
| `L3_WINDOW_MONTHS` | `12` | window of the Layer 3 score |

## Limitations

- LLM labels are hypotheses for a steward, not ground truth; the taxonomy and the event calendar
  are curated and incomplete by nature (add events through pull requests, with a source).
- Detection works on monthly aggregates: it finds changes in volume and value, not errors in
  individual records (Layers 1–2).
- Global detectors (Isolation Forest, LSTM-ED) are refitted at every run, so a past month's flag
  can change when new months arrive; rolling detectors do not. Judgments of months that stop being
  flagged are kept in the history but no longer counted.
- Fine totals are nominal; no inflation adjustment is applied.
- CPU inference takes tens of seconds per call on the Actions runner; the budget keeps runs within
  the job limit.

## Academic references

- Pinheiro, L. S., Silva, C. H. B., Aquino, V. B., Carvalho, T. M. C. S., Barros Filho, C. V. R., & Almeida, W. H. C. (2026). *Towards Trust Engineering in Open Data Systems: A Layered Conceptual Framework Integrating Quality Assurance and Governance Perspectives*. SOFTENG 2026, IARIA, pp. 21–28.
- Pinheiro, L. S. & Sérgio, A. T. (2026). *5LTEP-L4: An Open-Source CKAN Toolkit for Provenance-Enabled Observability of Open Government Data*. WFA, Anais Estendidos do WebMedia 2026 (to appear). Code: [5ltep-layer4](https://github.com/lsp3cesarschool/5ltep-layer4).
- Chandola, V., Banerjee, A., & Kumar, V. (2009). Anomaly detection: A survey. *ACM Computing Surveys*, 41(3).
- Liu, F. T., Ting, K. M., & Zhou, Z.-H. (2008). Isolation Forest. *IEEE ICDM*.
- Malhotra, P., et al. (2016). LSTM-based Encoder-Decoder for Multi-sensor Anomaly Detection. *ICML Anomaly Detection Workshop*.
- Iglewicz, B., & Hoaglin, D. (1993). *How to Detect and Handle Outliers*. ASQC Quality Press.
- Page, E. S. (1954). Continuous inspection schemes. *Biometrika*, 41(1/2), 100–115.
- Zheng, L., et al. (2023). Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena. *NeurIPS*.
- Wei, J., et al. (2022). Chain-of-Thought Prompting Elicits Reasoning in Large Language Models. *NeurIPS*.
- Wilkinson, M. D., et al. (2016). The FAIR Guiding Principles for scientific data management and stewardship. *Scientific Data*, 3, 160018.

## License

Code: MIT, see [LICENSE](LICENSE). The monthly series in `data/` are aggregates derived from IBAMA's
open data; when reusing them, cite IBAMA's open data portal as the original source.
