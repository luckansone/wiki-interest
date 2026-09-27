"""Pydantic models: the CLI request, per-language results, the saved run and the stdout JSON.

The JSON shapes are a contract with the agent (SKILL.md) and with `run.json` files of earlier
runs, so field names and order must not change without updating SKILL.md.
"""

from __future__ import annotations

from typing import Annotated, Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Discriminator, Field, Tag, TypeAdapter

from wiki_interest.enums import Confidence, Flag, Lang, Reason, Status, Verdict, Why


# ---------------------------------------------------------------- input
class Weights(BaseModel):
    """Ranking weights: growth of interest, share of interest (level), confidence."""

    growth: Annotated[float, Field(ge=0)] = 0.5
    level: Annotated[float, Field(ge=0)] = 0.3
    confidence: Annotated[float, Field(ge=0)] = 0.2

    @classmethod
    def parse(cls, raw: str | None) -> Weights:
        """'growth=0.5,level=0.3' -> Weights. Raises ValueError with a readable message."""
        values = cls().model_dump()
        for part in (raw or "").split(","):
            if not part.strip():
                continue
            key, sep, value = part.partition("=")
            key = key.strip()
            if not sep:
                raise ValueError(f"bad weight '{part.strip()}': expected name=value")
            if key not in values:
                raise ValueError(f"unknown weight '{key}', use growth/level/confidence")
            try:
                values[key] = float(value)
            except ValueError:
                raise ValueError(f"weight '{key}' must be a number, got '{value.strip()}'") from None
            if values[key] < 0:
                raise ValueError(f"weight '{key}' must be >= 0")
        return cls(**values)


class AnalyzeRequest(BaseModel):
    """Validated arguments of `wi analyze` (built by the CLI after its own checks)."""

    topics: list[str] = Field(min_length=1)
    langs: list[str] = Field(min_length=1, max_length=8)
    months: Annotated[int, Field(ge=12, le=120)] = 24
    pdf: bool = True
    question: str | None = None
    weights: Weights = Weights()
    source_site: str = "enwiki"
    out_lang: Lang = Lang.UK
    command: str = ""

    @property
    def yoy_window(self) -> int:
        """Months per side of the year-over-year comparison (12, or half the window if shorter)."""
        return 12 if self.months >= 24 else self.months // 2


# ---------------------------------------------------------------- data layer
class ResolvedTopic(BaseModel):
    """A --topic resolved through Wikidata: its QID, English label and titles per language."""

    topic: str
    qid: str
    label: str
    titles: dict[str, str]


class LangData(BaseModel):
    """Fetched monthly series of one language edition."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    articles: dict[str, str]  # topic label -> article title in this edition
    missing: list[str]  # topic labels without an article in this edition
    topic_views: pd.Series | None  # sum over the topic's articles; None if no article exists
    project_views: pd.Series  # whole edition (normalization denominator)


class Collected(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    window: list[pd.Period]
    resolved: list[ResolvedTopic]
    per_lang: dict[str, LangData]
    fetched_on: str


# ---------------------------------------------------------------- analysis results
class LangMetrics(BaseModel):
    """Metrics, verdict and confidence of one language. See references/METHODOLOGY.md."""

    months: int
    yoy_window_months: int
    median_views_month: int
    views_per_million: float
    yoy_raw: float | None
    yoy_norm: float | None
    yoy_norm_ci90: tuple[float, float] | None
    yoy_norm_prev_year: float | None
    trend_pct_year: float
    trend_p_value: float
    spike_share: float | None
    verdict: Verdict
    confidence: Confidence
    flags: list[Flag]
    confidence_reason_codes: list[Reason | Flag]
    missing_articles: list[str]
    confidence_reasons: list[str] = []  # English text of the reason codes

    @property
    def has_data(self) -> bool:
        return True


class NoData(BaseModel):
    """The edition has no article on any of the topic's articles."""

    status: Status = Status.NO_DATA
    missing_articles: list[str]
    flags: list[Flag] = [Flag.MISSING_ARTICLE]

    @property
    def has_data(self) -> bool:
        return False


def _result_kind(v: Any) -> str:
    status = v.get("status") if isinstance(v, dict) else getattr(v, "status", None)
    return "no_data" if status == Status.NO_DATA else "metrics"


# An explicit discriminator: both shapes share fields, so pydantic must not guess.
LangResult = Annotated[
    Annotated[LangMetrics, Tag("metrics")] | Annotated[NoData, Tag("no_data")], Discriminator(_result_kind)
]
LANG_RESULTS = TypeAdapter(dict[str, LangResult])


class RankRow(BaseModel):
    lang: str
    score: float
    position: int
    why: list[Why]


# ---------------------------------------------------------------- saved run and stdout
class TopicRef(BaseModel):
    input: str
    label: str
    qid: str


class RunRecord(BaseModel):
    """Everything about one analysis; saved as run.json and used to re-render the PDF."""

    run_id: str
    question: str | None = None
    out_lang: Lang = Lang.UK
    langs: list[str]
    months: int
    period: tuple[str, str]
    fetched_on: str
    topics: list[TopicRef]
    articles: dict[str, dict[str, str]]
    weights: Weights
    results: dict[str, LangResult]
    ranking: list[RankRow]
    summary_text: str
    synthetic: bool = False
    command: str = ""
    conclusion: str | None = None

    @property
    def measured(self) -> dict[str, LangMetrics]:
        """Languages with data, in request order."""
        return {l: r for l, r in self.results.items() if r.has_data}

    @property
    def no_data(self) -> list[str]:
        return [l for l, r in self.results.items() if not r.has_data]

    @property
    def yoy_window(self) -> int:
        return 12 if self.months >= 24 else self.months // 2


class CompactResult(BaseModel):
    """Per-language result as printed to stdout: only what the agent needs."""

    verdict: Verdict | None = None
    confidence: Confidence | None = None
    yoy_norm: float | None = None
    yoy_norm_ci90: tuple[float, float] | None = None
    yoy_norm_prev_year: float | None = None
    yoy_raw: float | None = None
    median_views_month: int | None = None
    views_per_million: float | None = None
    trend_pct_year: float | None = None
    trend_p_value: float | None = None
    flags: list[Flag] | None = None
    status: Status | None = None

    @classmethod
    def of(cls, r: LangResult) -> CompactResult:
        return cls.model_validate(r.model_dump(include=set(cls.model_fields)))


class OutputRankRow(BaseModel):
    lang: str
    position: int
    why: list[Why]


class Files(BaseModel):
    run_json: str | None = None
    series_csv: str | None = None
    chart_png: str | None = None
    pdf: str | None = None
    pdf_shared: str | None = None  # copy of the PDF in the folder the chat shows to the user (share_dir)


class AnalyzeOutput(BaseModel):
    run_id: str
    period: tuple[str, str]
    topics: list[str]
    results: dict[str, CompactResult]
    ranking: list[OutputRankRow]
    summary_text: str
    files: Files
    warnings: list[str] | None = None


class ReportOutput(BaseModel):
    run_id: str
    files: Files


class ErrorOutput(BaseModel):
    error: str
    fix: str
