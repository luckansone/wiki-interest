"""Closed sets of values. They are `StrEnum`, so they compare equal to, and serialize as, plain strings."""

from __future__ import annotations

from enum import StrEnum


class Verdict(StrEnum):
    GROWING = "growing"
    DECLINING = "declining"
    STABLE_OR_UNCLEAR = "stable_or_unclear"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

    @property
    def score(self) -> float:
        """Contribution of confidence to the ranking score."""
        return {Confidence.HIGH: 1.0, Confidence.MEDIUM: 0.5, Confidence.LOW: 0.0}[self]


class Flag(StrEnum):
    """Data-quality problems of one language series (see references/METHODOLOGY.md)."""

    SHORT_HISTORY = "SHORT_HISTORY"
    LOW_VOLUME = "LOW_VOLUME"
    PROJECT_SHIFT = "PROJECT_SHIFT"
    SPIKE_DRIVEN = "SPIKE_DRIVEN"
    MISSING_ARTICLE = "MISSING_ARTICLE"
    TREND_CONFLICT = "TREND_CONFLICT"


class Reason(StrEnum):
    """Why confidence is not high. Flags are reasons too; see `reason_codes`."""

    CI_CROSSES_ZERO = "CI_CROSSES_ZERO"
    NOT_SIGNIFICANT = "NOT_SIGNIFICANT"
    TREND_VS_YEAR = "TREND_VS_YEAR"


class Why(StrEnum):
    """Reasons attached to a ranking row."""

    FASTEST_GROWTH = "fastest_growth"
    BEST_TREND_IN_SET = "best_trend_in_set"
    HIGHEST_SHARE_OF_INTEREST = "highest_share_of_interest"
    GROWING = "growing"
    DECLINING = "declining"
    # flags, lower case
    SHORT_HISTORY = "short_history"
    LOW_VOLUME = "low_volume"
    PROJECT_SHIFT = "project_shift"
    SPIKE_DRIVEN = "spike_driven"
    MISSING_ARTICLE = "missing_article"
    TREND_CONFLICT = "trend_conflict"


class Lang(StrEnum):
    """Output language of summary_text and the PDF."""

    UK = "uk"
    EN = "en"


class Status(StrEnum):
    NO_DATA = "no_data"


class LogMode(StrEnum):
    """stderr logging: `auto` = rich dashboard on a terminal, warnings only when piped (agents)."""

    AUTO = "auto"
    RICH = "rich"
    PLAIN = "plain"
    QUIET = "quiet"
