"""Command-line interface. stdout is always ONE compact JSON object (or {"error","fix"}); logs go to stderr.

  wi analyze --topic "Intermittent fasting" --langs pl,cs --months 24 [--no-pdf] [--out-lang en]
  wi report  --run-id <id> --conclusion "..."      # re-render the PDF with the agent's own wording

Every analyze run writes a PDF report (one-page summary + appendix) unless --no-pdf is given.
"""

from __future__ import annotations

import argparse
import json
import sys

from loguru import logger
from pydantic import BaseModel

from wiki_interest import log as wlog
from wiki_interest import pipeline
from wiki_interest.config import MAX_LANGS, MAX_MONTHS, MIN_MONTHS, Settings
from wiki_interest.data.languages import normalize_lang
from wiki_interest.enums import Lang, LogMode
from wiki_interest.errors import UsageError, WikiInterestError
from wiki_interest.models import AnalyzeRequest, ErrorOutput, Weights


def emit(model: BaseModel, code: int = 0):
    """Print the result as one JSON line and exit. None values are left out."""
    print(json.dumps(model.model_dump(mode="json", exclude_none=True), ensure_ascii=False, separators=(",", ":")))
    sys.exit(code)


def parse_langs(raw: str) -> list[str]:
    out: list[str] = []
    for part in raw.replace(";", ",").split(","):
        if part.strip():
            code = normalize_lang(part)
            if code not in out:
                out.append(code)
    return out


def build_request(a: argparse.Namespace) -> AnalyzeRequest:
    """Check the arguments in the order the agent can fix them, with a concrete fix for each."""
    langs = parse_langs(a.langs)
    if len(langs) > MAX_LANGS:
        raise UsageError(
            f"{len(langs)} languages given; the MVP supports up to {MAX_LANGS} per run",
            f"split into several runs of <= {MAX_LANGS} languages, or keep the {MAX_LANGS} most relevant",
        )
    if not MIN_MONTHS <= a.months <= MAX_MONTHS:
        raise UsageError(
            f"--months must be between {MIN_MONTHS} and {MAX_MONTHS}", "use --months 24 (default) or --months 36"
        )
    try:
        weights = Weights.parse(a.weights)
    except ValueError as e:
        raise UsageError(str(e), 'e.g. --weights "growth=0.5,level=0.3,confidence=0.2"') from None
    return AnalyzeRequest(
        topics=a.topic,
        langs=langs,
        months=a.months,
        pdf=a.pdf,
        question=a.question,
        weights=weights,
        source_site=a.source_site,
        out_lang=Lang(a.out_lang),
        command=" ".join(sys.argv),
    )


def cmd_analyze(a: argparse.Namespace, settings: Settings) -> BaseModel:
    return pipeline.analyze(build_request(a), settings)


def cmd_report(a: argparse.Namespace, settings: Settings) -> BaseModel:
    return pipeline.rerender(a.run_id, settings, a.conclusion, a.question, Lang(a.out_lang) if a.out_lang else None)


class _JsonArgParser(argparse.ArgumentParser):
    """Argument errors come back as JSON with a fix hint, like every other error."""

    def error(self, message):
        emit(ErrorOutput(error=f"bad arguments: {message}", fix=UsageError.fix), 1)


def make_parser() -> argparse.ArgumentParser:
    p = _JsonArgParser(prog="wi", description="Wikipedia interest analysis")
    p.add_argument(
        "--log",
        choices=[m.value for m in LogMode],
        help="stderr logging: auto (default: rich on a terminal, quiet when piped), rich, plain, quiet; or WI_LOG",
    )
    sub = p.add_subparsers(dest="cmd", required=True, parser_class=_JsonArgParser)

    an = sub.add_parser("analyze", help="trend of a topic across language editions")
    an.add_argument(
        "--topic",
        action="append",
        required=True,
        help="English Wikipedia article title or Wikidata QID; repeat to sum several articles",
    )
    an.add_argument("--langs", required=True, help="comma-separated, e.g. uk,pl,cs")
    an.add_argument("--months", type=int, default=24, help=f"complete months to analyze ({MIN_MONTHS}-{MAX_MONTHS})")
    an.add_argument(
        "--pdf",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="write the PDF report: one-page summary + appendix (default: on; --no-pdf to skip)",
    )
    an.add_argument("--question", help="question text used as the report title")
    an.add_argument("--weights", help='ranking weights, e.g. "growth=0.5,level=0.3,confidence=0.2"')
    an.add_argument("--source-site", default="enwiki", help="wiki where --topic titles live (default enwiki)")
    an.add_argument(
        "--out-lang", choices=[l.value for l in Lang], default="uk", help="language of summary_text and the PDF"
    )
    an.set_defaults(func=cmd_analyze)

    rp = sub.add_parser("report", help="re-render the PDF of a previous run with your own conclusion")
    rp.add_argument("--run-id", required=True)
    rp.add_argument("--conclusion", help="2-4 sentences; use only numbers from the analyze output")
    rp.add_argument("--question")
    rp.add_argument(
        "--out-lang", choices=[l.value for l in Lang], help="PDF language (default: the one used by analyze)"
    )
    rp.set_defaults(func=cmd_report)
    return p


def main(argv: list[str] | None = None) -> None:
    a = make_parser().parse_args(argv)
    settings = Settings.from_env()
    wlog.setup(a.log or settings.log_mode, level=settings.log_level)
    log = logger.bind(scope="cli")
    try:
        result = a.func(a, settings)
    except WikiInterestError as e:
        log.info(f"error: {e}")  # the JSON carries it; quiet mode does not repeat it on stderr
        emit(ErrorOutput(error=str(e), fix=e.fix), 1)
    except Exception as e:  # a bug: still answer with JSON, so the agent does not parse a traceback
        log.opt(exception=e).error("unexpected error")
        emit(
            ErrorOutput(
                error=f"internal error: {type(e).__name__}: {e}",
                fix="re-run once; if it repeats, run with WI_LOG=plain WI_LOG_LEVEL=DEBUG and report the log",
            ),
            1,
        )
    emit(result)
