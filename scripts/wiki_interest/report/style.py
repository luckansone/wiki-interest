"""matplotlib setup shared by the chart and the PDF. Importing this module selects the Agg backend.

DejaVu Sans ships with matplotlib and covers Cyrillic, Polish/Czech diacritics, Vietnamese.
It has no CJK glyphs, so Chinese/Japanese/Korean titles show as empty boxes.
"""

from __future__ import annotations

import textwrap

import matplotlib


matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402


# Validated categorical palette (light mode), assigned in fixed order per language.
PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
INK, INK2, GRID, HEADER_BG, ALERT = "#0b0b0b", "#52514e", "#e4e3df", "#f3f2ee", "#e34948"
PAGE_W, PAGE_H = 8.27, 11.69  # A4, inches
LEFT, WIDTH = 0.07, 0.86  # page margins as figure fractions

plt.rcParams.update(
    {
        "pdf.fonttype": 42,  # embed TrueType, so the PDF text can be extracted
        "font.family": "DejaVu Sans",
        "font.size": 8.5,
        "axes.edgecolor": INK2,
        "axes.labelcolor": INK2,
        "xtick.color": INK2,
        "ytick.color": INK2,
    }
)


def colors_for(langs) -> dict[str, str]:
    return {l: PALETTE[i % len(PALETTE)] for i, l in enumerate(langs)}


def wrap(text: str, width: int, hang: str = "") -> str:
    """Wrap each paragraph to `width` chars; `hang` indents the continuation lines."""
    return "\n".join(textwrap.fill(p, width, subsequent_indent=hang) for p in text.split("\n"))


def fmt_p(p: float) -> str:
    return "<0.001" if p < 0.001 else f"{p:.3f}"
