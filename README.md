# wiki-interest — Agent Skill

An [Agent Skills](https://agentskills.io/specification) skill that answers "is interest
in X growing, and in which languages?" from Wikimedia pageview statistics.

- Measures interest in a topic across Wikipedia language editions, from real pageview
  data.
- Computes a verdict (`growing` / `declining` / `stable_or_unclear`), a confidence
  level and a ranking, all with deterministic code. The agent only chooses arguments
  and relays the result.
- Adjusts for whole-edition traffic shifts, so growth in one language is not confused
  with readers moving between languages.
- Writes a compact JSON result for the agent, plus a chart PNG and a one-page PDF
  report with an appendix, in Ukrainian or English.
- Runs offline, on synthetic data, for demos, tests and evals (`WI_FAKE_API=1`).

## Quick start

```bash
cd wiki-interest
export WI_CONTACT="you@company.com"          # Wikimedia asks every client for a contact
bash scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs --months 24 --pdf
```

Try it first without network access, using synthetic data:

```bash
make demo
```

`scripts/wi` picks `uv`, an already-suitable Python, or a pip fallback, by itself. See
`docs/002-installation-guide.md` for the exact rules and the environment variables.

## Documentation

| Document | Content |
|---|---|
| `docs/001-architecture.md` | Components, data flow, contracts, invariants, caching, thresholds. |
| `docs/002-installation-guide.md` | Requirements, how `scripts/wi` picks an environment, environment variables, troubleshooting. |
| `docs/003-onboarding-guide.md` | Developer onboarding: day-1 checklist, repo tour, how to add a flag, a UI string, a language or a CLI option. |
| `docs/004-install-in-claude.md` | Install and use the skill in Claude Code and on claude.ai. |
| `docs/005-install-in-codex.md` | Install and use the skill in OpenAI Codex. |
| `docs/006-cli-reference.md` | Every `wi analyze` and `wi report` option, the JSON output fields, exit codes, error examples. |
| `docs/007-logging-and-diagnostics.md` | stderr logging modes, the rich dashboard, how to report a bug. |
| `docs/008-testing-and-evals.md` | Test layout, the offline synthetic API, coverage, CI, how the evals work. |
| `docs/009-verification-log-and-roadmap.md` | How the code was verified, current limitations, planned iterations. |

`SKILL.md` is the contract with the agent that runs the skill. `references/METHODOLOGY.md`
holds the formulas, thresholds and limitations.

## Contributing

Read `AGENTS.md` first: it holds the rules for this repository (invariants, code style,
documentation style, and the model policy for development work). `CLAUDE.md` adds
Claude-specific notes on top of it.

```bash
make uv_install_deps       # uv sync: runtime + dev dependency groups
make test                  # pytest (offline, synthetic Wikimedia responses)
make lint                  # ruff check + ruff format --check
```

## Upload to Claude

```bash
make skill_zip
```

This builds `dist/wiki-interest.zip` (about 190 KB). See `docs/004-install-in-claude.md`
for the upload and onboarding steps, and `docs/005-install-in-codex.md` for Codex.
