# Methodology (MVP)

The computation is in `scripts/wiki_interest/analysis/` (`stats.py`, `metrics.py`, `ranking.py`). The thresholds are in `scripts/wiki_interest/config.py` (class `Thresholds`).

## Data

- **Articles per language.** Wikidata `wbgetentities` gives the sitelinks for each `--topic` (English title or QID). No machine translation is used.
- **Views.** Wikimedia Pageviews API, `per-article/{lang}.wikipedia/all-access/user/{title}/monthly`. The `user` agent excludes self-identified bots and automated traffic.
- **Denominator.** `aggregate/{lang}.wikipedia/all-access/user/monthly` gives the total views of the language edition.
- **Topic series.** The sum over the topic's articles in that language. Only complete calendar months are used; the current month is excluded.
- **Fetching and cache.** Pageviews are requested from 2015-07 (the API's first month) to the last complete month and sliced locally, and Wikidata returns all sitelinks. So a follow-up with other `--months` or languages reuses the cache.

## Metrics per language

- **Views per million (vpm)** = topic views / edition views × 10^6. Growth in vpm is growth in the *share of attention*. It removes edition-wide shifts, for example readers moving between language editions.
- **YoY** = sum(last 12 months) / sum(previous 12 months) − 1. It is computed on raw views (`yoy_raw`) and on vpm (`yoy_norm`). Comparing full years cancels seasonality.
- **90% CI of `yoy_norm`.** Bootstrap over month pairs (t, t−12), 1000 resamples, fixed seed.
- **Trend.** Theil–Sen slope of log(1+vpm) over the whole window, reported as %/year. The p-value comes from the Mann–Kendall test (Kendall τ vs time).
- **Spike share** = (max month − median month of the last year) / YoY gain.

## Verdict and confidence

| Rule | Result |
|---|---|
| CI of `yoy_norm` entirely > 0 | growing |
| CI entirely < 0 | declining |
| otherwise | stable_or_unclear |
| verdict growing/declining, 0 flags, trend p < 0.05 | confidence high |
| 1 flag, or p ≥ 0.05, or verdict stable_or_unclear | confidence medium |
| ≥ 2 flags | confidence low |

Confidence is confidence in the *verdict*, so `stable_or_unclear` (a CI that includes 0) is never "high". Each result lists its reasons in `confidence_reason_codes`: `CI_CROSSES_ZERO`, `NOT_SIGNIFICANT` (long-run trend p ≥ 0.05), `TREND_VS_YEAR` (significant long-run trend, but the last-year change is not confirmed), plus the flags.

Flags and when they fire:

- `LOW_VOLUME`: median < 300 views/month.
- `PROJECT_SHIFT`: raw and normalized YoY have different signs, and one of them exceeds 5%.
- `SPIKE_DRIVEN`: spike share > 40%.
- `MISSING_ARTICLE`: some topic articles are absent in that language.
- `SHORT_HISTORY`: fewer than 24 months of data.
- `TREND_CONFLICT`: the verdict is growing (declining) while the long-run Theil–Sen trend is significantly negative (positive): the last year is a rebound or a reversal.

## Ranking

score = w_growth·z(yoy_norm) + w_level·z(log(1+vpm)) + w_conf·{high 1, medium 0.5, low 0}

The z-scores are computed across the languages in the run. The `fastest_growth` reason is given only if that language's verdict is `growing`; otherwise the best growth z-score is labelled `best_trend_in_set`. The default weights are 0.5 / 0.3 / 0.2 and can be changed with `--weights`.

## Known limitations (MVP)

- Redirects are not added.
- Unidentified bots can remain inside `user` traffic, and daily data is not used to detect them.
- A language edition is not a country.
- Pageviews measure interest, not purchase intent.
- The ranking is relative to the chosen set of languages.
