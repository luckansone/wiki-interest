"""Settings from environment variables, and the analysis thresholds.

Settings are read from the environment on every `Settings.from_env()` call, so tests can
change them with `monkeypatch.setenv`.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from wiki_interest import __version__
from wiki_interest.enums import LogMode


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    contact: str = Field("https://github.com/ ; set WI_CONTACT env var", description="WI_CONTACT")
    cache_dir: Path = Field(Path.home() / ".cache" / "wiki-interest", description="WI_CACHE")
    out_dir: Path = Field(Path("wi_output"), description="WI_OUT")
    offline: bool = Field(False, description="WI_OFFLINE=1: use only the disk cache")
    fake_api: bool = Field(False, description="WI_FAKE_API=1: synthetic responses (demo, tests, evals)")
    log_mode: LogMode = Field(LogMode.AUTO, description="WI_LOG")
    log_level: str = Field("INFO", description="WI_LOG_LEVEL (DEBUG shows every request and cache hit)")
    share_dir: Path | None = Field(None, description="WI_SHARE_DIR: folder the chat shows to the user")

    @classmethod
    def from_env(cls) -> Settings:
        env = os.environ
        values: dict = {
            "offline": env.get("WI_OFFLINE") == "1",
            "fake_api": env.get("WI_FAKE_API") == "1",
        }
        for field, var in (("contact", "WI_CONTACT"), ("cache_dir", "WI_CACHE"), ("out_dir", "WI_OUT")):
            if env.get(var):
                values[field] = env[var]
        if env.get("WI_LOG"):
            values["log_mode"] = env["WI_LOG"].lower()
        if env.get("WI_LOG_LEVEL"):
            values["log_level"] = env["WI_LOG_LEVEL"].upper()
        values["share_dir"] = _share_dir(env.get("WI_SHARE_DIR"))
        return cls(**values)

    @property
    def user_agent(self) -> str:
        # Wikimedia asks every client to send a descriptive User-Agent with contact info.
        return f"wiki-interest-skill/{__version__} ({self.contact})"


# The code-execution sandbox of claude.ai (web, desktop, mobile) shows files in this folder to the user.
CHAT_OUTPUTS_DIR = Path("/mnt/user-data/outputs")


def _share_dir(raw: str | None) -> Path | None:
    """WI_SHARE_DIR if set ("off" disables sharing); else the chat outputs folder if it exists and is writable."""
    if raw is not None:
        return None if raw.strip().lower() in ("", "0", "off", "none") else Path(raw)
    if CHAT_OUTPUTS_DIR.is_dir() and os.access(CHAT_OUTPUTS_DIR, os.W_OK):
        return CHAT_OUTPUTS_DIR
    return None


class Thresholds(BaseModel):
    """Every number that decides a flag, verdict or confidence. See references/METHODOLOGY.md."""

    model_config = ConfigDict(frozen=True)

    low_volume_median: int = 300  # median views/month below this -> percentages are noisy
    spike_share_max: float = 0.40  # one month contributing >40% of the YoY gain -> spike-driven
    project_shift_min: float = 0.05  # raw vs normalized YoY disagree in sign and one is >5%
    p_significant: float = 0.05
    bootstrap_iters: int = 1000
    ci_level: float = 0.90
    seed: int = 42
    full_history_months: int = 24  # below this -> SHORT_HISTORY, and the YoY window shrinks


THRESHOLDS = Thresholds()

# HTTP
PAGEVIEWS_URL = "https://wikimedia.org/api/rest_v1/metrics/pageviews"
WIKIDATA_URL = "https://www.wikidata.org/w/api.php"
WIKIDATA_TTL_S = 30 * 24 * 3600
MAX_WORKERS = 8
MAX_ATTEMPTS = 5
MAX_RETRY_WAIT_S = 30
PAGEVIEWS_START = "2015-07"  # first month the Pageviews API has data for

# CLI limits
MAX_LANGS = 8
MIN_MONTHS, MAX_MONTHS = 12, 120
