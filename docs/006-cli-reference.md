# CLI reference

The CLI is `scripts/wiki_interest/cli.py`, run through `bash scripts/wi` or
`python scripts/wi.py`. stdout always carries exactly one JSON object. Every log line
goes to stderr; see `docs/007-logging-and-diagnostics.md`.

```bash
bash scripts/wi [--log auto|rich|plain|quiet] analyze --topic "<Title>" --langs <codes> [options]
bash scripts/wi [--log auto|rich|plain|quiet] report --run-id <run_id> [options]
```

`--log` is a global option. Put it before the subcommand (`analyze` or `report`), not
after it.

## 1. `wi analyze`

| Option | Required | Default | Meaning |
|---|---|---|---|
| `--topic` | yes | — | English Wikipedia article title, or a Wikidata QID (for example `Q12345`). Repeat `--topic` to sum several articles into one topic. |
| `--langs` | yes | — | Comma-separated Wikipedia language codes, for example `uk,pl,cs`. A language name (`Polish`) or an alias also works. At most 8. |
| `--months` | no | `24` | Complete calendar months to analyze. Must be 12–120. |
| `--pdf` / `--no-pdf` | no | `--pdf` (on) | Write `report.pdf`. Use `--no-pdf` to skip it and get only the chart PNG. |
| `--question` | no | none | The question text, used as the PDF title. |
| `--weights` | no | `growth=0.5,level=0.3,confidence=0.2` | Ranking weights. Format: `growth=<n>,level=<n>,confidence=<n>`, each `>= 0`. |
| `--source-site` | no | `enwiki` | The language edition where `--topic` titles live (a Wikidata site id). Use `--source-site ukwiki` to pass a Ukrainian title, for example. |
| `--out-lang` | no | `uk` | Language of `summary_text` and of the whole PDF: `uk` or `en`. |

## 2. `wi report`

Re-renders the PDF of a saved run, optionally with your own conclusion, title or
language.

| Option | Required | Default | Meaning |
|---|---|---|---|
| `--run-id` | yes | — | The `run_id` printed by a previous `analyze` call. |
| `--conclusion` | no | none | Replaces the automatic conclusion. Keep it to 2–4 sentences, using only numbers from the `analyze` output. |
| `--question` | no | none | Replaces the PDF title. |
| `--out-lang` | no | the run's own `out_lang` | `uk` or `en`. Leave it out to keep the language the run was created with. |

## 3. stdout JSON fields

### `wi analyze` success: `AnalyzeOutput`

| Field | Meaning |
|---|---|
| `run_id` | Identifier of this run. Pass it to `wi report --run-id`. |
| `period` | `[first month, last month]` of the analyzed window. |
| `topics` | Each `--topic`, resolved to `"<label> (<Wikidata QID>)"`. |
| `results.<lang>` | Per-language result. See the table below. |
| `ranking` | Languages ordered by score. Each row has `lang`, `position` and `why` (the reasons). |
| `summary_text` | A ready, correct paragraph with the key numbers. Base your answer on it. |
| `files` | Paths to the output files. See below. |
| `warnings` | Present only if something needs the agent's attention, for example no language has data. |

### `results.<lang>`: `CompactResult`

| Field | Meaning |
|---|---|
| `verdict` | `growing`, `declining` or `stable_or_unclear`. |
| `confidence` | `high`, `medium` or `low`: how much to trust the verdict. |
| `yoy_norm` | Last 12 complete months vs. the 12 months before, adjusted for the whole edition's traffic. The main number. |
| `yoy_norm_ci90` | `[low, high]`, the 90% confidence interval of `yoy_norm`. |
| `yoy_norm_prev_year` | The same comparison, one year earlier, if enough history exists. |
| `yoy_raw` | The same 12-vs-12 comparison, without the traffic adjustment. |
| `median_views_month` | Audience size: median monthly views over the comparison window. |
| `views_per_million` | Topic views per million views of the whole language edition. |
| `trend_pct_year` | Long-run trend over the whole `--months` window, in percent per year. |
| `trend_p_value` | Significance of `trend_pct_year` (Mann–Kendall test). |
| `flags` | Data-quality problems. See the table in section 5. |
| `status` | `no_data` if the language has no article on the topic. Only `status` and `flags` (`["MISSING_ARTICLE"]`) are then present; every other field is absent. |

A field is present only when it has a value: the CLI drops every `null` field before
printing the JSON.

### `ranking[]`: `OutputRankRow`

| Field | Meaning |
|---|---|
| `lang` | The language code. |
| `position` | 1 is the top-ranked language. |
| `why` | Reasons for this position, for example `fastest_growth`, `growing`, `low_volume`. |

### `files`: `Files`

| Field | Meaning |
|---|---|
| `run_json` | Path to `run.json` (the full `RunRecord`, see `docs/001-architecture.md`). |
| `series_csv` | Path to `series.csv` (raw monthly views per language). |
| `chart_png` | Path to the chart image. Absent if no language has data. |
| `pdf` | Path to `report.pdf`. Absent if `--no-pdf` was given, or if no language has data. |
| `pdf_shared` | Path to a copy of the PDF in the folder that the chat shows to the user (`WI_SHARE_DIR`, on claude.ai `/mnt/user-data/outputs/`). The file name is `wiki-interest-<topic>-<run_id>.pdf`. Present only in a chat sandbox or when `WI_SHARE_DIR` is set. |

### `wi report` success: `ReportOutput`

| Field | Meaning |
|---|---|
| `run_id` | The run that was re-rendered. |
| `files.pdf` | Path to the re-rendered PDF. |
| `files.pdf_shared` | The shared copy, replaced with the re-rendered PDF (only in a chat sandbox). |

### Any command's failure: `ErrorOutput`

| Field | Meaning |
|---|---|
| `error` | What went wrong. |
| `fix` | A concrete next command or setting. Run it, or apply it, then retry. |

## 4. Output files

Every `analyze` run writes to `<WI_OUT>/<run_id>/` (default `wi_output/<run_id>/`):

| File | Written when |
|---|---|
| `run.json` | Always. |
| `series.csv` | Always. |
| `chart.png` | At least one requested language has an article on the topic. |
| `report.pdf` | The above, and `--pdf` was not turned off (it is on by default). |

`wi report --run-id <id>` overwrites `report.pdf` and `run.json` in the same directory.

## 5. Flags

| Flag | Meaning |
|---|---|
| `SHORT_HISTORY` | Fewer than 24 months of data: seasonality is not controlled. |
| `LOW_VOLUME` | Median views/month below 300: percentages are noisy. |
| `PROJECT_SHIFT` | Raw and traffic-adjusted growth disagree in sign: the whole edition's traffic shifted. |
| `SPIKE_DRIVEN` | The growth comes mostly from a single month. |
| `MISSING_ARTICLE` | Some topic articles do not exist in this language. |
| `TREND_CONFLICT` | The last year moves against a significant long-run trend (a rebound or a reversal). |

## 6. Exit codes

| Code | Meaning |
|---|---|
| `0` | Success. The JSON on stdout has no `error` field. |
| `1` | Failure. The JSON on stdout is `{"error": ..., "fix": ...}`. This covers bad arguments, a Wikidata or Pageviews failure, and an unexpected internal error. |

## 7. Error examples

| Situation | `error` | `fix` |
|---|---|---|
| `--topic` does not exist on the source wiki | `topic '<title>' not found in Wikidata via enwiki` | Pass the exact English Wikipedia article title (as in its URL, for example `Intermittent_fasting`), or a Wikidata QID like `Q12345`; or set `--source-site ukwiki` and use the Ukrainian title. |
| `--langs` has an unrecognized code | `unknown language '<code>'` | Use Wikipedia language codes, for example `--langs uk,pl,cs,de,tr`. |
| More than 8 languages given | `9 languages given; the MVP supports up to 8 per run` (the count varies) | Split into several runs of 8 languages or fewer, or keep the 8 most relevant. |
| `--months` outside 12–120 | `--months must be between 12 and 120` | Use `--months 24` (default) or `--months 36`. |
| `--weights` malformed | for example `weight 'growth' must be a number, got 'x'` | `--weights "growth=0.5,level=0.3,confidence=0.2"`. |
| A required option is missing, or unknown | `bad arguments: ...` | `bash scripts/wi analyze --topic "<English article title>" --langs uk,pl --months 24`. |
| `WI_OFFLINE=1` and nothing cached yet | `offline mode and no cache for <url>` | Unset `WI_OFFLINE`, or run once with network access. |
| A request keeps failing after 5 attempts | `request failed after retries: <url> (<reason>)` | Retry in a minute; if it persists, check network access to `wikimedia.org`. |
| `wi report --run-id` for a run that does not exist | `run '<id>' not found in <out_dir>` | Use the `run_id` printed by the `analyze` command. |
| An unexpected internal error | `internal error: <ExceptionType>: <message>` | Re-run once; if it repeats, run with `WI_LOG=plain WI_LOG_LEVEL=DEBUG` and report the log. |
