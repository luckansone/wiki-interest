"""Page 1 of the PDF: a fixed one-page layout (header, conclusion, 2 charts, table, limitations, footer)."""

from __future__ import annotations

import pandas as pd

from wiki_interest.analysis.metrics import fmt_int, pct
from wiki_interest.models import RunRecord
from wiki_interest.report.charts import draw_index, draw_yoy
from wiki_interest.report.content import limitations, title_of
from wiki_interest.report.style import (
    ALERT,
    GRID,
    HEADER_BG,
    INK,
    INK2,
    LEFT,
    PAGE_H,
    PAGE_W,
    WIDTH,
    colors_for,
    fmt_p,
    plt,
    wrap,
)
from wiki_interest.text import CONFIDENCE, PDF_TEXT, VERDICT


def draw_summary_page(run: RunRecord, series_vpm: dict[str, pd.Series], conclusion: str):
    lang = run.out_lang
    t = PDF_TEXT[lang]
    h = run.yoy_window
    results = run.measured
    colors = colors_for(results)
    fig = plt.figure(figsize=(PAGE_W, PAGE_H))
    L, W = LEFT, WIDTH

    fig.text(L, 0.965, wrap(title_of(run), 80), fontsize=13, weight="bold", color=INK, va="top")
    sub = t["sub"].format(
        langs=", ".join(run.langs), p0=run.period[0], p1=run.period[1], m=run.months, f=run.fetched_on
    )
    fig.text(L, 0.925, sub, fontsize=8, color=INK2, va="top")
    if run.synthetic:
        fig.text(0.5, 0.905, t["demo"], ha="center", fontsize=10, color=ALERT, weight="bold")

    fig.text(L, 0.89, t["conclusion"], fontsize=10, weight="bold", color=INK, va="top")
    fig.text(L, 0.872, wrap(conclusion, 112), fontsize=8.2, color=INK, va="top", linespacing=1.35)

    a1 = fig.add_axes([L + 0.04, 0.545, W - 0.07, 0.215])
    draw_index(a1, {l: series_vpm[l] for l in results}, colors, h, lang)
    a2 = fig.add_axes([L + 0.04, 0.345, (W - 0.07) * 0.64, 0.145])
    draw_yoy(a2, results, colors, lang)

    # Metrics table
    rows = []
    for l, r in results.items():
        ci = r.yoy_norm_ci90
        rows.append(
            [
                l,
                str(len(run.articles[l])),
                fmt_int(r.median_views_month),
                f"{r.views_per_million:.1f}",
                pct(r.yoy_raw),
                f"{pct(r.yoy_norm)} [{pct(ci[0])}…{pct(ci[1])}]" if ci else pct(r.yoy_norm),
                fmt_p(r.trend_p_value),
                VERDICT[lang][r.verdict],
                CONFIDENCE[lang][r.confidence],
            ]
        )
    ta = fig.add_axes([L, 0.135, W, 0.155])
    ta.axis("off")
    widths = [0.06, 0.07, 0.11, 0.12, 0.08, 0.2, 0.08, 0.16, 0.1]
    tbl = ta.table(cellText=rows, colLabels=t["cols"], loc="upper center", cellLoc="center", colWidths=widths)
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(6.8)
    tbl.scale(1, 1.25)
    for (ri, _), cell in tbl.get_celld().items():
        cell.set_edgecolor(GRID)
        if ri == 0:
            cell.set_height(cell.get_height() * 1.8)
            cell.set_text_props(weight="bold", color=INK)
            cell.set_facecolor(HEADER_BG)

    # Limitations right under the table, whatever its height (depends on the number of languages)
    bb = tbl.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
    y0 = bb.y0 - 0.015
    fig.text(L, y0, t["lim_title"], fontsize=9, weight="bold", color=INK, va="top")
    lim_txt = wrap("\n".join("• " + x for x in limitations(run)), 130).split("\n")
    max_lines = max(int((y0 - 0.016 - 0.045) / 0.0105), 3)  # stop above the footer
    if len(lim_txt) > max_lines:
        lim_txt = lim_txt[: max_lines - 1] + [t["lim_more"]]
    fig.text(L, y0 - 0.016, "\n".join(lim_txt), fontsize=6.6, color=INK2, va="top", linespacing=1.3)

    arts = "; ".join(f"{l}: {', '.join(v.values()) or '—'}" for l, v in run.articles.items())
    fig.text(L, 0.022, wrap(t["foot"].format(arts=arts, rid=run.run_id), 150), fontsize=5.8, color=INK2, va="bottom")
    return fig
