"""Errors that the CLI turns into `{"error": ..., "fix": ...}` JSON."""

from __future__ import annotations


class WikiInterestError(RuntimeError):
    """Base error. `fix` is the hint shown to the agent next to the message."""

    fix: str = "retry in a minute; if it persists check network access to wikimedia.org"

    def __init__(self, message: str, fix: str | None = None):
        super().__init__(message)
        if fix is not None:
            self.fix = fix


class ApiError(WikiInterestError):
    """Wikimedia or Wikidata request failed, or returned no usable data."""


class TopicNotFoundError(ApiError):
    fix = (
        "pass the exact English Wikipedia article title (as in its URL, e.g. 'Intermittent_fasting') "
        "or a Wikidata QID like Q12345; or set --source-site ukwiki and use the Ukrainian title"
    )


class UnknownLanguageError(ApiError):
    fix = "use Wikipedia language codes, e.g. --langs uk,pl,cs,de,tr"


class UsageError(WikiInterestError):
    """Bad command-line input."""

    fix = 'bash scripts/wi analyze --topic "<English article title>" --langs uk,pl --months 24'
