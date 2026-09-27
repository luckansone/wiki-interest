# Onboarding guide (developers)

This guide is for a developer who changes the `wiki-interest` code or its docs. For
installing and using the skill itself, see `docs/002-installation-guide.md`,
`docs/004-install-in-claude.md` and `docs/005-install-in-codex.md`.

## 1. Day-1 checklist

1. Clone the repository.
2. Read `AGENTS.md` fully. It holds the rules for this repository.
3. Read `SKILL.md`. It is the contract with the agent that runs the skill.
4. Read `references/METHODOLOGY.md`. It holds the formulas and thresholds.
5. Install the dependencies:
   ```bash
   make uv_install_deps
   ```
6. Run the test suite:
   ```bash
   make test
   ```
7. Run the offline demo and open the PDF:
   ```bash
   make demo
   open "$(ls -td wi_output/*/ | head -1)report.pdf"   # macOS; use xdg-open on Linux
   ```

## 2. Repository tour

| Path | Content |
|---|---|
| `SKILL.md` | Instructions for the agent (runtime contract). |
| `references/METHODOLOGY.md` | Formulas, thresholds and limitations. |
| `scripts/wi` | Bash launcher. See `docs/002-installation-guide.md`. |
| `scripts/wi.py` | Entry point: puts `scripts/` on `sys.path`, calls `wiki_interest.cli.main`. |
| `scripts/wiki_interest/` | The Python package. See `docs/001-architecture.md` for the module table. |
| `tests/` | pytest suite. Runs offline, with synthetic Wikimedia responses. |
| `evals/` | Agent-loop evaluation on cheap models (`run_eval.py`, `scenarios.json`). |
| `docs/` | This documentation, numbered `001-...` and up. |
| `pyproject.toml`, `uv.lock` | The only source of dependencies and the supported Python range. |
| `Makefile` | Common tasks: `make test`, `make lint`, `make demo`, `make skill_zip`, and more. There is no `make help` target; read the `Makefile` itself for the full list. |

## 3. How a change flows

1. **Write a test first**, for a bug fix or a new behavior. Use `WI_FAKE_API=1`, or
   monkeypatch `wiki_interest.data.http.get_json`. Tests must not use the network.
2. **Write the code.** Follow the code style in `AGENTS.md`, section 6: Python 3.11 to
   3.14, line length 120, `from __future__ import annotations` in each module, a bound
   logger with a `scope`.
3. **Run `make lint` and `make test`.** Both must pass before you continue.
4. **Update the docs.** Update the matching file in `docs/`, and `SKILL.md` and
   `references/METHODOLOGY.md` if you changed the JSON contract, a formula or a
   threshold.
5. **Run `make skill_zip`** if the change will be uploaded as a skill.

## 4. How to add a new flag

A flag (`Flag` enum) marks a data-quality problem for one language, such as
`LOW_VOLUME` or `SPIKE_DRIVEN`.

1. Add the member to `Flag` in `scripts/wiki_interest/enums.py`. Also add the same name in
   lower case to `Why` in the same file.

   > **Caution:** `analysis/ranking.py` converts each flag to `Why(flag.lower())`. A flag
   > without a `Why` member stops every ranking with a `ValueError`.

2. Add its text, in Ukrainian and in English, to `FLAG_TEXT` and `FLAG_SHORT` in
   `scripts/wiki_interest/text.py`. Add the Ukrainian ranking reason to `WHY_UK`.
3. Add the detection rule to `analyze_series()` in
   `scripts/wiki_interest/analysis/metrics.py`. Read the threshold from
   `config.Thresholds`, or add a new field there.
4. Add a test in `tests/test_metrics.py`: build a synthetic series that must trigger the
   flag, and one that must not.
5. Document the flag in `SKILL.md`, section 3 ("Flags, and what to tell the user"), and
   in `references/METHODOLOGY.md`, in the flags table.
6. If the flag can appear in an eval scenario's expected mentions, update
   `evals/scenarios.json`.

## 5. How to add a new UI string

1. Add the string to both `Lang.UK` and `Lang.EN` in the matching dictionary in
   `scripts/wiki_interest/text.py` (`VERDICT`, `CONFIDENCE`, `FLAG_TEXT`, `FLAG_SHORT`,
   `REASON_TEXT`, `WHY_UK`, `DISCLAIMER` or `PDF_TEXT`).
2. Read the string from `text.py` in the code. Do not build UI text inline.
3. Add or update a test that reads the string in `tests/test_metrics.py` or
   `tests/test_cli.py`, if the string appears in `summary_text` or the PDF text.

## 6. How to add a new language alias

1. Open `scripts/wiki_interest/data/languages.py`.
2. Add the language code and its alias names to `_LANG_NAMES`. Give at least an English
   and a Ukrainian name, for example `"sk": ["slovak", "словацька"]`.
3. If the Wikidata site id does not follow the `<code>wiki` pattern (a hyphen becomes an
   underscore, or a legacy id), add an entry to `_SITE_OVERRIDES`.
4. Add a case to the parametrized tests `test_lang_aliases` and, if the site id needs an
   override, `test_wikidata_site_ids` in `tests/test_metrics.py`.

## 7. How to add a new CLI option

1. Add the `argparse` argument to the `analyze` or `report` subparser in
   `make_parser()`, in `scripts/wiki_interest/cli.py`.
2. Read it in `build_request()` (for `analyze`) and validate it there, with a
   `UsageError` and a concrete `fix` for bad input.
3. Add the field to `AnalyzeRequest` (or the matching model) in
   `scripts/wiki_interest/models.py`.
4. Use the field in `wiki_interest/pipeline.py`, or deeper in `analysis/` or `report/`.
5. Update `SKILL.md`, section 1 (the arguments table) and its examples.
6. Update `references/METHODOLOGY.md` if the option changes a formula.
7. Add tests in `tests/test_cli.py` for the new option, including a bad-input case.

## 8. How to run evals

The evals run the skill through a real (or scripted) model, the way a skill host would.

```bash
uv sync
export OPENROUTER_API_KEY=...
make eval                                                      # free model, offline data
make eval MODEL=anthropic/claude-haiku-4.5 EVAL_ARGS="--repeats 2"   # live Wikimedia data
```

`make eval` runs `uv run python evals/run_eval.py`, with `MODEL` defaulting to
`nvidia/nemotron-3-super-120b-a12b:free` and `EVAL_ARGS` defaulting to `--fake-api`.
Traces are saved to `evals/traces/`.

The eval harness itself has offline unit tests, `tests/test_eval_harness.py`. They run
as part of `make test` and need no API key: a scripted "model" plays the role of the LLM.

## 9. Model and agent policy (from `AGENTS.md`, section 9)

| Task | Model |
|---|---|
| Design, refactors, reviews, final checks | Opus 5.5 (default) |
| Research, first drafts of docs, mechanical edits over many files | Sonnet 5 |

Verify every Sonnet 5 result with Opus 5.5 before you report the work as done. Subagents
and workflows are permitted. Give each one a complete brief: the goal, the files, the
relevant rules from `AGENTS.md`, and the expected output.

## 10. Related documents

| Document | Content |
|---|---|
| `docs/001-architecture.md` | Components, data flow, contracts, invariants. |
| `docs/002-installation-guide.md` | Requirements, environment selection, environment variables. |
| `docs/004-install-in-claude.md` | Install and use the skill in Claude Code and claude.ai. |
| `docs/005-install-in-codex.md` | Install and use the skill in OpenAI Codex. |
| `docs/006-cli-reference.md` | Every `wi analyze` and `wi report` option, and the JSON output fields. |
| `docs/007-logging-and-diagnostics.md` | stderr logging modes and the rich dashboard. |
| `docs/008-testing-and-evals.md` | Test layout, the synthetic API, coverage, CI. |
| `docs/009-verification-log-and-roadmap.md` | How the code was verified, current limitations, planned work. |
