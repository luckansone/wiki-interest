"""Chart (PNG) and A4 PDF report built entirely with matplotlib (no system deps).

Page 1 is a fixed one-page summary; the appendix after it flows onto as many pages as the data needs.

All labels come in Ukrainian or English (`lang`, the same value as `--out-lang`).

DejaVu Sans ships with matplotlib and covers Cyrillic, Polish/Czech diacritics, Vietnamese.
"""

from __future__ import annotations

import textwrap

import matplotlib


matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.backends.backend_pdf import PdfPages  # noqa: E402

from metrics import CONF_UK, FLAG_TEXT_EN, FLAG_TEXT_UK, VERDICT_UK, WHY_UK, fmt_int, pct, reason_text  # noqa: E402


# Validated categorical palette (light mode), assigned in fixed order per language.
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update(
    {
        "pdf.fonttype": 42,
        "font.family": "DejaVu Sans",
        "font.size": 8.5,
        "axes.edgecolor": INK2,
        "axes.labelcolor": INK2,
        "xtick.color": INK2,
        "ytick.color": INK2,
    }
)


VERDICT = {
    "uk": VERDICT_UK,
    "en": {"growing": "growing", "declining": "declining", "stable_or_unclear": "no clear change"},
}
CONF = {"uk": CONF_UK, "en": {"high": "high", "medium": "medium", "low": "low"}}
FLAG_TEXT = {"uk": FLAG_TEXT_UK, "en": FLAG_TEXT_EN}
FLAG_SHORT = {
    "uk": {
        "SHORT_HISTORY": "коротка історія",
        "LOW_VOLUME": "малий обсяг",
        "PROJECT_SHIFT": "зсув трафіку розділу",
        "SPIKE_DRIVEN": "ріст через сплеск",
        "MISSING_ARTICLE": "не всі статті є",
        "TREND_CONFLICT": "суперечить тренду",
    },
    "en": {
        "SHORT_HISTORY": "short history",
        "LOW_VOLUME": "low volume",
        "PROJECT_SHIFT": "wiki-wide traffic shift",
        "SPIKE_DRIVEN": "spike-driven",
        "MISSING_ARTICLE": "some articles missing",
        "TREND_CONFLICT": "contradicts trend",
    },
}
SOURCE = "Wikimedia Pageviews API (per-article, aggregate), Wikidata sitelinks · run_id {rid}"
TXT = {
    "uk": {
        "index_ylabel": "Індекс (перші {h} міс. = 100)",
        "index_title": "Інтерес з поправкою на трафік розділу (тонка лінія — місяць, товста — 3-міс. середнє)",
        "conf": "довіра",
        "yoy_xlabel": "Зміна р/р, % (з поправкою на трафік розділу); лінія — 90% довірчий інтервал",
        "yoy_title": "Річна зміна інтересу",
        "no_articles": "Немає статей теми (не виміряно): ",
        "next": "Досліджувати далі (за рейтингом): ",
        "pct_note": "Відсотки — зміна за рік з поправкою на загальний трафік мовного розділу.",
        "title": "Інтерес до теми: ",
        "sub": "Мовні розділи: {langs} · період {p0} – {p1} ({m} міс.) · дані Wikimedia станом на {f}",
        "demo": "ДЕМО: СИНТЕТИЧНІ ДАНІ, НЕ РЕАЛЬНІ ПЕРЕГЛЯДИ",
        "conclusion": "Висновок",
        "cols": [
            "Мова",
            "Статей",
            "Перегл./міс.\n(медіана)",
            "На 1 млн\nперегл. розділу",
            "Р/р\nсирий",
            "Р/р з поправкою\n[90% ДІ]",
            "p\nтренду",
            "Вердикт",
            "Довіра",
        ],
        "lim_main": "Перегляди — сигнал інтересу, не платоспроможності; мовний розділ ≠ країна (en читають усюди).",
        "lim_generic": [
            "Лише перегляди людей (agent=user); нерозпізнані боти та редиректи не враховані (MVP).",
            "Поправка на трафік розділу прибирає загальні зсуви (напр., перехід читачів між мовами).",
        ],
        "lim_nodata": "{langs}: у розділі немає жодної статті теми — інтерес не виміряно.",
        "lim_title": "Припущення та обмеження",
        "lim_more": "• … повний перелік — у додатку",
        "foot": "Статті: {arts}\nДжерело: " + SOURCE,
        "page": "с. {i} з {n}",
        "app_title": "Додаток: деталі",
        "app_rank": "Рейтинг мовних розділів",
        "app_rank_cols": ["#", "Мова", "Бал", "Вердикт", "Чому"],
        "app_rank_note": "Бал = ваги × (ріст, частка інтересу, довіра): {w}. Рейтинг відносний до обраного набору мов.",
        "app_lang": "Деталі за мовами",
        "app_yoy": "Р/р з поправкою {v} (90% ДІ {lo}…{hi}); сирі перегляди {raw}; та сама зміна роком раніше {prev}",
        "app_trend": "Довгостроковий тренд {tr}/рік, p {p}; медіана {med} перегл./міс.; {vpm} на 1 млн перегл. розділу",
        "app_conf": "Вердикт: {verdict}; довіра {conf}",
        "app_reasons": "Чому така довіра: ",
        "app_reasons_none": "усі перевірки пройдено",
        "app_arts": "Статті: ",
        "app_missing": "Немає в розділі: ",
        "app_nodata": "Статті на цю тему немає — інтерес не виміряно (це не нульовий інтерес).",
        "app_full_conclusion": "Повний висновок",
        "app_lims": "Усі припущення та обмеження",
        "app_monthly": "Перегляди статей теми за місяцями (сума, лише люди)",
        "app_month": "Місяць",
        "app_monthly_note": "Сирі перегляди без поправки на трафік розділу. Ті самі дані — у series.csv.",
    },
    "en": {
        "index_ylabel": "Index (first {h} months = 100)",
        "index_title": "Traffic-adjusted interest (thin line: monthly, thick: 3-month average)",
        "conf": "confidence",
        "yoy_xlabel": "Year-over-year change, % (adjusted for edition traffic); line: 90% confidence interval",
        "yoy_title": "Year-over-year change in interest",
        "no_articles": "No articles on the topic (not measured): ",
        "next": "Research next (by ranking): ",
        "pct_note": "Percentages: change over the last year, adjusted for the whole language edition's traffic.",
        "title": "Interest in the topic: ",
        "sub": "Language editions: {langs} · period {p0} – {p1} ({m} months) · Wikimedia data as of {f}",
        "demo": "DEMO: SYNTHETIC DATA, NOT REAL PAGEVIEWS",
        "conclusion": "Conclusion",
        "cols": [
            "Lang",
            "Articles",
            "Views/month\n(median)",
            "Per 1M\nedition views",
            "YoY\nraw",
            "YoY adjusted\n[90% CI]",
            "Trend\np",
            "Verdict",
            "Confidence",
        ],
        "lim_main": "Pageviews signal interest, not willingness to pay; a language edition is not a country "
        "(en is read everywhere).",
        "lim_generic": [
            "Human pageviews only (agent=user); unrecognized bots and redirects are not counted (MVP).",
            "The edition-traffic adjustment removes wiki-wide shifts (e.g. readers moving between languages).",
        ],
        "lim_nodata": "{langs}: the edition has no article on this topic, so interest was not measured.",
        "lim_title": "Assumptions and limitations",
        "lim_more": "• … full list in the appendix",
        "foot": "Articles: {arts}\nSource: " + SOURCE,
        "page": "page {i} of {n}",
        "app_title": "Appendix: details",
        "app_rank": "Ranking of language editions",
        "app_rank_cols": ["#", "Lang", "Score", "Verdict", "Why"],
        "app_rank_note": "Score = weights × (growth, share of interest, confidence): {w}. "
        "The ranking is relative to the chosen set of languages.",
        "app_lang": "Details by language",
        "app_yoy": "YoY adjusted {v} (90% CI {lo}…{hi}); raw pageviews {raw}; same change a year earlier {prev}",
        "app_trend": "Long-run trend {tr}/year, p {p}; median {med} views/month; {vpm} per 1M edition views",
        "app_conf": "Verdict: {verdict}; confidence {conf}",
        "app_reasons": "Why this confidence: ",
        "app_reasons_none": "all checks passed",
        "app_arts": "Articles: ",
        "app_missing": "Missing in this edition: ",
        "app_nodata": "No article on this topic, so interest was not measured (this is not zero interest).",
        "app_full_conclusion": "Full conclusion",
        "app_lims": "All assumptions and limitations",
        "app_monthly": "Monthly pageviews of the topic articles (sum, humans only)",
        "app_month": "Month",
        "app_monthly_note": "Raw pageviews, not adjusted for edition traffic. The same data is in series.csv.",
    },
}


def _index_series(series_vpm: dict, h: int) -> dict:
    """Traffic-adjusted interest indexed so that the mean of the first h months = 100."""
    out = {}
    for lang, s in series_vpm.items():
        base = float(np.mean(s.to_numpy()[:h]))
        out[lang] = s / base * 100 if base > 0 else s * 0
    return out


def _style(ax):
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def draw_index(ax, series_vpm: dict, colors: dict, h: int, lang: str = "uk"):
    t = TXT[lang]
    idx = _index_series(series_vpm, h)
    for lang, s in idx.items():
        x = s.index.to_timestamp()
        ax.plot(x, s.values, color=colors[lang], linewidth=0.8, alpha=0.35)
        smooth = s.rolling(3, min_periods=1).mean()
        ax.plot(x, smooth.values, color=colors[lang], linewidth=2, label=lang)
        if len(idx) <= 4:  # direct labels at line end
            ax.annotate(
                lang,
                (x[-1], smooth.values[-1]),
                xytext=(4, 0),
                textcoords="offset points",
                color=INK,
                fontsize=8,
                va="center",
            )
    ax.axhline(100, color=INK2, linewidth=0.6, linestyle=":")
    ax.set_ylabel(t["index_ylabel"].format(h=h))
    ax.set_title(
        t["index_title"],
        loc="left",
        fontsize=9,
        color=INK,
    )
    ax.legend(frameon=False, ncol=min(len(idx), 8), fontsize=7.5, loc="upper left")
    _style(ax)


def draw_yoy(ax, results: dict, colors: dict, lang: str = "uk"):
    t = TXT[lang]
    langs = [l for l, r in results.items() if r.get("yoy_norm") is not None][::-1]
    for i, l in enumerate(langs):
        r = results[l]
        ci = r["yoy_norm_ci90"] or [r["yoy_norm"], r["yoy_norm"]]
        ax.plot([ci[0] * 100, ci[1] * 100], [i, i], color=colors[l], linewidth=2, solid_capstyle="round")
        ax.plot(
            r["yoy_norm"] * 100, i, "o", color=colors[l], markersize=7, markeredgecolor="white", markeredgewidth=1.5
        )
        ax.annotate(
            f"{pct(r['yoy_norm'])}  {VERDICT[lang][r['verdict']]}, {t['conf']} {CONF[lang][r['confidence']]}",
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
    lo = min([0] + [(results[l]["yoy_norm_ci90"] or [results[l]["yoy_norm"]])[0] * 100 for l in langs])
    hi = max([0] + [(results[l]["yoy_norm_ci90"] or [0, results[l]["yoy_norm"]])[-1] * 100 for l in langs])
    span = max(hi - lo, 10)
    ax.set_xlim(lo - 0.08 * span, hi + 0.08 * span)
    ax.set_ylim(-0.7, len(langs) - 0.3)
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="x", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def save_chart_png(path, series_vpm, results, h, lang: str = "uk"):
    colors = {l: PALETTE[i % len(PALETTE)] for i, l in enumerate(results)}
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(8, 6.5), gridspec_kw={"height_ratios": [3, 2]})
    draw_index(a1, series_vpm, colors, h, lang)
    draw_yoy(a2, results, colors, lang)
    fig.tight_layout()
    pos = a2.get_position()  # leave room on the right for the aligned text labels
    a2.set_position([pos.x0, pos.y0, pos.width * 0.66, pos.height])
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _wrap(text: str, width: int) -> str:
    return "\n".join(textwrap.fill(p, width) for p in text.split("\n"))


def pdf_conclusion(run: dict, lang: str = "uk") -> str:
    """Short, grouped conclusion (the full per-language detail lives in the table)."""
    t = TXT[lang]
    groups = {"growing": [], "declining": [], "stable_or_unclear": []}
    for l, r in run["results"].items():
        if r.get("status") == "no_data":
            continue
        tag = f"{l} ({pct(r['yoy_norm'])}, {t['conf']} {CONF[lang][r['confidence']]}"
        tag += ", " + ", ".join(FLAG_SHORT[lang][f] for f in r["flags"]) + ")" if r["flags"] else ")"
        groups[r["verdict"]].append(tag)
    lines = [f"{VERDICT[lang][v].capitalize()}: " + "; ".join(t) + "." for v, t in groups.items() if t]
    nodata = [l for l, r in run["results"].items() if r.get("status") == "no_data"]
    if nodata:
        lines.append(t["no_articles"] + ", ".join(nodata) + ".")
    if len(run["ranking"]) > 1:
        lines.append(t["next"] + ", ".join(r["lang"] for r in run["ranking"][:3]) + ".")
    lines.append(t["pct_note"])
    return "\n".join(lines)


def _limitations(run: dict, lang: str) -> list[str]:
    """List caveats: the fixed one, then the flags actually raised, then generic ones (cut first on page 1)."""
    t = TXT[lang]
    lim = [t["lim_main"]]
    by_flag: dict[str, list[str]] = {}
    for l, r in run["results"].items():
        for f in r["flags"] if r.get("status") != "no_data" else []:
            by_flag.setdefault(f, []).append(l)
    for f, ls in by_flag.items():
        lim.append(f"{', '.join(ls)}: {FLAG_TEXT[lang][f]}.")
    nodata = [l for l, r in run["results"].items() if r.get("status") == "no_data"]
    if nodata:
        lim.append(t["lim_nodata"].format(langs=", ".join(nodata)))
    return lim + t["lim_generic"]


def fmt_p(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.3f}"


def save_pdf(path, run: dict, series_vpm: dict, h: int, topic_views: dict | None = None):
    """Page 1: header, conclusion, 2 charts, metrics table, limitations, footer. Then the appendix.

    topic_views: {lang: monthly pageviews Series} for the appendix table (skipped when None).
    """
    lang = run.get("out_lang", "uk")
    t = TXT[lang]
    results = {l: r for l, r in run["results"].items() if r.get("status") != "no_data"}
    colors = {l: PALETTE[i % len(PALETTE)] for i, l in enumerate(results)}
    fig = plt.figure(figsize=(8.27, 11.69))
    L, W = 0.07, 0.86

    title = run.get("question") or t["title"] + ", ".join(r["label"] for r in run["topics"])
    fig.text(L, 0.965, _wrap(title, 80), fontsize=13, weight="bold", color=INK, va="top")
    sub = t["sub"].format(
        langs=", ".join(run["langs"]), p0=run["period"][0], p1=run["period"][1], m=run["months"], f=run["fetched_on"]
    )
    fig.text(L, 0.925, sub, fontsize=8, color=INK2, va="top")
    if run.get("synthetic"):
        fig.text(
            0.5,
            0.905,
            t["demo"],
            ha="center",
            fontsize=10,
            color="#e34948",
            weight="bold",
        )

    full_conclusion = run.get("conclusion") or pdf_conclusion(run, lang)
    conclusion = full_conclusion if len(full_conclusion) <= 700 else full_conclusion[:699] + "…"
    fig.text(L, 0.89, t["conclusion"], fontsize=10, weight="bold", color=INK, va="top")
    fig.text(L, 0.872, _wrap(conclusion, 112), fontsize=8.2, color=INK, va="top", linespacing=1.35)

    a1 = fig.add_axes([L + 0.04, 0.545, W - 0.07, 0.215])
    draw_index(a1, {l: series_vpm[l] for l in results}, colors, h, lang)
    a2 = fig.add_axes([L + 0.04, 0.345, (W - 0.07) * 0.64, 0.145])
    draw_yoy(a2, results, colors, lang)

    # Metrics table
    cols = t["cols"]
    rows = []
    for l, r in results.items():
        ci = r["yoy_norm_ci90"]
        rows.append(
            [
                l,
                str(len(run["articles"][l])),
                fmt_int(r["median_views_month"]),
                f"{r['views_per_million']:.1f}",
                pct(r["yoy_raw"]),
                f"{pct(r['yoy_norm'])} [{pct(ci[0])}…{pct(ci[1])}]" if ci else pct(r["yoy_norm"]),
                fmt_p(r["trend_p_value"]),
                VERDICT[lang][r["verdict"]],
                CONF[lang][r["confidence"]],
            ]
        )
    ta = fig.add_axes([L, 0.135, W, 0.155])
    ta.axis("off")
    widths = [0.06, 0.07, 0.11, 0.12, 0.08, 0.2, 0.08, 0.16, 0.1]
    tbl = ta.table(cellText=rows, colLabels=cols, loc="upper center", cellLoc="center", colWidths=widths)
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(6.8)
    tbl.scale(1, 1.25)
    for (ri, _), cell in tbl.get_celld().items():
        cell.set_edgecolor(GRID)
        if ri == 0:
            cell.set_height(cell.get_height() * 1.8)
            cell.set_text_props(weight="bold", color=INK)
            cell.set_facecolor("#f3f2ee")

    lim = _limitations(run, lang)
    # place the block right under the table, whatever its height (depends on the number of languages)
    bb = tbl.get_window_extent(fig.canvas.get_renderer()).transformed(fig.transFigure.inverted())
    y0 = bb.y0 - 0.015
    fig.text(L, y0, t["lim_title"], fontsize=9, weight="bold", color=INK, va="top")
    lim_txt = _wrap("\n".join("• " + x for x in lim), 130).split("\n")
    max_lines = max(int((y0 - 0.016 - 0.045) / 0.0105), 3)  # stop above the footer
    if len(lim_txt) > max_lines:
        lim_txt = lim_txt[: max_lines - 1] + [t["lim_more"]]
    fig.text(L, y0 - 0.016, "\n".join(lim_txt), fontsize=6.6, color=INK2, va="top", linespacing=1.3)

    arts = "; ".join(f"{l}: {', '.join(v.values()) or '—'}" for l, v in run["articles"].items())
    foot = t["foot"].format(arts=arts, rid=run["run_id"])
    fig.text(L, 0.022, _wrap(foot, 150), fontsize=5.8, color=INK2, va="bottom")

    pages = [fig] + _appendix(run, lang, topic_views, full_conclusion if len(full_conclusion) > 700 else None)
    for i, page in enumerate(pages, 1):
        page.text(1 - L, 0.008, t["page"].format(i=i, n=len(pages)), fontsize=6, color=INK2, ha="right")
    with PdfPages(path) as pdf:
        for page in pages:
            pdf.savefig(page)
            plt.close(page)


# ---------------------------------------------------------------- appendix (flowing layout)
PAGE_W, PAGE_H = 8.27, 11.69
TOP, BOTTOM, ROW_H = 0.955, 0.04, 0.0165  # figure fractions; ROW_H = one table row


class _Flow:
    """Places text and tables top-down and starts a new A4 page when the current one is full."""

    def __init__(self, header: str):
        self.header, self.pages = header, []
        self._new_page()

    def _new_page(self):
        self.fig = plt.figure(figsize=(PAGE_W, PAGE_H))
        self.fig.text(0.07, 0.975, self.header, fontsize=7, color=INK2, va="top")
        self.pages.append(self.fig)
        self.y = TOP

    def _room(self, height: float):
        if self.y - height < BOTTOM and self.y < TOP:
            self._new_page()

    def text(self, s: str, size: float = 7.5, bold: bool = False, color: str = INK, indent: float = 0.0, gap=0.004):
        chars = int((0.86 - indent) * PAGE_W * 72 / (0.56 * size))  # ~average DejaVu glyph width
        line_h = size * 1.4 / 72 / PAGE_H
        hang = "   " if s.startswith("• ") else ""  # wrapped bullet lines align with the text, not the bullet
        for line in "\n".join(textwrap.fill(p, chars, subsequent_indent=hang) for p in s.split("\n")).split("\n"):
            self._room(line_h)
            self.fig.text(
                0.07 + indent, self.y, line, fontsize=size, color=color, va="top", weight="bold" * bold or None
            )
            self.y -= line_h
        self.y -= gap

    def heading(self, s: str):
        self._room(0.06)  # never leave a heading alone at the bottom of a page
        self.y -= 0.006
        self.text(s, 9.5, bold=True, gap=0.006)

    def table(self, cols: list[str], rows: list[list[str]], widths: list[float], size: float = 6.8):
        """Rows are split across pages; the header repeats on each page."""
        rows = rows or [["—"] * len(cols)]
        while rows:
            self._room(ROW_H * 3)
            fit = max(int((self.y - BOTTOM) / ROW_H) - 1, 1)
            chunk, rows = rows[:fit], rows[fit:]
            height = ROW_H * (len(chunk) + 1)
            ax = self.fig.add_axes([0.07, self.y - height, 0.86, height])
            ax.axis("off")
            tbl = ax.table(cellText=chunk, colLabels=cols, colWidths=widths, cellLoc="center", bbox=[0, 0, 1, 1])
            tbl.auto_set_font_size(False)
            tbl.set_fontsize(size)
            for (ri, _), cell in tbl.get_celld().items():
                cell.set_edgecolor(GRID)
                if ri == 0:
                    cell.set_text_props(weight="bold", color=INK)
                    cell.set_facecolor("#f3f2ee")
            self.y -= height + 0.008
            if rows:
                self._new_page()


def _why_text(codes: list[str], lang: str) -> str:
    if lang == "uk":
        return ", ".join(WHY_UK.get(c, c) for c in codes) or "збалансований профіль"
    return ", ".join(c.replace("_", " ") for c in codes) or "balanced profile"


def _appendix(run: dict, lang: str, topic_views: dict | None, full_conclusion: str | None) -> list:
    from wiki_api import edition_name  # local import, as in metrics.summary_text

    t = TXT[lang]
    title = run.get("question") or t["title"] + ", ".join(r["label"] for r in run["topics"])
    flow = _Flow(f"{title} · {t['app_title']}")
    flow.text(t["app_title"], 13, bold=True, gap=0.01)

    if full_conclusion:
        flow.heading(t["app_full_conclusion"])
        flow.text(full_conclusion)

    if run["ranking"]:
        flow.heading(t["app_rank"])
        rows = [
            [
                str(r["position"]),
                r["lang"],
                f"{r['score']:+.2f}" if r.get("score") is not None else "—",
                VERDICT[lang][run["results"][r["lang"]]["verdict"]],
                _why_text(r["why"], lang),
            ]
            for r in run["ranking"]
        ]
        flow.table(t["app_rank_cols"], rows, [0.04, 0.07, 0.08, 0.15, 0.66])
        w = run.get("weights") or {}
        flow.text(t["app_rank_note"].format(w=", ".join(f"{k}={v:g}" for k, v in w.items())), 6.8, color=INK2)

    flow.heading(t["app_lang"])
    for l, r in run["results"].items():
        flow.text(f"{l} · {edition_name(l, lang)}", 8.2, bold=True, gap=0.002)
        arts = run["articles"].get(l) or {}
        missing = r.get("missing_articles") or []
        if r.get("status") == "no_data":
            lines = [t["app_nodata"]]
        else:
            ci = r["yoy_norm_ci90"] or [None, None]
            reasons = [reason_text(c, r, lang) for c in r.get("confidence_reason_codes", [])]
            lines = [
                t["app_yoy"].format(
                    v=pct(r["yoy_norm"]),
                    lo=pct(ci[0]),
                    hi=pct(ci[1]),
                    raw=pct(r["yoy_raw"]),
                    prev=pct(r.get("yoy_norm_prev_year")),
                ),
                t["app_trend"].format(
                    tr=pct(r["trend_pct_year"]),
                    p=("< " if r["trend_p_value"] < 0.001 else "= ") + fmt_p(r["trend_p_value"]).lstrip("<"),
                    med=fmt_int(r["median_views_month"]),
                    vpm=f"{r['views_per_million']:.1f}",
                ),
                t["app_conf"].format(verdict=VERDICT[lang][r["verdict"]], conf=CONF[lang][r["confidence"]]),
                t["app_reasons"] + ("; ".join(reasons) or t["app_reasons_none"]),
            ]
        if arts:
            lines.append(t["app_arts"] + ", ".join(arts.values()))
        if missing:
            lines.append(t["app_missing"] + ", ".join(missing))
        for line in lines:
            flow.text("• " + line, 7, indent=0.015, gap=0.001)
        flow.y -= 0.006

    flow.heading(t["app_lims"])
    for line in _limitations(run, lang):
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
        flow.table([t["app_month"]] + list(views), rows, [0.12] + [0.88 / n] * n)
    return flow.pages
