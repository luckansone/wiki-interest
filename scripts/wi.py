#!/usr/bin/env python3
"""wiki-interest CLI.

  wi.py analyze --topic "Intermittent fasting" --langs pl,cs --months 24 [--no-pdf] [--out-lang en]
  wi.py report  --run-id <id> --conclusion "..."      # re-render PDF with the agent's own wording

Every analyze run writes a PDF report (one-page summary + appendix) unless --no-pdf is given.

stdout is always ONE compact JSON object (or {"error","fix"}); full data goes to files.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))

import pandas as pd  # noqa: E402

import metrics  # noqa: E402
import wiki_api  # noqa: E402


OUT_DIR = Path(os.environ.get("WI_OUT", "wi_output"))

if os.environ.get("WI_FAKE_API") == "1":
    # Offline demo/eval mode: synthetic responses in the real API format; reports get a banner.
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
    import fake_api  # noqa: E402

    wiki_api.http_get_json = fake_api.http_get_json
    os.environ["WI_SYNTHETIC"] = "1"


def _emit(obj: dict, code: int = 0):
    print(json.dumps(obj, ensure_ascii=False, separators=(",", ":")))
    sys.exit(code)


def _error(msg: str, fix: str):
    _emit({"error": msg, "fix": fix}, 1)


def _parse_langs(raw: str) -> list[str]:
    out = []
    for part in raw.replace(";", ",").split(","):
        if part.strip():
            code = wiki_api.normalize_lang(part)
            if code not in out:
                out.append(code)
    return out


def cmd_analyze(a) -> None:
    try:
        langs = _parse_langs(a.langs)
    except wiki_api.ApiError as e:
        _error(str(e), "use Wikipedia language codes, e.g. --langs uk,pl,cs,de,tr")
    if len(langs) > 8:
        _error(
            f"{len(langs)} languages given; the MVP supports up to 8 per run",
            "split into several runs of <= 8 languages, or keep the 8 most relevant",
        )
    if not 12 <= a.months <= 120:
        _error("--months must be between 12 and 120", "use --months 24 (default) or --months 36")
    try:
        weights = metrics.parse_weights(a.weights)
    except ValueError as e:
        _error(str(e), 'e.g. --weights "growth=0.5,level=0.3,confidence=0.2"')

    try:
        data = wiki_api.collect(a.topic, langs, a.months, a.source_site)
    except wiki_api.ApiError as e:
        if "not found in Wikidata" in str(e):
            _error(
                str(e),
                "pass the exact English Wikipedia article title (as in its URL, e.g. "
                "'Intermittent_fasting') or a Wikidata QID like Q12345; or set "
                "--source-site ukwiki and use the Ukrainian title",
            )
        _error(str(e), "retry in a minute; if it persists check network access to wikimedia.org")

    window = data["window"]
    results, series_vpm, articles = {}, {}, {}
    for l in langs:
        d = data["per_lang"][l]
        articles[l] = d["articles"]
        if d["topic_views"] is None:
            results[l] = {"status": "no_data", "missing_articles": d["missing"], "flags": ["MISSING_ARTICLE"]}
            continue
        results[l] = metrics.analyze_series(d["topic_views"], d["project_views"], d["missing"])
        proj = d["project_views"].replace(0, pd.NA).astype("float")
        series_vpm[l] = (d["topic_views"] / proj * 1e6).astype(float).ffill().bfill().fillna(0)

    ranking = metrics.rank(results, weights)
    summary = metrics.summary_text(results, ranking, a.out_lang)

    key = json.dumps([a.topic, langs, a.months, a.weights, data["fetched_on"]])
    run_id = dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + hashlib.sha1(key.encode()).hexdigest()[:6]
    run_dir = OUT_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    run = {
        "run_id": run_id,
        "question": a.question,
        "out_lang": a.out_lang,
        "langs": langs,
        "months": a.months,
        "period": [str(window[0]), str(window[-1])],
        "fetched_on": data["fetched_on"],
        "topics": [{"input": r["topic"], "label": r["label"], "qid": r["qid"]} for r in data["resolved"]],
        "articles": articles,
        "weights": weights,
        "results": results,
        "ranking": ranking,
        "summary_text": summary,
        "synthetic": os.environ.get("WI_SYNTHETIC") == "1",
        "command": " ".join(sys.argv),
    }
    raw = pd.DataFrame(
        {
            f"{l}_topic": data["per_lang"][l]["topic_views"]
            for l in langs
            if data["per_lang"][l]["topic_views"] is not None
        }
    )
    for l in langs:
        raw[f"{l}_project"] = data["per_lang"][l]["project_views"]
    raw.index = raw.index.astype(str)
    raw.to_csv(run_dir / "series.csv")
    (run_dir / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=1))

    files = {"run_json": str(run_dir / "run.json"), "series_csv": str(run_dir / "series.csv")}
    warnings = []
    h = 12 if a.months >= 24 else a.months // 2
    if not series_vpm:
        warnings.append(
            ("PDF and chart not created: " if a.pdf else "chart not created: ")
            + "none of the requested languages has an article on this topic. "
            "Re-run with a broader --topic (parent concept) or other --langs."
        )
    else:
        import report  # imported lazily: matplotlib is slow to load

        files["chart_png"] = str(run_dir / "chart.png")
        report.save_chart_png(files["chart_png"], series_vpm, {l: results[l] for l in series_vpm}, h, a.out_lang)
        if a.pdf:
            files["pdf"] = str(run_dir / "report.pdf")
            topic_views = {l: data["per_lang"][l]["topic_views"] for l in series_vpm}
            report.save_pdf(files["pdf"], run, series_vpm, h, topic_views)

    compact = {
        k: {
            kk: r.get(kk)
            for kk in (
                "verdict",
                "confidence",
                "yoy_norm",
                "yoy_norm_ci90",
                "yoy_norm_prev_year",
                "yoy_raw",
                "median_views_month",
                "views_per_million",
                "trend_pct_year",
                "trend_p_value",
                "flags",
                "status",
            )
            if r.get(kk) is not None
        }
        for k, r in results.items()
    }
    out = {
        "run_id": run_id,
        "period": run["period"],
        "topics": [f"{t['label']} ({t['qid']})" for t in run["topics"]],
        "results": compact,
        "ranking": [{k: v for k, v in r.items() if k != "score"} for r in ranking],
        "summary_text": summary,
        "files": files,
    }
    if warnings:
        out["warnings"] = warnings
    _emit(out)


def cmd_report(a) -> None:
    run_dir = OUT_DIR / a.run_id
    if not (run_dir / "run.json").exists():
        _error(f"run '{a.run_id}' not found in {OUT_DIR}", "use the run_id printed by the analyze command")
    run = json.loads((run_dir / "run.json").read_text())
    if a.conclusion:
        run["conclusion"] = a.conclusion
    if a.question:
        run["question"] = a.question
    if a.out_lang:
        run["out_lang"] = a.out_lang
    raw = pd.read_csv(run_dir / "series.csv", index_col=0)
    raw.index = pd.PeriodIndex(raw.index, freq="M")
    series_vpm, topic_views = {}, {}
    for l, r in run["results"].items():
        if r.get("status") != "no_data":
            proj = raw[f"{l}_project"].replace(0, pd.NA).astype(float)
            series_vpm[l] = (raw[f"{l}_topic"] / proj * 1e6).ffill().bfill().fillna(0)
            topic_views[l] = raw[f"{l}_topic"]
    import report

    h = 12 if run["months"] >= 24 else run["months"] // 2
    pdf = run_dir / "report.pdf"
    report.save_pdf(pdf, run, series_vpm, h, topic_views)
    (run_dir / "run.json").write_text(json.dumps(run, ensure_ascii=False, indent=1))
    _emit({"run_id": a.run_id, "files": {"pdf": str(pdf)}})


class _JsonArgParser(argparse.ArgumentParser):
    """Argument errors come back as JSON with a fix hint, like every other error."""

    def error(self, message):
        _error(
            f"bad arguments: {message}",
            'bash scripts/wi analyze --topic "<English article title>" --langs uk,pl --months 24',
        )


def main(argv=None):
    p = _JsonArgParser(prog="wi", description="Wikipedia interest analysis")
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=_JsonArgParser)

    an = sub.add_parser("analyze", help="trend of a topic across language editions")
    an.add_argument(
        "--topic",
        action="append",
        required=True,
        help="English Wikipedia article title or Wikidata QID; repeat to sum several articles",
    )
    an.add_argument("--langs", required=True, help="comma-separated, e.g. uk,pl,cs")
    an.add_argument("--months", type=int, default=24, help="complete months to analyze (12-120)")
    an.add_argument(
        "--pdf",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="write the PDF report: one-page summary + appendix (default: on; --no-pdf to skip)",
    )
    an.add_argument("--question", help="question text used as the report title")
    an.add_argument("--weights", help='ranking weights, e.g. "growth=0.5,level=0.3,confidence=0.2"')
    an.add_argument("--source-site", default="enwiki", help="wiki where --topic titles live (default enwiki)")
    an.add_argument("--out-lang", choices=["uk", "en"], default="uk", help="language of summary_text and the PDF")
    an.set_defaults(func=cmd_analyze)

    rp = sub.add_parser("report", help="re-render the PDF of a previous run with your own conclusion")
    rp.add_argument("--run-id", required=True)
    rp.add_argument("--conclusion", help="2-4 sentences; use only numbers from the analyze output")
    rp.add_argument("--question")
    rp.add_argument("--out-lang", choices=["uk", "en"], help="PDF language (default: the one used by analyze)")
    rp.set_defaults(func=cmd_report)

    a = p.parse_args(argv)
    a.func(a)


if __name__ == "__main__":
    main()
