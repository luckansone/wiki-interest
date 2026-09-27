# Verification log and roadmap

## 1. Verification log

### Version 0.3.0

- **The PDF shows in the chat.** In a chat sandbox, `analyze` copies the PDF to the outputs
  folder (`files.pdf_shared`). `SKILL.md` tells the agent to show it with its file tool. Before
  this change, claude.ai showed only a path that the user could not open. The evals now fail
  if the agent does not call `present_files`.

- **Package refactor.** The code moved from a flat `scripts/` layout into the
  `scripts/wiki_interest/` package: Pydantic models for every JSON shape, `StrEnum`
  types for verdicts, flags, confidence and reasons, and separate `data/`, `analysis/`
  and `report/` subpackages.
- **New logging.** loguru and rich add logging to stderr. Logging has four modes
  (`auto`, `rich`, `plain`, `quiet`) and a final dashboard in `rich` mode. See
  `docs/007-logging-and-diagnostics.md`.
- **Output checked byte for byte.** For 7 golden scenarios (4 analyses and 3 errors), the
  stdout JSON of 0.3.0 is byte-identical to 0.2. The PDF text of the 4 analyses is also
  identical. `run.json` has one new field, `conclusion`, with the default value `null`.
- **Cache compatibility.** A live run of 0.3.0 used the disk cache of 0.2 (4 of 4 cache
  hits, no new requests). The cache key format did not change.
- **Both launcher paths tested from a clean zip.** `scripts/wi` was run from a freshly
  built `dist/wiki-interest.zip`, once through `uv` and once through the pip-only
  fallback (a bare Python 3.12 without packages), in a copy without `.venv`.

### Earlier verification

- **Statistics tested against a known ground truth.** Synthetic series with a set
  trend, seasonality, a spike and an edition-wide shift. The tests check the correct
  verdict and flags, invariance to scale, determinism, and that changing the ranking
  weights actually changes the ranking.
- **End-to-end tests on the three target questions**, through the CLI, with the
  synthetic API in the real JSON shape. The tests check the correct verdicts and flags
  (`PROJECT_SHIFT`, `SPIKE_DRIVEN`, `MISSING_ARTICLE`), that page 1 is the one-page
  summary and the appendix flows onto extra pages without dropping a row, and that the
  PDF text can be extracted (the fonts are embedded).
- **Visual review** of rendered PDFs for 2 and for 8 languages. Label collisions and
  overflow were fixed as a result.
- **Reproducibility.** Dependencies are locked in `uv.lock`. The test suite passes on
  Python 3.11, 3.12, 3.13 and 3.14 (the CI matrix in `.github/workflows/test.yml`). The
  launcher was tested from a clean checkout: through `uv`, through the pip fallback, and
  with neither available (it then prints the JSON error with the `uv` install command).
- **Spec compliance.** `agentskills validate` reported "Valid skill".
- **The eval harness is tested itself.** A scripted model with an honest answer passes
  the checks; one with a hallucinated number is caught; a dangerous command is blocked.
  See `docs/008-testing-and-evals.md`, section 5.
- **Live API run (2026-09-27).** The three target questions were run against the real
  Wikimedia and Wikidata APIs. The resulting series were cross-checked against direct
  Pageviews API calls (Czech intermittent fasting, Ukrainian astronomy articles): the
  year-over-year change and the medians matched exactly. This run also found that
  Wikidata's anonymous rate limit (about 2 requests, then HTTP 429 with a
  `Retry-After` of about 15 seconds) broke every cold run with 3 or more topics; the
  client now reads and honors `Retry-After`.
- **End-to-end run on Haiku 4.5.** Each scenario's agent saw only the skill's name and
  description, read `SKILL.md` itself, and ran the CLI. Every run used the correct
  single command and only numbers from the tool output. The first round found answer
  wording problems: countries named instead of language editions, a percentage
  reported over the wrong window ("−39% over 36 months" instead of the 12-vs-12
  comparison), "weak growth" used for a `stable_or_unclear` verdict, and a missing PDF
  path. These findings led to the wording rules now in `SKILL.md`, section 4, and to
  the explicit comparison window in `summary_text`.

**Still to do:** an `evals/run_eval.py` run on OpenRouter's free models, which needs an
API key.

## 2. Limitations of the MVP

| Limitation | Detail |
|---|---|
| Not willingness to pay | Pageviews measure interest, not purchase intent. |
| Not a country | A language edition is not a country. English is read everywhere; Portuguese is read mostly, but not only, in Brazil. |
| No redirects | Views to a redirect page are not added to the target article's count. |
| Unfiltered bots | Some unrecognized bots can remain inside the `agent=user` traffic that this tool counts. |
| Language limit | At most 8 languages per run. |
| Relative ranking | The ranking orders the chosen set of languages against each other, not against every Wikipedia language edition. |

## 3. Next iterations

1. **Data quality**: add redirects, use daily data for better bot detection, define
   topic baskets as reusable assets, and add a geographic breakdown for the top
   articles.
2. **Dialogue**: a `--from-run` option with deltas ("add Slovak"), a "what changed since
   the last run" block, and a `wi check --claim` command so the agent can check its own
   conclusions.
3. **Statistics**: STL decomposition, changepoint detection, a forecast with confidence
   intervals, and partial pooling for small language editions.
4. **Scale**: monthly `pageview_complete` dumps, loaded into Parquet and then
   DuckDB or PySpark (a Trino table), to scan hundreds of topics across dozens of
   languages. The same CLI would run behind a `--backend dumps` option.
5. **Business calibration**: backtest the Wikipedia signal against the product's own
   installs or revenue by locale (using aggregates only), and weight languages by
   market size.

Each iteration starts with new eval scenarios built from real requests, and ends with a
regression run on a cheap model.
