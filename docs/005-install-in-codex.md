# Install and onboard the skill in OpenAI Codex

Facts in this document about Codex (CLI, IDE extension, ChatGPT desktop) were checked
against the official documentation on 2026-09-27.

## 1. Where Codex looks for skills

Codex scans these locations, and needs no feature flag to do it:

| Location | Scope |
|---|---|
| `$CWD/.agents/skills` | Current working directory |
| `$CWD/../.agents/skills` | Parent of the current working directory |
| `$REPO_ROOT/.agents/skills` | Repository root |
| `$HOME/.agents/skills` | Your user account, every repository |
| `/etc/codex/skills` | Set by an administrator, every user |

Codex also ships built-in system skills; `wiki-interest` is not one of them, so it must
be installed in one of the locations above.

An older Codex setup used `~/.codex/skills`. That location is not part of the current
scan list; it may still work in an older Codex version, but do not rely on it in a
current install.

## 2. Install

Choose a repository-level or a user-level install.

**User-level** (every repository on this machine, recommended while you develop the skill):

```bash
mkdir -p ~/.agents/skills
ln -s "$(pwd)" ~/.agents/skills/wiki-interest
```

**Repository-level** (one other project). Build the zip here, then unzip it into the
`.agents/skills/` folder of that project and commit it:

```bash
make skill_zip
cd /path/to/other-project
mkdir -p .agents/skills
unzip -q /path/to/wiki-interest/dist/wiki-interest.zip -d .agents/skills/
```

> **Caution:** Do not link this repository into its own `.agents/skills/` folder. The link
> then points to its own parent, and recursive tools (`grep -r`, `find -L`) can loop.

**A frozen user-level copy** (instead of the symlink):

```bash
make skill_zip
mkdir -p ~/.agents/skills/wiki-interest
unzip -q dist/wiki-interest.zip -d /tmp/wiki-interest-unzip
cp -R /tmp/wiki-interest-unzip/wiki-interest/. ~/.agents/skills/wiki-interest/
rm -rf /tmp/wiki-interest-unzip
```

## 3. AGENTS.md

Codex reads `AGENTS.md` files starting from the repository root and walking down to the
current directory; a file closer to the current directory is read later, so it can
override an earlier one. There is also a global file, `~/.codex/AGENTS.md`, and an
`AGENTS.override.md` file overrides the `AGENTS.md` at its own level.

This repository's `AGENTS.md` already gives Codex the rules for this project: the
repository map, the commands, the invariants in section 5, and the coding style. Keep
any Codex-specific note brief and put shared rules in `AGENTS.md`, not in a separate
file.

## 4. Enable network access

Codex's default sandbox mode, `workspace-write`, blocks outbound network access. The
skill needs network access to `wikimedia.org` and `www.wikidata.org` for a real
`analyze` run.

Enable network access for the whole sandbox, in `~/.codex/config.toml`:

```toml
[sandbox_workspace_write]
network_access = true
```

Or enable it for one run only:

```bash
codex --config sandbox_workspace_write.network_access=true
```

| Sandbox mode | Network access | Use it for |
|---|---|---|
| `read-only` | Blocked | Reading code, never running the skill. |
| `workspace-write` (default) | Blocked, unless `network_access = true` | Everyday use. Turn network access on, and leave file access scoped to the workspace. |
| `danger-full-access` | Allowed | Not recommended for this skill. It removes the sandbox entirely, not only the network block. |

Prefer `network_access = true` inside `workspace-write` over `danger-full-access`. It
gives the skill the network access it needs, without widening file-system access beyond
the workspace.

The approval policy controls what Codex does when a command needs more access than the
sandbox gives. With `on-request` (the default), Codex asks you first, for example before
a command uses the network. With `never`, Codex does not ask, and a blocked request fails.

## 5. First use

Set your contact address once:

```bash
export WI_CONTACT="you@company.com"
```

Invoke the skill explicitly:

```text
$wiki-interest
```

or browse the installed skills with `/skills` and pick it from the list. Codex can also
select the skill on its own, from its description, without an explicit `$` invocation.

Example prompts, in English and in Ukrainian (from `SKILL.md` and
`evals/scenarios.json`):

| Language | Prompt |
|---|---|
| English | "Compare interest in learning English in our languages, and give a short report: which audiences next, and why?" |
| Ukrainian | "Ми створюємо застосунок для вивчення мов. Порівняй інтерес до вивчення англійської у вибраних нами мовних розділах: українська, польська, турецька, в'єтнамська, індонезійська, португальська — та підготуй короткий звіт: які аудиторії варто дослідити наступними й чому?" |

A good answer names language editions (not countries), states the confidence for each
verdict, and ends with the full path to `report.pdf`. Codex has no tool that shows a file
in the chat, so the path is the result. Open the file from that path.

`$skill-installer <name>` installs a curated skill by name, for skills published in
Codex's own catalog. `wiki-interest` is not in that catalog; install it with the steps
in section 2 instead.

## 6. Verify with the offline demo

```bash
WI_FAKE_API=1 bash scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs --months 24 --pdf
```

This needs no network access and no `WI_CONTACT`. The PDF carries a red demo banner,
because the data is synthetic. If this command works but a real run does not, the
sandbox's network setting (section 4) is the likely cause.

## 7. Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Codex does not list `wiki-interest` under `/skills` | The skill folder, or its symlink, is not in a scanned location. | Check `ls .agents/skills/wiki-interest/SKILL.md` or `ls ~/.agents/skills/wiki-interest/SKILL.md`. |
| Every real `analyze` run fails to reach Wikimedia | `network_access` is not enabled for `workspace-write`. | Set `network_access = true` under `[sandbox_workspace_write]` in `~/.codex/config.toml`, or pass `--config sandbox_workspace_write.network_access=true`. |
| The offline demo (`WI_FAKE_API=1`) also fails | Not a network problem: check the launcher itself. | See `docs/002-installation-guide.md`, section 5. |
| Codex asks for approval before each real run | `network_access` is off, so each run needs more access than the sandbox gives. | Set `network_access = true` (section 4). Then the run stays inside the sandbox and Codex does not ask. |

See `docs/002-installation-guide.md` for launcher and environment-variable
troubleshooting that applies everywhere, not only in Codex.
