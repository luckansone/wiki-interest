"""wiki-interest: topic interest trends across Wikipedia language editions.

Package layout:

- `config`, `enums`, `errors`, `models`, `text`: shared settings, types and UI strings.
- `data`: languages, HTTP with cache and retry, Wikidata and Pageviews clients.
- `analysis`: statistics per language, ranking, summary text.
- `report`: chart PNG and the PDF report (summary page + appendix).
- `pipeline`: runs one analysis end to end; `cli`: the JSON command-line interface.
- `log`: loguru + rich logging to stderr (stdout carries only the JSON result).
"""

__version__ = "0.3.0"
