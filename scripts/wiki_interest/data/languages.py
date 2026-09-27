"""Wikipedia language codes: aliases, Wikidata site ids and human edition names."""

from __future__ import annotations

import re

from wiki_interest.enums import Lang
from wiki_interest.errors import UnknownLanguageError


# alias -> Wikipedia language code. Codes themselves are always accepted.
_LANG_NAMES = {
    "en": ["english", "англійська"],
    "uk": ["ukrainian", "українська"],
    "pl": ["polish", "польська"],
    "cs": ["czech", "чеська"],
    "sk": ["slovak", "словацька"],
    "de": ["german", "німецька"],
    "fr": ["french", "французька"],
    "es": ["spanish", "іспанська"],
    "it": ["italian", "італійська"],
    "pt": ["portuguese", "португальська"],
    "ro": ["romanian", "румунська"],
    "hu": ["hungarian", "угорська"],
    "bg": ["bulgarian", "болгарська"],
    "hr": ["croatian", "хорватська"],
    "sr": ["serbian", "сербська"],
    "sl": ["slovenian", "словенська"],
    "lt": ["lithuanian", "литовська"],
    "lv": ["latvian", "латиська"],
    "et": ["estonian", "естонська"],
    "fi": ["finnish", "фінська"],
    "sv": ["swedish", "шведська"],
    "no": ["norwegian", "норвезька"],
    "da": ["danish", "данська"],
    "nl": ["dutch", "нідерландська"],
    "el": ["greek", "грецька"],
    "tr": ["turkish", "турецька"],
    "ru": ["russian", "російська"],
    "be": ["belarusian", "білоруська"],
    "kk": ["kazakh", "казахська"],
    "ka": ["georgian", "грузинська"],
    "hy": ["armenian", "вірменська"],
    "az": ["azerbaijani", "азербайджанська"],
    "ar": ["arabic", "арабська"],
    "he": ["hebrew", "іврит"],
    "fa": ["persian", "farsi", "перська"],
    "hi": ["hindi", "гінді"],
    "bn": ["bengali", "бенгальська"],
    "ur": ["urdu", "урду"],
    "id": ["indonesian", "індонезійська"],
    "ms": ["malay", "малайська"],
    "vi": ["vietnamese", "вʼєтнамська", "в'єтнамська"],
    "th": ["thai", "тайська"],
    "zh": ["chinese", "китайська"],
    "ja": ["japanese", "японська"],
    "ko": ["korean", "корейська"],
    "tl": ["tagalog", "filipino", "тагальська"],
    "sw": ["swahili", "суахілі"],
}
LANG_ALIASES = {a: code for code, names in _LANG_NAMES.items() for a in names}
LANG_ALIASES.update({c: c for c in _LANG_NAMES})


def normalize_lang(raw: str) -> str:
    """'pl', 'plwiki', 'pl.wikipedia', 'Polish', 'польська' -> 'pl'."""
    s = raw.strip().lower()
    s = re.sub(r"(\.wikipedia(\.org)?|wiki)$", "", s)
    if s in LANG_ALIASES:
        return LANG_ALIASES[s]
    if re.fullmatch(r"[a-z]{2,3}(-[a-z]+)*", s):  # any other valid-looking code (zh-yue, zh-min-nan)
        return s
    raise UnknownLanguageError(f"unknown language '{raw}'")


# Wikidata site ids use '_' where the domain uses '-' (zh-yue.wikipedia -> zh_yuewiki);
# a few editions kept a legacy id.
_SITE_OVERRIDES = {"be-tarask": "be_x_old"}


def wikidata_site(lang: str) -> str:
    return _SITE_OVERRIDES.get(lang, lang.replace("-", "_")) + "wiki"


def edition_name(lang: str, out: Lang | str = Lang.UK) -> str:
    """'pl' -> 'польська Вікіпедія' / 'Polish Wikipedia'. Names the edition, never a country."""
    names = _LANG_NAMES.get(lang)
    if not names:
        return f"{lang}.wikipedia"
    if out == Lang.EN:
        return names[0].capitalize() + " Wikipedia"
    uk = next((n for n in names if re.search("[а-яіїєґ]", n)), names[0])
    return f"{uk} Вікіпедія" if uk.endswith("ька") else f"Вікіпедія мовою {uk}"
