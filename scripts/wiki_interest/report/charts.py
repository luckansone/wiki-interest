"""The two charts: traffic-adjusted interest index over time, and the year-over-year change with its CI."""

from __future__ import annotations

import numpy as np
import pandas as pd

from wiki_interest.analysis.metrics import pct
from wiki_interest.enums import Lang
from wiki_interest.models import LangMetrics
from wiki_interest.report.style import GRID, INK, INK2, colors_for, plt
from wiki_interest.text import CONFIDENCE, PDF_TEXT, VERDICT


def index_series(series_vpm: dict[str, pd.Series], h: int) -> dict[str, pd.Series]:
    """Traffic-adjusted interest indexed so that the mean of the first h months = 100."""
    out = {}
    for lang, s in series_vpm.items():
        base = float(np.mean(s.to_numpy()[:h]))
        out[lang] = s / base * 100 if base > 0 else s * 0
    return out


def draw_index(ax, series_vpm: dict[str, pd.Series], colors: dict, h: int, lang: Lang = Lang.UK) -> None:
    t = PDF_TEXT[lang]
    idx = index_series(series_vpm, h)
    for code, s in idx.items():
        x = s.index.to_timestamp()
        ax.plot(x, s.values, color=colors[code], linewidth=0.8, alpha=0.35)
        smooth = s.rolling(3, min_periods=1).mean()
        ax.plot(x, smooth.values, color=colors[code], linewidth=2, label=code)
        if len(idx) <= 4:  # direct labels at line end
            ax.annotate(
                code,
                (x[-1], smooth.values[-1]),
                xytext=(4, 0),
                textcoords="offset points",
                color=INK,
                fontsize=8,
                va="center",
            )
    ax.axhline(100, color=INK2, linewidth=0.6, linestyle=":")
    ax.set_ylabel(t["index_ylabel"].format(h=h))
    ax.set_title(t["index_title"], loc="left", fontsize=9, color=INK)
    ax.legend(frameon=False, ncol=min(len(idx), 8), fontsize=7.5, loc="upper left")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def draw_yoy(ax, results: dict[str, LangMetrics], colors: dict, lang: Lang = Lang.UK) -> None:
    t = PDF_TEXT[lang]
    langs = [l for l, r in results.items() if r.yoy_norm is not None][::-1]
    for i, l in enumerate(langs):
        r = results[l]
        ci = r.yoy_norm_ci90 or (r.yoy_norm, r.yoy_norm)
        ax.plot([ci[0] * 100, ci[1] * 100], [i, i], color=colors[l], linewidth=2, solid_capstyle="round")
        ax.plot(r.yoy_norm * 100, i, "o", color=colors[l], markersize=7, markeredgecolor="white", markeredgewidth=1.5)
        ax.annotate(
            f"{pct(r.yoy_norm)}  {VERDICT[lang][r.verdict]}, {t['conf']} {CONFIDENCE[lang][r.confidence]}",
            (1.0, i),
            xycoords=("axes fraction", "data"),
            xytext=(6, 0),
            textcoords="offset points",
            va="center",
            fontsize=7.5,
            color=INK,
        )
    ax.axvline(0, color=INK2, linewidth=0.8)
    ax.set_yticks(range(len(langs)), langs)
    ax.set_xlabel(t["yoy_xlabel"])
    ax.set_title(t["yoy_title"], loc="left", fontsize=9, color=INK)
    lo = min([0] + [(results[l].yoy_norm_ci90 or (results[l].yoy_norm,))[0] * 100 for l in langs])
    hi = max([0] + [(results[l].yoy_norm_ci90 or (0, results[l].yoy_norm))[-1] * 100 for l in langs])
    span = max(hi - lo, 10)
    ax.set_xlim(lo - 0.08 * span, hi + 0.08 * span)
    ax.set_ylim(-0.7, len(langs) - 0.3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def save_chart_png(
    path, series_vpm: dict[str, pd.Series], results: dict[str, LangMetrics], h: int, lang: Lang = Lang.UK
) -> None:
    colors = colors_for(results)
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 6.5), gridspec_kw={"height_ratios": [3, 2]})
    draw_index(a1, series_vpm, colors, h, lang)
    draw_yoy(a2, results, colors, lang)
    fig.tight_layout()
    pos = a2.get_position()  # leave room on the right for the aligned text labels
    a2.set_position([pos.x0, pos.y0, pos.width * 0.66, pos.height])
    fig.savefig(path, dpi=150)
    plt.close(fig)
