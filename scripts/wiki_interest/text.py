"""Every human-readable string, in Ukrainian and English, keyed by `Lang` and the enums.

Code never builds UI text inline: it looks it up here, so both languages stay in sync.
"""

from __future__ import annotations

from wiki_interest.config import THRESHOLDS
from wiki_interest.enums import Confidence, Flag, Lang, Reason, Verdict, Why


VERDICT: dict[Lang, dict[Verdict, str]] = {
    Lang.UK: {Verdict.GROWING: "зростає", Verdict.DECLINING: "спадає", Verdict.STABLE_OR_UNCLEAR: "без чіткої зміни"},
    Lang.EN: {Verdict.GROWING: "growing", Verdict.DECLINING: "declining", Verdict.STABLE_OR_UNCLEAR: "no clear change"},
}
CONFIDENCE: dict[Lang, dict[Confidence, str]] = {
    Lang.UK: {Confidence.HIGH: "висока", Confidence.MEDIUM: "середня", Confidence.LOW: "низька"},
    Lang.EN: {Confidence.HIGH: "high", Confidence.MEDIUM: "medium", Confidence.LOW: "low"},
}
FLAG_TEXT: dict[Lang, dict[Flag, str]] = {
    Lang.UK: {
        Flag.SHORT_HISTORY: "менше 24 міс. даних: сезонність не врахована",
        Flag.LOW_VOLUME: f"малий обсяг (медіана < {THRESHOLDS.low_volume_median} переглядів/міс.)",
        Flag.PROJECT_SHIFT: "сирий і нормалізований ріст розходяться: зсув трафіку всього розділу",
        Flag.SPIKE_DRIVEN: "ріст дає один місяць-сплеск",
        Flag.MISSING_ARTICLE: "частини статей теми немає в цьому розділі",
        Flag.TREND_CONFLICT: "зміна за останній рік суперечить значущому довгостроковому тренду (відскок або розворот)",
    },
    Lang.EN: {
        Flag.SHORT_HISTORY: "less than 24 months of data: seasonality not controlled",
        Flag.LOW_VOLUME: f"low volume (median < {THRESHOLDS.low_volume_median} views/month)",
        Flag.PROJECT_SHIFT: "raw and traffic-adjusted growth disagree: whole-wiki traffic shift",
        Flag.SPIKE_DRIVEN: "growth driven by a single-month spike",
        Flag.MISSING_ARTICLE: "some topic articles do not exist in this language",
        Flag.TREND_CONFLICT: "last-year change contradicts the significant long-run trend (rebound or reversal)",
    },
}
FLAG_SHORT: dict[Lang, dict[Flag, str]] = {
    Lang.UK: {
        Flag.SHORT_HISTORY: "коротка історія",
        Flag.LOW_VOLUME: "малий обсяг",
        Flag.PROJECT_SHIFT: "зсув трафіку розділу",
        Flag.SPIKE_DRIVEN: "ріст через сплеск",
        Flag.MISSING_ARTICLE: "не всі статті є",
        Flag.TREND_CONFLICT: "суперечить тренду",
    },
    Lang.EN: {
        Flag.SHORT_HISTORY: "short history",
        Flag.LOW_VOLUME: "low volume",
        Flag.PROJECT_SHIFT: "wiki-wide traffic shift",
        Flag.SPIKE_DRIVEN: "spike-driven",
        Flag.MISSING_ARTICLE: "some articles missing",
        Flag.TREND_CONFLICT: "contradicts trend",
    },
}
# {p} = trend p-value, {tr} = trend %/year
REASON_TEXT: dict[Lang, dict[Reason, str]] = {
    Lang.UK: {
        Reason.CI_CROSSES_ZERO: "90% ДІ зміни з поправкою містить 0",
        Reason.NOT_SIGNIFICANT: "довгостроковий тренд статистично незначущий (p={p:.2f})",
        Reason.TREND_VS_YEAR: "довгостроковий тренд {tr}/рік значущий, але зміну за останній рік не підтверджено",
    },
    Lang.EN: {
        Reason.CI_CROSSES_ZERO: "90% CI of the adjusted change includes 0",
        Reason.NOT_SIGNIFICANT: "long-run trend not statistically significant (p={p:.2f})",
        Reason.TREND_VS_YEAR: "long-run trend {tr}/year is significant, but the last-year change is not confirmed",
    },
}
WHY_UK: dict[Why, str] = {
    Why.FASTEST_GROWTH: "найшвидший ріст",
    Why.HIGHEST_SHARE_OF_INTEREST: "найвища частка інтересу",
    Why.BEST_TREND_IN_SET: "найкраща динаміка серед обраних, але ріст не підтверджено",
    Why.GROWING: "зростає",
    Why.DECLINING: "спадає",
    Why.SPIKE_DRIVEN: "але ріст через сплеск",
    Why.PROJECT_SHIFT: "зсув трафіку розділу",
    Why.LOW_VOLUME: "малий обсяг",
    Why.MISSING_ARTICLE: "не всі статті теми є",
    Why.SHORT_HISTORY: "коротка історія",
    Why.TREND_CONFLICT: "суперечить довгостроковому тренду",
}
DISCLAIMER: dict[Lang, str] = {
    Lang.UK: (
        "Перегляди Wikipedia — сигнал інтересу, а не готовності платити; мовний розділ ≠ країна. "
        "Використовуйте як підказку, що перевіряти далі."
    ),
    Lang.EN: (
        "Wikipedia pageviews signal interest, not willingness to pay; a language edition is not "
        "a country. Use this to pick what to validate next."
    ),
}
NOT_AVAILABLE: dict[Lang, str] = {Lang.UK: "н/д", Lang.EN: "n/a"}

SOURCE = "Wikimedia Pageviews API (per-article, aggregate), Wikidata sitelinks · run_id {rid}"
PDF_TEXT: dict[str, dict] = {
    Lang.UK: {
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
    Lang.EN: {
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
