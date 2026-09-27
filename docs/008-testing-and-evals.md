# Testing and evals

## 1. Test layout

The suite is offline. It uses synthetic Wikimedia and Wikidata responses
(`wiki_interest/data/fake.py`), so it needs no network access.

| File | Covers |
|---|---|
| `tests/test_cli.py` | End-to-end CLI runs for the three target questions: JSON shape, exit codes, PDF page count and text, error messages, log modes. |
| `tests/test_data.py` | The HTTP layer: `Retry-After` handling, retry limits, a corrupt cache entry, the stable cache-key format, offline mode, and that requests do not depend on `--months` or the language list (so a follow-up run reuses the cache). |
| `tests/test_metrics.py` | Statistics on synthetic series with a known ground truth: verdicts, flags, scale invariance, determinism, ranking and its `why`, language aliases, edition names. |
| `tests/test_models.py` | Pydantic models: `Weights` parsing, `Settings.from_env()`, and that an older `run.json` (without newer fields) still loads into the right result types. |
| `tests/test_log.py` | Logging: `auto` mode is quiet when stderr is piped, the quiet sink shows only warnings, the diverging meter and the sparkline render correctly, the rich dashboard renders every expected value. |
| `tests/test_eval_harness.py` | The eval harness itself (section 4): a scripted "model" drives the real CLI, and the automatic checks catch a hallucinated number and block a disallowed command. |

Run the suite:

```bash
make test              # pytest, offline
make test_cov          # pytest with coverage
```

## 2. The offline synthetic API

`wiki_interest/data/fake.py` returns Wikidata and Pageviews responses in the real JSON
shape, built from fixed formulas plus seeded noise. It exists for tests, the demo mode
and the evals, not to say anything about real interest; a report built from it always
carries a red demo banner.

It knows a fixed set of topics (`TOPICS`), each with a Wikidata QID and a title per
language, and it encodes specific scenarios for the test suite and the evals to check
against:

| Language | Scenario |
|---|---|
| `pl` | Steady growth (`TOPIC_GROWTH["pl"] = 0.30`/year). |
| `cs` | Flat (`0.0`/year): the tests expect `stable_or_unclear`. |
| `uk` | The whole `uk.wikipedia` edition grows faster than the topic (`PROJECT_GROWTH["uk"] = 0.20`), so raw views rise while the traffic-adjusted share falls: `PROJECT_SHIFT`. |
| `vi` | One viral month in the last year: `SPIKE_DRIVEN`. |
| `id` | Missing the "International English Language Testing System" article: `MISSING_ARTICLE`. |
| `pt` | Declining (`TOPIC_GROWTH["pt"] = -0.10`). |
| `tr` | No article on "Intermittent fasting": `status: no_data`. |

Turn it on with `WI_FAKE_API=1`. It bypasses the disk cache and the network entirely.

## 3. Coverage

`.coveragerc` sets branch coverage over `scripts` and `evals` (`tests/*` excluded), with
a minimum of 85%:

```ini
[report]
fail_under = 85
```

`make test_cov` runs `pytest --cov --cov-report=term-missing` and fails if coverage
drops below that threshold.

## 4. Continuous integration

`.github/workflows/test.yml` defines three jobs, all on `ubuntu-latest`:

| Job | Runs | Checks |
|---|---|---|
| `lint` | Once. | `uv lock --check` (the lockfile matches `pyproject.toml`), then `ruff format --check` and `ruff check`. |
| `test-python` | On a matrix of Python 3.11, 3.12, 3.13 and 3.14. | `pytest --cov --cov-report=xml --junitxml=test-results.xml`, with reports uploaded as build artifacts. |
| `skill-launcher` | Once, from a clean checkout. | `bash scripts/wi analyze ...` end to end, with `WI_FAKE_API=1`, checking the JSON has no `error` field and that `files.pdf` is present. |

## 5. How the evals work

`evals/run_eval.py` drives the skill through a real language model (or, in
`tests/test_eval_harness.py`, a scripted stand-in), the way a real skill host would:

1. The model sees only the skill's `name` and `description` from `SKILL.md`'s
   frontmatter, exactly as a skill host would show it.
2. It must decide to read `SKILL.md` itself, using a `read_file` tool.
3. It can call `present_files`, like the tool of claude.ai that shows a file card. The
   harness sets `WI_SHARE_DIR`, so the output has `files.pdf_shared` as in the claude.ai sandbox.
4. It runs the CLI with a `bash` tool, restricted to an allowlist: `bash scripts/wi ...`,
   `scripts/wi ...`, `python3 scripts/wi.py ...`, or a handful of read-only file commands
   (`cat`, `ls`, `head`, `pwd`) inside the skill directory. Shell syntax such as `;`,
   `|`, `` ` ``, `<`, `>` or `$` is rejected outright, so the model cannot chain or
   redirect commands.
5. It answers in the user's language, based on the tool output.

### Automatic checks (`run_eval.check`)

| Check | Fails when |
|---|---|
| Languages | A language from `expect.langs` is missing from the `--langs` argument actually used. |
| `--months` | `expect.months` is set and the command used a different value. |
| PDF shown | `expect.pdf` is true, and the model did not call `present_files` with `files.pdf_shared` or `files.pdf` (or it used `--no-pdf`). A path in the answer text is not enough. |
| `--question` | `expect.question` is true, and the command did not pass `--question`. |
| Tool-call budget | More tool calls than `expect.max_tool_calls` (default 6). |
| Required mentions | None of the words in an `expect.mention_any` group appear in the answer. |
| Hallucinated numbers | A percentage in the answer does not match any percentage (or `yoy_*`/`trend_pct_year` value, rounded to 0–2 decimals) printed by the tool. |
| Clarifying question | `expect.clarify` is true, and the model ran `analyze` instead of asking which languages to use, or did not ask a question at all. |

`evals/scenarios.json` defines the four scenarios: the three target questions plus one
that must trigger a clarifying question (no languages given).

### Run the evals

```bash
uv sync
export OPENROUTER_API_KEY=...
make eval                                                      # free model, offline (synthetic) data
make eval MODEL=anthropic/claude-haiku-4.5 EVAL_ARGS="--repeats 2"   # live Wikimedia data
```

`make eval` runs `uv run python evals/run_eval.py --model $(MODEL) $(EVAL_ARGS)`, with
`MODEL` defaulting to `nvidia/nemotron-3-super-120b-a12b:free` and `EVAL_ARGS` defaulting
to `--fake-api`. Traces (the full message history, tool calls and check results) are
saved to `evals/traces/`.

## 6. Before you finish a change (from `AGENTS.md`, section 10)

1. Run `make lint` and `make test`. All tests must pass.
2. For a change in output: run `make demo` and open the PDF.
3. For a change in the JSON contract or in `SKILL.md`: run `make eval`, if an API key is
   available.
4. Update the matching file in `docs/`, and `SKILL.md` and `references/METHODOLOGY.md`
   if the change touches them.
5. Run `make skill_zip` if the skill will be uploaded.
