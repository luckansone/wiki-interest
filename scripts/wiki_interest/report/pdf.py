"""The PDF report: page 1 is a one-page summary; the appendix follows on as many pages as needed."""

from __future__ import annotations

import re
import warnings

import pandas as pd
from loguru import logger
from matplotlib.backends.backend_pdf import PdfPages

from wiki_interest.models import RunRecord
from wiki_interest.report.appendix import build_appendix
from wiki_interest.report.content import CONCLUSION_MAX, auto_conclusion
from wiki_interest.report.style import INK2, LEFT, plt
from wiki_interest.report.summary_page import draw_summary_page
from wiki_interest.text import PDF_TEXT


GLYPH_RE = re.compile(r"Glyph (\d+) .*missing from font")


def save_pdf(path, run: RunRecord, series_vpm: dict[str, pd.Series], topic_views: dict[str, pd.Series] | None = None):
    """Write the report. `topic_views` (monthly pageviews per language) fills the appendix table."""
    t = PDF_TEXT[run.out_lang]
    full = run.conclusion or auto_conclusion(run)
    fits = len(full) <= CONCLUSION_MAX
    page1 = draw_summary_page(run, series_vpm, full if fits else full[: CONCLUSION_MAX - 1] + "…")
    pages = [page1, *build_appendix(run, topic_views, None if fits else full)]
    for i, page in enumerate(pages, 1):
        page.text(1 - LEFT, 0.008, t["page"].format(i=i, n=len(pages)), fontsize=6, color=INK2, ha="right")
    with warnings.catch_warnings(record=True) as caught, PdfPages(path) as pdf:
        warnings.simplefilter("always")
        for page in pages:
            pdf.savefig(page)
            plt.close(page)
    log = logger.bind(scope="report")
    # matplotlib warns once per glyph: "Glyph 22825 (...) missing from font(s) DejaVu Sans."
    missing = sorted({chr(int(m.group(1))) for w in caught if (m := GLYPH_RE.search(str(w.message)))})
    if missing:  # one readable line instead of one warning per glyph
        log.warning(f"PDF font has no glyph for {''.join(missing[:12])}; these characters show as empty boxes")
    log.info(f"PDF: {len(pages)} pages → {path}")
