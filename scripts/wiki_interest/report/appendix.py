"""PDF appendix: text and tables that flow top-down onto as many A4 pages as the data needs."""

from __future__ import annotations

import pandas as pd

from wiki_interest.analysis.metrics import fmt_int, pct, reason_text
from wiki_interest.data.languages import edition_name
from wiki_interest.enums import Lang, Why
from wiki_interest.models import RunRecord
from wiki_interest.report.content import limitations, title_of
from wiki_interest.report.style import GRID, HEADER_BG, INK, INK2, LEFT, PAGE_H, PAGE_W, WIDTH, fmt_p, plt, wrap
from wiki_interest.text import CONFIDENCE, PDF_TEXT, VERDICT, WHY_UK


TOP, BOTTOM, ROW_H = 0.955, 0.04, 0.0165  # figure fractions; ROW_H = one table row


class Flow:
    """Places text and tables top-down and starts a new A4 page when the current one is full."""

    def __init__(self, header: str):
        self.header = header
        self.pages: list = []
        self._new_page()

    def _new_page(self) -> None:
        self.fig = plt.figure(figsize=(PAGE_W, PAGE_H))
        self.fig.text(LEFT, 0.975, self.header, fontsize=7, color=INK2, va="top")
        self.pages.append(self.fig)
        self.y = TOP

    def _room(self, height: float) -> None:
        if self.y - height < BOTTOM and self.y < TOP:
            self._new_page()

    def text(
        self, s: str, size: float = 7.5, bold: bool = False, color: str = INK, indent: float = 0.0, gap: float = 0.004
    ) -> None:
        chars = int((WIDTH - indent) * PAGE_W * 72 / (0.56 * size))  # ~average DejaVu glyph width
        line_h = size * 1.4 / 72 / PAGE_H
        hang = "   " if s.startswith("• ") else ""  # wrapped bullet lines align with the text, not the bullet
        for line in wrap(s, chars, hang).split("\n"):
            self._room(line_h)
            self.fig.text(
                LEFT + indent, self.y, line, fontsize=size, color=color, va="top", weight="bold" if bold else None
            )
            self.y -= line_h
        self.y -= gap

    def heading(self, s: str) -> None:
        self._room(0.06)  # never leave a heading alone at the bottom of a page
        self.y -= 0.006
        self.text(s, 9.5, bold=True, gap=0.006)

    def table(self, cols: list[str], rows: list[list[str]], widths: list[float], size: float = 6.8) -> None:
        """Rows are split across pages; the header repeats on each page."""
        rows = rows or [["—"] * len(cols)]
        while rows:
            self._room(ROW_H * 3)
            fit = max(int((self.y - BOTTOM) / ROW_H) - 1, 1)
            chunk, rows = rows[:fit], rows[fit:]
            height = ROW_H * (len(chunk) + 1)
            ax = self.fig.add_axes([LEFT, self.y - height, WIDTH, height])
            ax.axis("off")
            tbl = ax.table(cellText=chunk, colLabels=cols, colWidths=widths, cellLoc="center", bbox=[0, 0, 1, 1])
            tbl.auto_set_font_size(False)
            tbl.set_fontsize(size)
            for (ri, _), cell in tbl.get_celld().items():
                cell.set_edgecolor(GRID)
                if ri == 0:
                    cell.set_text_props(weight="bold", color=INK)
                    cell.set_facecolor(HEADER_BG)
            self.y -= height + 0.008
            if rows:
                self._new_page()


def _why_text(codes: list[Why], lang: Lang) -> str:
    if lang == Lang.UK:
        return ", ".join(WHY_UK.get(c, c) for c in codes) or "збалансований профіль"
    return ", ".join(c.value.replace("_", " ") for c in codes) or "balanced profile"


def _p_text(p: float) -> str:
    return ("< " if p < 0.001 else "= ") + fmt_p(p).lstrip("<")


def build_appendix(run: RunRecord, topic_views: dict[str, pd.Series] | None, full_conclusion: str | None) -> list:
    """Return the appendix pages (matplotlib figures)."""
    lang = run.out_lang
    t = PDF_TEXT[lang]
    flow = Flow(f"{title_of(run)} · {t['app_title']}")
    flow.text(t["app_title"], 13, bold=True, gap=0.01)

    if full_conclusion:
        flow.heading(t["app_full_conclusion"])
        flow.text(full_conclusion)

    if run.ranking:
        flow.heading(t["app_rank"])
        rows = [
            [
                str(r.position),
                r.lang,
                f"{r.score:+.2f}",
                VERDICT[lang][run.results[r.lang].verdict],
                _why_text(r.why, lang),
            ]
            for r in run.ranking
        ]
        flow.table(t["app_rank_cols"], rows, [0.04, 0.07, 0.08, 0.15, 0.66])
        w = run.weights.model_dump()
        flow.text(t["app_rank_note"].format(w=", ".join(f"{k}={v:g}" for k, v in w.items())), 6.8, color=INK2)

    flow.heading(t["app_lang"])
    for l, r in run.results.items():
        flow.text(f"{l} · {edition_name(l, lang)}", 8.2, bold=True, gap=0.002)
        if not r.has_data:
            lines = [t["app_nodata"]]
        else:
            ci = r.yoy_norm_ci90 or (None, None)
            reasons = [reason_text(c, r, lang) for c in r.confidence_reason_codes]
            lines = [
                t["app_yoy"].format(
                    v=pct(r.yoy_norm), lo=pct(ci[0]), hi=pct(ci[1]), raw=pct(r.yoy_raw), prev=pct(r.yoy_norm_prev_year)
                ),
                t["app_trend"].format(
                    tr=pct(r.trend_pct_year),
                    p=_p_text(r.trend_p_value),
                    med=fmt_int(r.median_views_month),
                    vpm=f"{r.views_per_million:.1f}",
                ),
                t["app_conf"].format(verdict=VERDICT[lang][r.verdict], conf=CONFIDENCE[lang][r.confidence]),
                t["app_reasons"] + ("; ".join(reasons) or t["app_reasons_none"]),
            ]
        arts = run.articles.get(l) or {}
        if arts:
            lines.append(t["app_arts"] + ", ".join(arts.values()))
        if r.missing_articles:
            lines.append(t["app_missing"] + ", ".join(r.missing_articles))
        for line in lines:
            flow.text("• " + line, 7, indent=0.015, gap=0.001)
        flow.y -= 0.006

    flow.heading(t["app_lims"])
    for line in limitations(run):
        flow.text("• " + line, 7, color=INK2, gap=0.001)

    views = {l: s for l, s in (topic_views or {}).items() if s is not None}
    if views:
        flow.heading(t["app_monthly"])
        flow.text(t["app_monthly_note"], 6.8, color=INK2)
        months = sorted(set().union(*(s.index for s in views.values())))
        rows = [
            [str(m)] + [fmt_int(views[l][m]) if m in views[l].index and pd.notna(views[l][m]) else "—" for l in views]
            for m in months
        ]
        n = len(views)
        flow.table([t["app_month"], *views], rows, [0.12] + [0.88 / n] * n)
    return flow.pages
