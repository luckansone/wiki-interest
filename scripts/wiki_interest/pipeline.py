"""One analysis end to end: fetch -> analyze -> save run files -> chart + PDF. Also re-renders a saved PDF."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
from pathlib import Path

import pandas as pd
from loguru import logger

from wiki_interest import log as wlog
from wiki_interest.analysis.metrics import analyze_series
from wiki_interest.analysis.ranking import rank
from wiki_interest.analysis.stats import per_million_series
from wiki_interest.analysis.summary import summary_text
from wiki_interest.config import Settings
from wiki_interest.data import wikimedia
from wiki_interest.enums import Lang
from wiki_interest.errors import UsageError
from wiki_interest.models import (
    AnalyzeOutput,
    AnalyzeRequest,
    CompactResult,
    Files,
    LangResult,
    NoData,
    OutputRankRow,
    ReportOutput,
    RunRecord,
    TopicRef,
)


log = logger.bind(scope="pipeline")


def _run_id(req: AnalyzeRequest, fetched_on: str) -> str:
    key = json.dumps([req.topics, req.langs, req.months, req.weights.model_dump(), fetched_on])
    return dt.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + hashlib.sha1(key.encode()).hexdigest()[:6]


def _save_json(path: Path, model) -> None:
    path.write_text(json.dumps(model.model_dump(mode="json"), ensure_ascii=False, indent=1))


def share_pdf(pdf: Path, run: RunRecord, settings: Settings) -> str | None:
    """Copy the PDF to the folder the chat shows to the user, under a readable name. Never fails the run."""
    if settings.share_dir is None:
        return None
    slug = re.sub(r"[^a-z0-9]+", "-", run.topics[0].label.lower()).strip("-")[:40] if run.topics else ""
    target = settings.share_dir / f"wiki-interest-{slug or 'report'}-{run.run_id}.pdf"
    try:
        settings.share_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pdf, target)
    except OSError as e:  # a read-only or missing mount must not lose the analysis
        log.warning(f"could not copy the PDF to {settings.share_dir}: {e}")
        return None
    log.info(f"PDF shared → {target}")
    return str(target)


def analyze(req: AnalyzeRequest, settings: Settings) -> AnalyzeOutput:
    wlog.header("analyze")
    with wlog.stage("fetch"):
        data = wikimedia.collect(req.topics, req.langs, req.months, req.source_site)

    with wlog.stage("analyze"):
        results: dict[str, LangResult] = {}
        series_vpm: dict[str, pd.Series] = {}
        for l in req.langs:
            d = data.per_lang[l]
            if d.topic_views is None:
                results[l] = NoData(missing_articles=d.missing)
                log.info(f"{l}: no article on this topic, interest not measured")
                continue
            results[l] = analyze_series(d.topic_views, d.project_views, d.missing)
            series_vpm[l] = per_million_series(d.topic_views, d.project_views)
        ranking = rank(results, req.weights)
        summary = summary_text(results, ranking, req.out_lang)

    run = RunRecord(
        run_id=_run_id(req, data.fetched_on),
        question=req.question,
        out_lang=req.out_lang,
        langs=req.langs,
        months=req.months,
        period=(str(data.window[0]), str(data.window[-1])),
        fetched_on=data.fetched_on,
        topics=[TopicRef(input=r.topic, label=r.label, qid=r.qid) for r in data.resolved],
        articles={l: data.per_lang[l].articles for l in req.langs},
        weights=req.weights,
        results=results,
        ranking=ranking,
        summary_text=summary,
        synthetic=settings.fake_api,
        command=req.command,
    )
    run_dir = settings.out_dir / run.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    raw = pd.DataFrame({f"{l}_topic": d.topic_views for l, d in data.per_lang.items() if d.topic_views is not None})
    for l in req.langs:
        raw[f"{l}_project"] = data.per_lang[l].project_views
    raw.index = raw.index.astype(str)
    raw.to_csv(run_dir / "series.csv")
    _save_json(run_dir / "run.json", run)

    files = Files(run_json=str(run_dir / "run.json"), series_csv=str(run_dir / "series.csv"))
    warnings = []
    if not series_vpm:
        warnings.append(
            ("PDF and chart not created: " if req.pdf else "chart not created: ")
            + "none of the requested languages has an article on this topic. "
            "Re-run with a broader --topic (parent concept) or other --langs."
        )
        log.info(warnings[-1])
    else:
        from wiki_interest import report  # imported lazily: matplotlib is slow to load

        with wlog.stage("render"):
            files.chart_png = str(run_dir / "chart.png")
            report.save_chart_png(files.chart_png, series_vpm, run.measured, run.yoy_window, req.out_lang)
            if req.pdf:
                files.pdf = str(run_dir / "report.pdf")
                topic_views = {l: data.per_lang[l].topic_views for l in series_vpm}
                report.save_pdf(files.pdf, run, series_vpm, topic_views)
                files.pdf_shared = share_pdf(Path(files.pdf), run, settings)

    wlog.dashboard(run, series_vpm, files.model_dump())
    return AnalyzeOutput(
        run_id=run.run_id,
        period=run.period,
        topics=[f"{t.label} ({t.qid})" for t in run.topics],
        results={l: CompactResult.of(r) for l, r in results.items()},
        ranking=[OutputRankRow(lang=r.lang, position=r.position, why=r.why) for r in ranking],
        summary_text=summary,
        files=files,
        warnings=warnings or None,
    )


def rerender(
    run_id: str,
    settings: Settings,
    conclusion: str | None = None,
    question: str | None = None,
    out_lang: Lang | None = None,
) -> ReportOutput:
    """Re-render the PDF of a saved run, optionally with the agent's own conclusion, title or language."""
    wlog.header("report")
    run_dir = settings.out_dir / run_id
    if not (run_dir / "run.json").exists():
        raise UsageError(
            f"run '{run_id}' not found in {settings.out_dir}", "use the run_id printed by the analyze command"
        )
    run = RunRecord.model_validate_json((run_dir / "run.json").read_text())
    updates = {"conclusion": conclusion, "question": question, "out_lang": out_lang}
    run = run.model_copy(update={k: v for k, v in updates.items() if v})

    raw = pd.read_csv(run_dir / "series.csv", index_col=0)
    raw.index = pd.PeriodIndex(raw.index, freq="M")
    series_vpm = {l: per_million_series(raw[f"{l}_topic"], raw[f"{l}_project"]) for l in run.measured}
    topic_views = {l: raw[f"{l}_topic"] for l in run.measured}

    from wiki_interest import report

    pdf = run_dir / "report.pdf"
    with wlog.stage("render"):
        report.save_pdf(pdf, run, series_vpm, topic_views)
    _save_json(run_dir / "run.json", run)
    return ReportOutput(run_id=run_id, files=Files(pdf=str(pdf), pdf_shared=share_pdf(pdf, run, settings)))
