"""Text blocks of the report that page 1 and the appendix share."""

from __future__ import annotations

from wiki_interest.analysis.metrics import pct
from wiki_interest.enums import Lang, Verdict
from wiki_interest.models import RunRecord
from wiki_interest.text import CONFIDENCE, FLAG_SHORT, FLAG_TEXT, PDF_TEXT, VERDICT


CONCLUSION_MAX = 700  # characters that fit on page 1; longer text goes to the appendix in full


def title_of(run: RunRecord) -> str:
    return run.question or PDF_TEXT[run.out_lang]["title"] + ", ".join(t.label for t in run.topics)


def auto_conclusion(run: RunRecord) -> str:
    """Short conclusion grouped by verdict (the full per-language detail lives in the tables)."""
    lang = run.out_lang
    t = PDF_TEXT[lang]
    groups: dict[Verdict, list[str]] = {v: [] for v in Verdict}
    for l, r in run.measured.items():
        tag = f"{l} ({pct(r.yoy_norm)}, {t['conf']} {CONFIDENCE[lang][r.confidence]}"
        tag += ", " + ", ".join(FLAG_SHORT[lang][f] for f in r.flags) + ")" if r.flags else ")"
        groups[r.verdict].append(tag)
    lines = [f"{VERDICT[lang][v].capitalize()}: " + "; ".join(tags) + "." for v, tags in groups.items() if tags]
    if run.no_data:
        lines.append(t["no_articles"] + ", ".join(run.no_data) + ".")
    if len(run.ranking) > 1:
        lines.append(t["next"] + ", ".join(r.lang for r in run.ranking[:3]) + ".")
    lines.append(t["pct_note"])
    return "\n".join(lines)


def limitations(run: RunRecord) -> list[str]:
    """List the fixed caveat, the flags actually raised, then generic ones (page 1 cuts from the end)."""
    lang: Lang = run.out_lang
    t = PDF_TEXT[lang]
    lim = [t["lim_main"]]
    by_flag: dict = {}
    for l, r in run.measured.items():
        for f in r.flags:
            by_flag.setdefault(f, []).append(l)
    for f, langs in by_flag.items():
        lim.append(f"{', '.join(langs)}: {FLAG_TEXT[lang][f]}.")
    if run.no_data:
        lim.append(t["lim_nodata"].format(langs=", ".join(run.no_data)))
    return lim + t["lim_generic"]
