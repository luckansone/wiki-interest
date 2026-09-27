# Logging and diagnostics

`wiki_interest/log.py` sends every log line to stderr, through loguru and rich. stdout
never carries a log line: it carries only the one JSON result. All examples below use
the offline demo (`WI_FAKE_API=1`), so no network access is needed to reproduce them.

## 1. Log modes

Set the mode with the `--log` flag (before the subcommand) or the `WI_LOG` environment
variable. `--log` wins if both are set.

| Mode | When to use it | Behavior |
|---|---|---|
| `auto` (default) | Always safe to leave as is. | `rich` when stderr is a terminal (a human is watching); `quiet` when stderr is piped (an agent's tool call). |
| `rich` | Watching a run yourself. | Boxed log lines, a fetch-progress meter, and a final dashboard. |
| `plain` | CI logs, log files, bug reports. | One timestamped line per event, no color. |
| `quiet` | The default an agent already gets through `auto`. | Warnings and errors only, one short line each. |

`WI_LOG_LEVEL=DEBUG` (default `INFO`) also logs every cache hit and every HTTP request,
in the `rich` and `plain` modes. The `quiet` mode always shows only warnings and errors.

## 2. The rich view

### Header

Each command prints a rule with its name and version when it starts:

```text
┤ wiki-interest 0.3.0 · analyze ├ ────────────────────────────────────────────────────────────────────────────
```

### Boxed log lines

Each line has four fields: time (with milliseconds), level, scope and message.

```text
│ 18:22:18.925 │ INFO    │ fetch    │ 'English language' → Q_FAKE_EN, articles in 3/3 editions
│ 18:22:18.925 │ INFO    │ fetch    │ 6 pageview series for 3 editions, 2024-09 – 2026-08
│ 18:22:18.967 │ INFO    │ fetch    │ done in 0.04 s
```

`scope` names the pipeline stage or module that logged the line (`fetch`, `analyze`,
`render`, `cli`, `http`, `pipeline`, `report`).

### Fetch progress meter

While pageviews and Wikidata requests are in flight, `rich` mode shows a bar with a
count and an elapsed time, for example `fetch  [██████········] 4/9  0:00:02`. It
disappears once the stage finishes; a fast offline run may finish before you see it.

### Final dashboard

A boxed panel prints after every run, in `rich` mode:

```text
╭─ ┤ wiki-interest ├ ────────────────────────────────────────────────────────────────────────────────────────╮
│ net  synthetic data (WI_FAKE_API=1): no requests, not real pageviews                                       │
│ time fetch 0.04s  analyze 0.01s  render 0.29s                                                              │
│                                                                                                            │
│  lang   yoy adj.   −50%      0      +50%   share of attention, 24 mo   verdict     conf.    flags          │
│  ────────────────────────────────────────────────────────────────────────────────────────────────────────  │
│  uk          -8%   ········■■┊··········   ▇▄▄█▅▆▆▆▄▁▄▆▃▅▆▄▁▂▁▂▃▁▃▃    declining   medium   PROJECT_SHIFT  │
│  pl         +28%   ··········┊■■■■■■····   ▁▁▂▁▂▂▂▄▃▄▄▃▄▄▅▄▆▃▆▅▆▇█▇    growing     high     —              │
│  vi         +33%   ··········┊■■■■■■■···   ▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁▁█▁▁▁    growing     medium   SPIKE_DRIVEN   │
│                                                                                                            │
│ out                                                                                                        │
│ wi_output/                                                                                                 │
│      run.json  ·  series.csv  ·  chart.png                                                                │
╰─────────────────────────────────────────────────────────────────────────── ┤ run 20260927-182218-f76b05 ├ ─╯
```

Captured with:

```bash
COLUMNS=110 WI_FAKE_API=1 bash scripts/wi --log rich analyze --topic "English language" --langs uk,pl,vi --no-pdf
```

The dashboard rows, top to bottom:

- **net**: request count, cache hit rate, retry count; or a note that the run used
  synthetic data.
- **time**: seconds spent in each pipeline stage.
- **the language table**: one row per requested language.
  - **yoy adj.**: `yoy_norm`, the traffic-adjusted year-over-year change.
  - **the meter**: a diverging bar from −50% to +50%, red for decline and green for
    growth. The column header shows this fixed range; it does not change with the data.
  - **share of attention**: a sparkline of the traffic-adjusted series over the last 24
    months. The label says "24 mo" even when `--months` is a different value; it names
    the sparkline width, not the analysis window.
  - **verdict**, **conf.**, **flags**: as in the stdout JSON.
- **out**: the output directory, then the files actually written.

## 3. Why a piped run stays quiet

An agent reads a tool's stdout and its stderr. `auto` mode checks whether stderr is a
terminal; a tool call pipes it, so `auto` resolves to `quiet`. A successful run then adds
nothing to the agent's context beyond the one JSON object on stdout. Only a warning or an
error appears on stderr, as one short line:

```text
wi: warning: HTTP 429 from www.wikidata.org, retry 2/5 in 15 s
```

This is `AGENTS.md`, section 5, rule 2: keep stderr quiet when it is piped.

## 4. `plain` mode

`plain` mode timestamps each line without color, one per event, suited to CI logs and
log files:

```text
18:22:18 INFO    fetch    'English language' → Q_FAKE_EN, articles in 3/3 editions
18:22:18 INFO    fetch    done in 0.04 s
18:22:18 INFO    analyze  done in 0.01 s
18:22:19 INFO    render   done in 0.29 s
```

## 5. How to report a bug

1. Reproduce the problem with full detail on stderr:
   ```bash
   WI_LOG=plain WI_LOG_LEVEL=DEBUG bash scripts/wi analyze --topic "<topic>" --langs <langs> 2> wi-debug.log
   ```
2. Attach `wi-debug.log` and the stdout JSON to the bug report.
3. If the CLI printed `{"error": "internal error: ...", ...}`, the `plain` log has the
   full traceback. Attach it.
