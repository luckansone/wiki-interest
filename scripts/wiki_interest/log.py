"""Logging to stderr with loguru + rich, drawn in a btop-like style. stdout carries only the JSON result.

Modes (`--log` or WI_LOG):

- `auto` (default): `rich` when stderr is a terminal (a human), `quiet` when it is piped (an agent).
  Agents read stderr too, so a quiet default keeps their context small.
- `rich`: boxed btop-like lines, a progress meter while fetching and a dashboard at the end.
- `plain`: one timestamped line per event, no colors (CI logs, files).
- `quiet`: warnings and errors only, one short line each.

WI_LOG_LEVEL=DEBUG also shows every cache hit and HTTP request.
"""

from __future__ import annotations

import sys
import threading
import time
import traceback
from collections import Counter
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger
from rich import box
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import BarColumn, MofNCompleteColumn, Progress, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.text import Text

from wiki_interest import __version__
from wiki_interest.enums import Confidence, LogMode, Verdict


if TYPE_CHECKING:
    import pandas as pd

    from wiki_interest.models import RunRecord

console = Console(stderr=True, highlight=False)

# btop palette: dim frame, cyan labels, green -> yellow -> red meters
FRAME, LABEL, MUTED = "grey42", "cyan", "grey62"
LEVEL_STYLE = {
    "TRACE": "grey50",
    "DEBUG": "grey62",
    "INFO": "bold bright_cyan",
    "SUCCESS": "bold green",
    "WARNING": "bold yellow",
    "ERROR": "bold red",
    "CRITICAL": "bold white on red",
}
VERDICT_STYLE = {Verdict.GROWING: "green", Verdict.DECLINING: "red", Verdict.STABLE_OR_UNCLEAR: "yellow"}
CONF_STYLE = {Confidence.HIGH: "green", Confidence.MEDIUM: "yellow", Confidence.LOW: "red"}
SPARK = "▁▂▃▄▅▆▇█"

_mode = LogMode.QUIET


class Telemetry:
    """Thread-safe counters and stage timings for the final dashboard."""

    def __init__(self):
        self._lock = threading.Lock()
        self.counts: Counter[str] = Counter()
        self.stages: dict[str, float] = {}

    def count(self, key: str, n: int = 1) -> None:
        with self._lock:
            self.counts[key] += n

    def reset(self) -> None:
        with self._lock:
            self.counts.clear()
            self.stages.clear()


telemetry = Telemetry()


# ---------------------------------------------------------------- setup
def _scope(record) -> str:
    return record["extra"].get("scope") or record["name"].rsplit(".", 1)[-1]


def _rich_sink(message) -> None:
    r = message.record
    level = r["level"].name
    line = Text.assemble(
        ("│ ", FRAME),
        (r["time"].strftime("%H:%M:%S.%f")[:-3], MUTED),
        (" │ ", FRAME),
        (f"{level:<7}", LEVEL_STYLE.get(level, "")),
        (" │ ", FRAME),
        (f"{_scope(r):<8}", LABEL),
        (" │ ", FRAME),
        (r["message"], "bright_white" if level != "DEBUG" else MUTED),
    )
    if r["exception"]:
        line.append(f"\n{r['exception'].type.__name__}: {r['exception'].value}", "red")
    console.print(line, soft_wrap=True)


def _plain_sink(message) -> None:
    r = message.record
    sys.stderr.write(f"{r['time']:%H:%M:%S} {r['level'].name:<7} {_scope(r):<8} {r['message']}\n")
    if r["exception"]:  # full traceback: this is the mode for bug reports
        sys.stderr.write("".join(traceback.format_exception(*r["exception"])))


def _quiet_sink(message) -> None:
    r = message.record
    sys.stderr.write(f"wi: {r['level'].name.lower()}: {r['message']}\n")


def setup(mode: LogMode | str = LogMode.AUTO, level: str = "INFO") -> LogMode:
    """Configure loguru for this process. Returns the resolved mode."""
    global _mode
    mode = LogMode(mode)
    if mode == LogMode.AUTO:
        mode = LogMode.RICH if sys.stderr.isatty() else LogMode.QUIET
    _mode = mode
    telemetry.reset()
    logger.remove()
    if mode == LogMode.RICH:
        logger.add(_rich_sink, level=level, colorize=False, format="{message}")
    elif mode == LogMode.PLAIN:
        logger.add(_plain_sink, level=level, colorize=False, format="{message}")
    else:
        logger.add(_quiet_sink, level="WARNING", colorize=False, format="{message}")
    return mode


def is_rich() -> bool:
    return _mode == LogMode.RICH


def header(command: str) -> None:
    if is_rich():
        console.rule(
            Text.assemble(
                ("┤ ", FRAME),
                ("wiki-interest ", "bold bright_cyan"),
                (f"{__version__} ", MUTED),
                ("· ", FRAME),
                (command, "bold white"),
                (" ├", FRAME),
            ),
            style=FRAME,
            align="left",
            characters="─",
        )


@contextmanager
def stage(name: str) -> Iterator[None]:
    """Time a pipeline stage; the time shows in the dashboard."""
    start = time.perf_counter()
    logger.bind(scope=name).debug("start")
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        telemetry.stages[name] = telemetry.stages.get(name, 0.0) + elapsed
        logger.bind(scope=name).info(f"done in {elapsed:.2f} s")


@contextmanager
def progress(total: int, description: str) -> Iterator[Callable[[], None]]:
    """Show a btop-like meter in rich mode (a no-op elsewhere). Yields `advance()`."""
    if not is_rich() or total <= 0:
        yield lambda: None
        return
    bar = Progress(
        TextColumn(f"[{FRAME}]│[/] [{LABEL}]{{task.description:<8}}[/]"),
        BarColumn(bar_width=32, style=FRAME, complete_style="green", finished_style="bright_green"),
        MofNCompleteColumn(),
        TextColumn(f"[{FRAME}]│[/]"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    )
    with bar:
        task = bar.add_task(description, total=total)
        yield lambda: bar.advance(task)


# ---------------------------------------------------------------- dashboard
def _meter(value: float | None, half: int = 10, full_scale: float = 0.5) -> Text:
    """Diverging meter: red cells left of the center line for decline, green right for growth."""
    if value is None:
        return Text("·" * half + "┊" + "·" * half, FRAME)
    cells = min(round(abs(value) / full_scale * half), half)
    neg, pos = (cells, 0) if value < 0 else (0, cells)
    return Text.assemble(
        ("·" * (half - neg), FRAME), ("■" * neg, "red"), ("┊", MUTED), ("■" * pos, "green"), ("·" * (half - pos), FRAME)
    )


def _spark(series: pd.Series | None, width: int = 24) -> Text:
    if series is None or len(series) == 0:
        return Text("—", FRAME)
    v = series.to_numpy(dtype=float)[-width:]
    lo, hi = float(v.min()), float(v.max())
    span = hi - lo or 1.0
    return Text("".join(SPARK[min(int((x - lo) / span * (len(SPARK) - 1)), len(SPARK) - 1)] for x in v), LABEL)


def _pct(v: float | None) -> str:
    return "  n/a" if v is None else f"{v * 100:+5.0f}%"


def dashboard(run: RunRecord, series: dict[str, pd.Series], files: dict[str, str | None]) -> None:
    """Print the final btop-like summary box (rich mode only)."""
    if not is_rich():
        return
    c = telemetry.counts
    hits, misses = c["cache_hit"], c["cache_miss"]
    hit_rate = f"{hits / (hits + misses):.0%}" if hits + misses else "—"
    if run.synthetic:
        net = Text.assemble(
            ("net  ", LABEL), ("synthetic data (WI_FAKE_API=1): no requests, not real pageviews", "red")
        )
    else:
        net = Text.assemble(
            ("net  ", LABEL),
            (f"requests {c['http_request']}", "white"),
            ("  ·  ", FRAME),
            (f"cache {hits}/{hits + misses} ({hit_rate})", "white"),
            ("  ·  ", FRAME),
            (f"retries {c['http_retry']}", "yellow" if c["http_retry"] else "white"),
        )
    cpu = Text.assemble(
        ("time ", LABEL),
        *(part for name, sec in telemetry.stages.items() for part in ((f"{name} ", MUTED), (f"{sec:.2f}s  ", "white"))),
    )

    langs = Table(box=box.SIMPLE_HEAD, border_style=FRAME, header_style=f"bold {LABEL}", pad_edge=False, expand=True)
    for col, kw in (
        ("lang", {}),
        ("yoy adj.", {"justify": "right"}),
        ("−50%      0      +50%", {"justify": "center"}),
        ("share of attention, 24 mo", {}),
        ("verdict", {}),
        ("conf.", {}),
        ("flags", {"overflow": "fold"}),
    ):
        langs.add_column(col, **kw)
    for lang, r in run.results.items():
        if not r.has_data:
            langs.add_row(
                Text(lang, "bold"),
                "  n/a",
                _meter(None),
                Text("no article", MUTED),
                Text("no data", MUTED),
                "",
                Text("MISSING_ARTICLE", "yellow"),
            )
            continue
        langs.add_row(
            Text(lang, "bold"),
            Text(_pct(r.yoy_norm), VERDICT_STYLE[r.verdict]),
            _meter(r.yoy_norm),
            _spark(series.get(lang)),
            Text(r.verdict.value, VERDICT_STYLE[r.verdict]),
            Text(r.confidence.value, CONF_STYLE[r.confidence]),
            Text(", ".join(f.value for f in r.flags) or "—", "yellow" if r.flags else FRAME),
        )

    paths = [Path(p) for k, p in files.items() if p and k != "pdf_shared"]
    out = Text.assemble(
        ("out  ", LABEL),
        (f"{paths[0].parent}/" if paths else "—", "white"),
        ("\n     ", ""),
        ("  ·  ".join(p.name for p in paths), "bright_white"),
    )
    if files.get("pdf_shared"):
        out.append_text(Text.assemble(("\nchat ", LABEL), (files["pdf_shared"], "bright_green")))

    console.print(
        Panel(
            Group(net, cpu, langs, out),
            box=box.ROUNDED,
            border_style=FRAME,
            title=Text.assemble(("┤ ", FRAME), ("wiki-interest", "bold bright_cyan"), (" ├", FRAME)),
            title_align="left",
            subtitle=Text.assemble(("┤ ", FRAME), (f"run {run.run_id}", MUTED), (" ├", FRAME)),
            subtitle_align="right",
            padding=(0, 1),
        )
    )
