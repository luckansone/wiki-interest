# wiki-interest — Agent Skill (MVP)

An [Agent Skills](https://agentskills.io/specification) skill that answers questions like "is interest in X growing, and in which languages?" from Wikimedia pageview statistics. It produces:

- a compact JSON output for the agent;
- a chart (PNG);
- an A4 PDF report: page 1 is a one-page summary (verdict, confidence, charts, metrics table, limitations); the appendix after it lists the ranking with scores, full per-language details and confidence reasons, all limitations and the monthly pageviews table (as many pages as needed). It is created on every `analyze` run (skip it with `--no-pdf`), in Ukrainian or English (`--out-lang uk|en`).

The agent only chooses arguments and relays the results. **All numbers and verdicts are produced by deterministic code.**

## Quick start

```bash
cd wiki-interest
export WI_CONTACT="you@company.com"          # Wikimedia asks for a contact in the User-Agent
bash scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs --months 24 --pdf
```

`scripts/wi` picks the environment by itself:

- **uv installed (recommended):** `uv run --frozen --no-dev`. Python comes from `.python-version` (3.13; uv downloads it if missing), packages from `uv.lock`, into `.venv`. First run ~1 min, then ~2 s.
- **No uv, but a Python ≥ 3.11 that already has the packages** (e.g. the claude.ai code sandbox): used directly, nothing is installed.
- **No uv:** any Python ≥ 3.11 from `PATH` + pip, pinned by `requirements.txt` (exported from `uv.lock`).
- **`WI_PYTHON=/path/to/python`:** use that interpreter as is.

If neither uv nor Python ≥ 3.11 is available, it prints a JSON error with the install command for uv.

Results go to `./wi_output/<run_id>/`: `run.json`, `series.csv`, `chart.png`, `report.pdf` (always, unless `--no-pdf`). Cache: `~/.cache/wiki-interest` (override with `WI_CACHE`).

## The three target questions

```bash
# 1. Intermittent fasting, pl vs cs, 2 years
bash scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs --months 24 --pdf
# 2. Astronomy in uk: is it growing, and can we trust it
bash scripts/wi analyze --topic "Astronomy" --topic "Solar System" --topic "Telescope" --langs uk --months 36 --pdf
# 3. Learning English in the selected editions + report
bash scripts/wi analyze --topic "English language" --topic "International English Language Testing System" \
  --topic "Test of English as a Foreign Language" --langs uk,pl,tr,vi,id,pt --months 24 --pdf
```

## Structure

```text
SKILL.md                 instructions for the agent (decision table, templates, interpretation rules)
references/METHODOLOGY.md formulas, thresholds, limitations
scripts/wi               launcher (uv run, or pip venv fallback)
scripts/wi.py            CLI: analyze, report
scripts/wiki_api.py      Wikidata sitelinks, per-article + aggregate pageviews, cache, retry
scripts/metrics.py       YoY, bootstrap CI, Theil–Sen, Mann–Kendall, flags, confidence, ranking
scripts/report.py        chart + PDF: one-page summary + flowing appendix (matplotlib only, no system dependencies)
tests/                   pytest: statistics on synthetic series, e2e CLI, eval harness
evals/                   agent-loop run on a cheap model + scenarios
```

## Development

The tooling follows the same setup as [langgraph-agent-toolkit](https://github.com/kryvokhyzha/langgraph-agent-toolkit): uv, `pyproject.toml` with dependency groups, ruff, pre-commit and a GitHub Actions matrix.

```bash
make uv_install_deps       # uv sync: runtime + dev groups (lint, tests) on Python 3.13
make test                  # pytest (offline, synthetic Wikimedia responses)
make test_cov              # with coverage (threshold in .coveragerc)
make lint                  # ruff check + ruff format --check
make pre_commit_install    # needs a git repo
make uv_get_lock uv_export_requirements   # after changing dependencies in pyproject.toml
```

- `pyproject.toml`: runtime deps (what `scripts/wi` installs) and the `lint` / `tests` / `dev` groups; `[tool.uv] package = false`, since the skill runs from `scripts/` and is not installed as a package.
- `requirements.txt` is generated from `uv.lock` (the `uv-export` pre-commit hook and CI keep them in sync). Do not edit it by hand.
- CI: lockfile and `requirements.txt` checks, ruff, tests on 3.11–3.14, and an end-to-end `bash scripts/wi` run from a clean checkout.

## Upload to Claude

```bash
make skill_zip        # -> dist/wiki-interest.zip (~150 KB)
```

The zip is built from an allowlist (`SKILL_FILES` in the Makefile) with `wiki-interest/` as its root folder. It never contains `.venv` (~280 MB), caches, `wi_output/` or `.claude/`. Zipping the project folder by hand includes `.venv` and exceeds the 30 MB upload limit.

On claude.ai the skill runs in the code-execution sandbox. It needs network access to `wikimedia.org` and `www.wikidata.org` (add them to the allowed domains in the code execution settings if egress is restricted). Without network, only the offline demo mode (`WI_FAKE_API=1`) works.

## Offline demo mode

`WI_FAKE_API=1 bash scripts/wi analyze ...` replaces the API with synthetic responses in the real format. The PDF then gets a red banner, "ДЕМО: СИНТЕТИЧНІ ДАНІ". Use this mode for tests and for evals on free models without load on Wikimedia. Its numbers mean nothing about real interest.

## Checking on cheap models (Haiku 4.5 / free OpenRouter)

```bash
uv sync
export OPENROUTER_API_KEY=...
uv run python evals/run_eval.py --model anthropic/claude-haiku-4.5 --repeats 2
uv run python evals/run_eval.py --fake-api   # default: nvidia/nemotron-3-super-120b-a12b:free, no Wikimedia load
```

The harness works like a real skill host:

- The model sees only the skill's `name` and `description`.
- It reads SKILL.md itself.
- It calls `bash` and `read_file`; commands are restricted to an allowlist.

Automatic checks:

- the right arguments (languages, `--months`, `--question`, no `--no-pdf`);
- the answer gives the PDF path;
- at most 6–7 tool calls;
- mentions of confidence and limitations;
- **every % in the answer must be present in the tool output**, which catches hallucinated numbers;
- for a request with no languages, the agent must ask instead of guessing.

Traces are saved to `evals/traces/`.

## How the code was verified

- **Statistics are tested against a known ground truth.** Synthetic series with a set trend, seasonality, spike and edition-wide shift. Checks: correct verdict and flags, invariance to scale, determinism, and weights actually changing the ranking.
- **E2E on the three questions** through the CLI, with the fake API in the real JSON format. Checks: correct verdicts, flags (`PROJECT_SHIFT`, `SPIKE_DRIVEN`, `MISSING_ARTICLE`), page 1 is the summary and the appendix flows onto extra pages without dropping rows, and the text is extractable (fonts embedded).
- **Visual review** of rendered PDFs for 2 and 8 languages. Label collisions and overflow were fixed.
- **Reproducibility.** Dependencies are locked in `uv.lock`. The suite passes on Python 3.11, 3.12, 3.13 and 3.14 (CI matrix in `.github/workflows/test.yml`). The launcher was tested from a clean copy via uv, via the pip fallback, and without any suitable Python.
- **Spec.** `agentskills validate` → `Valid skill`.
- **The eval harness is tested itself.** A scripted "model" with an honest answer passes; one with a hallucinated number is caught; dangerous commands are blocked.

- **Live API (2026-09-27).** The three target questions were run against live Wikimedia/Wikidata. Series were cross-checked with direct Pageviews API calls (cs intermittent fasting, uk astronomy articles): YoY and medians match exactly. This run found that Wikidata's anonymous limit (~2 fast requests, then 429 with `Retry-After` ≈ 15 s) broke every cold run with 3+ topics; the client now honors `Retry-After`.
- **Haiku 4.5, end to end.** Each scenario agent saw only the skill name and description, read SKILL.md itself and ran the CLI. All ran the correct single command and used only numbers from the output. The first round's answer-quality issues (countries instead of editions, "−39% over 36 months", "weak growth" for a `stable_or_unclear` verdict, missing PDF path) led to the wording rules in SKILL.md and the explicit comparison window in `summary_text`.

**Still to do:** an `evals/run_eval.py` run on OpenRouter free models (needs an API key).

## Limitations of the MVP

- Pageviews measure interest, not willingness to pay.
- A language edition is not a country.
- Redirects are not added.
- Unrecognized bots inside `agent=user` traffic are not filtered.
- At most 8 languages per run.
- The ranking is relative to the chosen set of languages.

## Next iterations

1. **Data quality**: redirects, daily data for bot detection, topic baskets in `assets/`, geo breakdown for top articles.
2. **Dialogue**: `--from-run` + deltas ("add sk"), a "what changed vs the previous run" block, `wi check --claim` for the agent to self-check its conclusions.
3. **Statistics**: STL decomposition, changepoints, forecast with intervals, partial pooling for small editions.
4. **Scale**: monthly `pageview_complete` dumps → Parquet → DuckDB/PySpark (Trino table) for scanning hundreds of topics × dozens of languages. The same CLI behind `--backend dumps`.
5. **Business calibration**: backtest the Wikipedia signal against the product's own installs/revenue by locale (aggregates only); weights by market size.

Each iteration starts with new eval scenarios from real requests and ends with a regression run on a cheap model.
