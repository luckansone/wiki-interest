"""`summary_text`: the ready paragraph with all key numbers that the agent bases its answer on."""

from __future__ import annotations

from wiki_interest.analysis.metrics import fmt_int, pct, reason_text
from wiki_interest.data.languages import edition_name
from wiki_interest.enums import Lang
from wiki_interest.models import LangResult, RankRow
from wiki_interest.text import CONFIDENCE, DISCLAIMER, VERDICT, WHY_UK


def summary_text(results: dict[str, LangResult], ranking: list[RankRow], lang: Lang = Lang.UK) -> str:
    lines = []
    for l, r in results.items():
        ed = f"{l} ({edition_name(l, lang)})"
        if not r.has_data:
            lines.append(
                f"{ed}: статті на цю тему немає — інтерес не виміряно (це не означає нульовий "
                f"інтерес; можна спробувати ширшу тему)."
                if lang == Lang.UK
                else f"{ed}: no article on this topic — interest not measured (not the same as zero "
                f"interest; a broader topic may exist)."
            )
            continue
        ci, h = r.yoy_norm_ci90, r.yoy_window_months
        reasons = [reason_text(c, r, lang) for c in r.confidence_reason_codes]
        if lang == Lang.UK:
            s = (
                f"{ed}: {VERDICT[lang][r.verdict]} — {pct(r.yoy_norm)} за останні {h} міс. проти попередніх {h} "
                f"з поправкою на трафік розділу (90% ДІ {pct(ci[0]) if ci else 'н/д'}…{pct(ci[1]) if ci else 'н/д'}; "
                f"сирі перегляди {pct(r.yoy_raw)}), медіана {fmt_int(r.median_views_month)} переглядів/міс.; "
                f"довіра {CONFIDENCE[lang][r.confidence]}"
            )
            if r.yoy_norm_prev_year is not None:
                s += f"; та сама зміна роком раніше {pct(r.yoy_norm_prev_year)}"
        else:
            # English keeps the machine values (growing / stable_or_unclear), as SKILL.md documents them
            s = (
                f"{ed}: {r.verdict.value} — {pct(r.yoy_norm)} last {h} months vs previous {h}, traffic-adjusted "
                f"(90% CI {pct(ci[0]) if ci else 'n/a'}..{pct(ci[1]) if ci else 'n/a'}; raw {pct(r.yoy_raw)}), "
                f"median {r.median_views_month:,} views/month; confidence {r.confidence.value}"
            )
            if r.yoy_norm_prev_year is not None:
                s += f"; same change a year earlier {pct(r.yoy_norm_prev_year)}"
        if reasons:
            s += " (" + "; ".join(reasons) + ")"
        lines.append(s + ".")
    if len(ranking) > 1:
        top = ranking[:3]
        if lang == Lang.UK:
            parts = []
            for row in top:
                why = ", ".join(WHY_UK[w] for w in row.why if w in WHY_UK) or "збалансований профіль"
                parts.append(f"{row.lang} ({why})")
            lines.append("Рейтинг для подальшого дослідження: " + "; ".join(parts) + ".")
        else:
            lines.append(
                "Ranking to investigate next: "
                + "; ".join(f"{row.lang} ({', '.join(w.value for w in row.why) or 'balanced'})" for row in top)
                + "."
            )
    lines.append(DISCLAIMER[lang])
    return "\n".join(lines)
