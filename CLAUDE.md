@AGENTS.md

## Claude Code notes

- `AGENTS.md` (imported above) is the shared context for all coding agents. Put general rules there, not here.
- Put only Claude-specific notes in this file.
- For subagents, set `model: "sonnet"` for research, first drafts and mechanical edits. Review their output on Opus before you report the result (AGENTS.md, section 9).
- Load the `writing-clearly-and-concisely` skill before you write docs or long text, if it is installed (AGENTS.md, section 7).
- To test the skill as a user does, copy or link this folder to `~/.claude/skills/wiki-interest/`. See `docs/004-install-in-claude.md`.
