---
name: wiki-interest
description: Measures how interest in a topic changes across Wikipedia language editions using Wikimedia pageview statistics, with trend confidence, charts and a PDF report (one-page summary + appendix). Use when a B2C founder or product team asks whether interest in a topic (course, subject, niche) is growing, how languages/markets compare, which language to localize into or which audience to research next. Keywords - Wikipedia pageviews, interest trend, topic demand, localization, language market, інтерес до теми, перегляди Вікіпедії, яку мову запускати, зростання інтересу.
compatibility: bash, internet access to wikimedia.org and wikidata.org, and uv (preferred; fetches a suitable Python itself) or Python 3.11–3.14. First run creates .venv (~1 min).
metadata:
  version: "0.3.0"
---

# wiki-interest

**Every `analyze` run produces a PDF report (page 1: one-page summary; then an appendix with the ranking, per-language details, all limitations and monthly pageviews), and you must show that PDF to the user as a file (section 4, step 7).** If you need to ask the user something first (e.g. which languages), ask before running anything.

All numbers are computed by `scripts/wi`. **Never compute, estimate or round numbers
yourself. Quote them from the command output.**

## 1. Turn the request into arguments

| Argument | How to choose |
|---|---|
| `--topic` | The **exact English Wikipedia article title**. Repeat it for 1–4 closely related articles that together form the topic. The tool finds the article in each language through Wikidata, so do not translate titles yourself. |
| `--langs` | Wikipedia language codes, comma-separated (`uk,pl,cs`). Names such as `Polish` also work. Maximum 8. If the user says "our selected languages" and did not list them, **ask which ones**. |
| `--months` | 24 by default. "last N years" → N×12. For "can we trust this growth?" use 36. |
| `--pdf` | **Always add it**, even if the user did not ask for a report (it is also the default). Never use `--no-pdf`. |
| `--question` | Always pass the user's question, in their language. It becomes the PDF title. |
| `--out-lang` | `uk` (default) if the user writes in Ukrainian; otherwise `en`. Sets the language of `summary_text` and of the whole PDF. |
| `--weights` | Only for ranking. Use it when the user changes priorities, e.g. "audience size matters more" → `--weights "growth=0.3,level=0.5,confidence=0.2"`. |

Topic templates (exact titles):

- Learning English: `--topic "English language" --topic "International English Language Testing System" --topic "Test of English as a Foreign Language"`
- Astronomy: `--topic "Astronomy" --topic "Solar System" --topic "Telescope"`
- Intermittent fasting: `--topic "Intermittent fasting"`

## 2. Run ONE command

```bash
bash scripts/wi analyze --topic "<Title>" [--topic "<Title 2>"] --langs <codes> --months 24 --pdf --question "<text>" [--out-lang en]
```

`--pdf` and `--question` are mandatory in every `analyze` call, including follow-up re-runs. Run it from this skill's directory. stdout is one JSON object. If it contains `error`, run the command given in `fix`. Do not guess.

Examples for typical questions (the comments are English translations; the users asked in Ukrainian, so `--question` is in Ukrainian and `--out-lang` is left at `uk`):

```bash
# "Compare growth of interest in intermittent fasting in Polish vs Czech Wikipedia, last 2 years"
bash scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs --months 24 --pdf --question "Як змінюється інтерес до інтервального голодування в польській і чеській Вікіпедії?"

# "Is interest in astronomy growing in Ukrainian Wikipedia, and how far can we trust it?"
bash scripts/wi analyze --topic "Astronomy" --topic "Solar System" --topic "Telescope" --langs uk --months 36 --pdf --question "Чи зростає інтерес до астрономії в українській Вікіпедії?"

# "Compare interest in learning English in our languages + short report: which audiences next and why?"
bash scripts/wi analyze --topic "English language" --topic "International English Language Testing System" --topic "Test of English as a Foreign Language" --langs uk,pl,tr,vi,id,pt --months 24 --pdf --question "Які аудиторії застосунку для вивчення англійської досліджувати далі?"

# The same question asked in English: English title and an English PDF
bash scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs --months 24 --pdf --question "How is interest in intermittent fasting changing in Polish vs Czech Wikipedia?" --out-lang en
```

## 3. Read the output

- `summary_text` is a ready, correct paragraph with all the key numbers and the reasons for each confidence level. Base your answer on it.
- `results.<lang>`:
  - `verdict`: `growing` / `declining` / `stable_or_unclear`.
  - `confidence`: `high` / `medium` / `low` — how much to trust the verdict.
  - `yoy_norm`: **last 12 complete months vs the 12 months before**, adjusted for the whole wiki's traffic. **This is the main number.** It is NOT the change over the whole `--months` period.
  - `yoy_norm_ci90`: 90% interval for `yoy_norm`.
  - `yoy_raw`: raw pageview change, same 12-vs-12 months.
  - `trend_pct_year`, `trend_p_value`: long-run trend over the whole period.
  - `median_views_month`: audience size.
  - `flags`: data problems (see below).
  - `status: "no_data"`: the topic has no article in that language.
- `ranking`: languages ordered by score (growth 50%, share of interest 30%, confidence 20% by default). `why` gives the reasons. `best_trend_in_set` means "least bad of the chosen languages", not growth.
- `files`: the paths `pdf`, `chart_png`, `series_csv` and `run_json` (the full data). `pdf_shared` (only in a chat sandbox, e.g. claude.ai) is a copy of the PDF in the folder the chat shows to the user. `files.pdf` must be present. If it is missing and `warnings` do not explain why, the command was run with `--no-pdf`: re-run it without that flag.
- `warnings` (only if present): tell the user, e.g. why no PDF was made.
- stderr is normally empty. A `wi: warning: ...` line reports a retry or characters the PDF font cannot show. Mention it only if it affects the answer.

Flags, and what to tell the user:

- `PROJECT_SHIFT`: raw and adjusted growth point in different directions. The whole language edition's traffic changed, so raw growth is misleading. Trust `yoy_norm`.
- `SPIKE_DRIVEN`: the growth comes mostly from one month (news, viral event). It is not a stable trend.
- `LOW_VOLUME`: fewer than 300 views/month, so percentages are noisy.
- `MISSING_ARTICLE`: some topic articles don't exist in that language, so coverage is partial.
- `SHORT_HISTORY`: less than 24 months of data, so seasonality is not controlled.
- `TREND_CONFLICT`: the last year moves against a significant long-run trend (a rebound or a reversal). Report both directions.

## 4. Answer (in the user's language)

1. Start with a direct answer (e.g. "Yes, it is growing, with medium confidence").
2. Give the key numbers per language, copied from `summary_text` or `results`. Say "over the last 12 months vs the previous 12".
3. Say why confidence is what it is: copy the reasons in brackets from `summary_text`.
4. For ranking questions, name the top 2–3 languages and their `why`.
5. Always add this limitation: pageviews show interest, not willingness to pay; a language edition is not a country.
6. Suggest one next validation step (survey, landing-page test, app-store search data).
7. Always end with the PDF report, shown as a file:
   - If you have a tool that shows or sends files to the user (for example `present_files` on claude.ai, or a send-file tool in Claude Code), call it with `files.pdf_shared` if it exists, else with `files.pdf`. A path in the text alone does not show the file.
   - If you have no such tool, give the full `files.pdf` path.

   If no PDF was created, relay the reason from `warnings` (e.g. no language has an article) and offer a re-run with a broader `--topic`.

Rules:

- Never call a trend "growing" or "declining" if `verdict` is `stable_or_unclear`, even if `yoy_norm` is positive or negative. Say "no clear change".
- Name language editions, never countries: "Portuguese Wikipedia" (`pt`, readers mostly in Brazil), not "Portugal"; "Vietnamese Wikipedia", not "Vietnam". `summary_text` already names them this way.
- Copy numbers exactly as printed. Do not round them again (write `4 426`, not "4.4 thousand").
- Do not add causes the data does not show (e.g. "maybe academic English lost appeal"). Offer them only as hypotheses to check.
- Never drop `flags` from your answer.
- Never compare raw views across languages without mentioning edition size. Use `views_per_million` for that.

If a language has `status: "no_data"`: say that edition has no article on this topic, so interest there was not measured (it is not zero interest, and a missing article can itself be a content gap). Offer to re-run with a broader English article (e.g. `Fasting` instead of `Intermittent fasting`, `Diet (nutrition)`), which is a follow-up run, not a replacement for the answer.

## 5. Report with your own wording (optional)

The PDF from `analyze --pdf` already contains an automatic conclusion. To replace it with yours, run the command below. Keep it to 2–4 sentences, using only numbers from the output (page 1 shows up to 700 characters; a longer text is printed in full in the appendix). The appendix is re-rendered too. Show the new PDF to the user again (step 7): the output has `files.pdf` and, in a chat sandbox, `files.pdf_shared`.

```bash
bash scripts/wi report --run-id <run_id> --conclusion "<text>"
```

## 6. Follow-up questions

Re-run `analyze` with the changed arguments, again with `--pdf`, and show the new PDF (step 7) ("add Slovak" → `--langs pl,cs,sk`; "over 3 years" → `--months 36`). Responses are cached on disk: changing `--months`, `--weights` or the language list only downloads the articles and editions not fetched before (the cache refreshes when a new month completes). Tell the user what changed compared to the previous answer.

Methodology details, if the user asks how numbers are computed: `references/METHODOLOGY.md`.
