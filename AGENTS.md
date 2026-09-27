# AGENTS.md — wiki-interest

This file gives coding agents (Claude Code, Codex and others) the shared context for development sessions on this repository. Read it before you change code or docs.

## 1. What this project is

- `wiki-interest` is an [Agent Skill](https://agentskills.io/specification). An agent reads `SKILL.md`, runs one command and relays the result.
- The skill measures how interest in a topic changes across Wikipedia language editions. It uses Wikimedia pageview statistics and Wikidata sitelinks.
- The command writes one JSON object to stdout, plus `run.json`, `series.csv`, `chart.png` and `report.pdf` to `wi_output/<run_id>/`.
- Deterministic code calculates all numbers and verdicts. The agent never calculates numbers.

## 2. Repository map

| Path | Content |
|---|---|
| `SKILL.md` | Instructions for the agent that uses the skill (runtime contract). |
| `references/METHODOLOGY.md` | Formulas, thresholds and limitations. The agent reads it on request. |
| `scripts/wi` | Bash launcher. It selects uv, an existing Python, or a pip venv. |
| `scripts/wi.py` | Entry point. It adds `scripts/` to `sys.path` and calls `wiki_interest.cli.main`. |
| `scripts/wiki_interest/` | The Python package (see section 4). |
| `tests/` | pytest suite. It runs offline with synthetic Wikimedia responses. |
| `evals/` | Agent-loop evaluation on cheap models (`run_eval.py`, `scenarios.json`). |
| `docs/` | Developer and user documentation, numbered (`001-architecture.md`, ...). |
| `pyproject.toml`, `uv.lock` | The only source of dependencies and the supported Python range. |
| `Makefile` | Common tasks: `make test`, `make lint`, `make demo`, `make skill_zip`. |

## 3. Commands

```bash
make uv_install_deps     # install runtime and dev dependencies with uv
make lint                # ruff check + ruff format --check
make format              # ruff fix + format
make test                # pytest, offline
make test_cov            # pytest with coverage (minimum 85%)
make demo                # offline demo run, synthetic data, PDF with a red DEMO banner
make skill_zip           # build dist/wiki-interest.zip for upload
```

Run one analysis:

```bash
WI_FAKE_API=1 bash scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs --months 24
```

Use `WI_FAKE_API=1` for all local experiments. It sends no requests to Wikimedia.

## 4. Package layout

| Module | Responsibility |
|---|---|
| `wiki_interest/enums.py` | `StrEnum` types: `Verdict`, `Confidence`, `Flag`, `Reason`, `Why`, `Lang`, `LogMode`. |
| `wiki_interest/models.py` | Pydantic models: request, per-language results, `RunRecord` (run.json), stdout output. |
| `wiki_interest/config.py` | `Settings` from environment variables. `Thresholds`. API URLs and limits. |
| `wiki_interest/errors.py` | Errors with a `fix` hint. The CLI turns them into `{"error", "fix"}` JSON. |
| `wiki_interest/text.py` | All UI text in Ukrainian and English. |
| `wiki_interest/log.py` | loguru + rich logging to stderr, in a btop-like style. |
| `wiki_interest/data/` | `languages.py`, `http.py` (cache and retry), `wikimedia.py` (Wikidata, Pageviews), `fake.py` (synthetic API). |
| `wiki_interest/analysis/` | `stats.py`, `metrics.py` (verdict, confidence, flags), `ranking.py`, `summary.py`. |
| `wiki_interest/report/` | `charts.py`, `summary_page.py` (PDF page 1), `appendix.py` (flowing pages), `pdf.py`. |
| `wiki_interest/pipeline.py` | One run from end to end: fetch, analyze, save, render. Also re-renders a saved PDF. |
| `wiki_interest/cli.py` | argparse. It validates input and prints exactly one JSON object. |

## 5. Rules that you must not break

1. **stdout is one JSON object.** Do not print to stdout. Send all logs to stderr through `loguru.logger`.
2. **Keep stderr quiet when it is piped.** Agents read stderr. In `auto` mode, a piped run shows only warnings that are not in the JSON (for example, an HTTP retry).
3. **Keep the JSON contract stable.** `SKILL.md` documents the field names of the stdout JSON. If you change a field, update `SKILL.md`, the tests and the evals in the same change.
4. **Keep old `run.json` files readable.** `wi report --run-id` must load run files from earlier versions. Add new fields with a default value.
5. **Do not change the cache key.** `data/http.py::cache_path` hashes the URL and the parameters. A new format discards the cache of every user.
6. **Do not change numbers without a reason.** The statistics are deterministic (fixed seed). If a change affects a number, explain why in the commit and update the tests.
7. **Put UI text in `text.py`.** Add each string in Ukrainian and in English.
8. **Use the enums and models.** Do not use bare strings for verdicts, flags or confidence. Do not use plain dicts for data that crosses modules.
9. **Update `SKILL_FILES` in the `Makefile`** when you add a top-level file that the skill needs at runtime.

## 6. Code style

- Python 3.11 to 3.14. Line length 120. Ruff rules `E, F, W, I, D`.
- Use `from __future__ import annotations` in each module.
- Get a logger with a scope: `log = logger.bind(scope="fetch")`. Use `info` for stages, `debug` for single requests and `warning` only for problems that the JSON does not show.
- Wrap a pipeline stage in `wlog.stage("name")`. The stage time then shows in the dashboard.
- Import matplotlib code (`wiki_interest.report`) lazily, because it is slow to load.
- Write tests first for a bug fix. Use `WI_FAKE_API=1` or monkeypatch `http.get_json`. Tests must not use the network.

## 7. Documentation rules

- Save documentation as Markdown files in `docs/`. Use a three-digit number and a short name: `001-architecture.md`, `002-installation-guide.md`. Use the next free number for a new file.
- Keep `README.md` short. It links to the files in `docs/`.
- Use Mermaid diagrams for flows and structures.
- Write in **ASD-STE100 Simplified Technical English (STE)**. See section 8.
- Apply the **writing-clearly-and-concisely** skill: <https://github.com/softaworks/agent-toolkit/tree/main/skills/writing-clearly-and-concisely>. Install it with `npx skills add softaworks/agent-toolkit` or copy the skill folder to `~/.claude/skills/` (Claude Code) or `~/.agents/skills/` (Codex).
- Apply these rules to all human-readable text: docs, commit messages, error messages, `fix` hints, log lines and UI strings.

## 8. STE writing rules (summary of ASD-STE100)

1. Write procedures as numbered steps. Use the imperative: "Run the command.", not "The command should be run."
2. Write one instruction in each sentence. If two actions occur at the same time, you can write them in one sentence.
3. Keep procedural sentences to 20 words or fewer. Keep descriptive sentences to 25 words or fewer.
4. Use the active voice. Use the passive voice only when the actor is not known or not important.
5. Use simple verb tenses: present, simple past, simple future. Do not use "have been", "would have" and similar forms.
6. Use one word for one meaning. Use the same term for the same thing everywhere (for example, "language edition", not also "wiki" and "site").
7. Use short, common words. Write "use", not "utilize". Write "start", not "initiate".
8. Do not use "-ing" words as verbs in place of a clause. "When you run the test", not "When running the test".
9. Keep noun clusters to three words or fewer. Write "the cache of pageview responses", not "pageview response cache entry file".
10. Do not omit articles ("the", "a"), subjects or verbs to make text shorter.
11. Write a paragraph about one topic. Use six sentences or fewer.
12. Write a warning or a caution before the step that it applies to.
13. Do not use phrasal verbs when a single verb exists. Write "remove", not "take out".
14. Write numbers and units exactly as the tool prints them.

Write short, specific text. Do not use promotional words ("seamless", "powerful", "robust"). Do not use filler ("it is important to note that").

## 9. Models and agents for development work

- Use **Opus 5.5** by default: design, refactors, reviews and final checks.
- Use **Sonnet 5** for simple or token-heavy tasks: research, first drafts of docs, mechanical edits over many files.
- Verify every Sonnet result with **Opus 5.5** before you report the work as done.
- Subagents, agents and workflows are permitted. Give each subagent a complete brief: goal, files, rules from this file and the expected output.

## 10. Before you finish a change

1. Run `make lint` and `make test`. All tests must pass.
2. For a change in output: run `make demo` and open the PDF.
3. For a change in the JSON or in `SKILL.md`: run the evals (`make eval`) if an API key is available.
4. Update the related file in `docs/` and, if necessary, `SKILL.md` and `references/METHODOLOGY.md`.
5. Run `make skill_zip` if the user will upload the skill.
