#!/usr/bin/env python3
"""Minimal agent loop to test the skill end-to-end on a cheap model (OpenAI-compatible API).

  export OPENROUTER_API_KEY=...
  uv run python evals/run_eval.py --model anthropic/claude-haiku-4.5       # real Wikimedia data
  uv run python evals/run_eval.py --fake-api        # default free model (Nemotron 3 Super), synthetic data

The model sees only the skill's name+description (like a real skill host), must decide to
read SKILL.md, run the CLI and answer. Automatic checks per scenario; traces -> evals/traces/.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

import requests


SKILL_DIR = Path(__file__).resolve().parents[1]
TRACES = SKILL_DIR / "evals" / "traces"
# Commands run WITHOUT a shell (argv from shlex), so ; | > $() and newlines are never interpreted.
ALLOWED = (("bash", "scripts/wi"), ("scripts/wi",), ("python3", "scripts/wi.py"), ("python", "scripts/wi.py"))
FILE_CMDS = ("cat", "ls", "head", "pwd")  # read-only; path arguments must stay inside SKILL_DIR
PCT_RE = r"[+\-−]?\d+(?:[.,]\d+)?\s?%"
# Free OpenRouter model with tool calling (262K context); override with --model / EVAL_MODEL.
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b:free"

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": "Run a shell command in the skill directory. Returns stdout+stderr.",
            "parameters": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read a text file (path relative to the skill directory).",
            "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        },
    },
]


def skill_frontmatter() -> tuple[str, str]:
    text = (SKILL_DIR / "SKILL.md").read_text()
    name = re.search(r"^name:\s*(.+)$", text, re.M).group(1).strip()
    desc = re.search(r"^description:\s*(.+)$", text, re.M).group(1).strip()
    return name, desc


def system_prompt() -> str:
    name, desc = skill_frontmatter()
    return (
        "You are a helpful analyst assistant with tools.\n"
        f"Available skills:\n- {name}: {desc}\n  Instructions: SKILL.md (read it with read_file "
        "before using the skill). The working directory is the skill directory.\n"
        "Answer in the user's language."
    )


def _inside(path: str) -> bool:
    p = (SKILL_DIR / path).resolve()
    return p == SKILL_DIR or SKILL_DIR in p.parents


def run_tool(name: str, args: dict, env: dict) -> str:
    if name == "read_file":
        if not _inside(args.get("path", "")):
            return "error: path outside the skill directory"
        p = (SKILL_DIR / args.get("path", "")).resolve()
        return p.read_text()[:12000] if p.is_file() else f"error: no such file {args.get('path')}"
    denied = "error: command not allowed in the eval harness (use bash scripts/wi ...)"
    cmd = args.get("command", "").strip()
    if re.search(r"[;&|`<>\n\r]|\$", cmd):  # shell syntax is never needed; reject it with a clear message
        return denied
    try:
        argv = shlex.split(cmd)
    except ValueError:
        return denied
    if not argv:
        return denied
    if argv[0] in FILE_CMDS:
        if not all(_inside(a) for a in argv[1:] if not a.startswith("-")):
            return "error: path outside the skill directory"
    elif not any(tuple(argv[: len(p)]) == p for p in ALLOWED):
        return denied
    try:
        r = subprocess.run(argv, cwd=SKILL_DIR, capture_output=True, text=True, timeout=240, env=env)
        return (r.stdout + ("\n[stderr]\n" + r.stderr[-2000:] if r.stderr.strip() else ""))[:8000]
    except subprocess.TimeoutExpired:
        return "error: timeout"
    except OSError as e:  # e.g. scripts/wi not executable, python not installed
        return f"error: {e}"


def chat(base_url: str, api_key: str, model: str, messages: list) -> dict:
    for attempt in range(5):
        r = requests.post(
            f"{base_url}/chat/completions",
            timeout=180,
            headers={"Authorization": f"Bearer {api_key}"},
            json={"model": model, "messages": messages, "tools": TOOLS, "temperature": 0},
        )
        if r.status_code == 429 or r.status_code >= 500:  # free models are rate limited
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError(f"model API failed: {r.status_code} {r.text[:300]}")


def run_scenario(sc: dict, chat_fn, env: dict, max_steps: int = 12) -> dict:
    messages = [{"role": "system", "content": system_prompt()}, {"role": "user", "content": sc["prompt"]}]
    calls, outputs, usage = [], [], {"prompt_tokens": 0, "completion_tokens": 0}
    answer = ""
    for _ in range(max_steps):
        resp = chat_fn(messages)
        for k in usage:
            usage[k] += (resp.get("usage") or {}).get(k, 0) or 0
        msg = resp["choices"][0]["message"]
        messages.append({k: v for k, v in msg.items() if k in ("role", "content", "tool_calls")})
        if not msg.get("tool_calls"):
            answer = msg.get("content") or ""
            break
        for tc in msg["tool_calls"]:
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
                out = run_tool(tc["function"]["name"], args, env)
            except json.JSONDecodeError:  # cheap models sometimes emit broken JSON: tell them, don't crash
                args, out = {}, "error: tool arguments are not valid JSON"
            calls.append({"tool": tc["function"]["name"], "args": args})
            outputs.append(out)
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": out})
    return {"answer": answer, "calls": calls, "outputs": outputs, "usage": usage, "messages": messages}


def _pct_value(s: str) -> float:
    """Parse a percent as an absolute value: '−17 %' / '+17%' / '16,65%' -> 17.0 / 17.0 / 16.65.

    The sign is dropped because 'fell by 17%' is honest wording of '-17%'.
    """
    return abs(float(re.sub(r"[^\d.,]", "", s).replace(",", ".")))


def allowed_percents(outputs: list[str]) -> set[float]:
    """Every % the answer may legitimately contain = the ones printed by the tool (as absolute values)."""
    found = set()
    for o in outputs:
        found |= {_pct_value(m) for m in re.findall(PCT_RE, o)}
        vals = re.findall(r'"(?:yoy_norm|yoy_raw|yoy_norm_prev_year|trend_pct_year)":(-?[\d.]+)', o)
        for lo, hi in re.findall(r'"yoy_norm_ci90":\[(-?[\d.]+),(-?[\d.]+)\]', o):
            vals += [lo, hi]
        for v in vals:  # the model may quote the raw fraction at 0-2 decimals: -0.1665 -> 17% / 16.7% / 16.65%
            found |= {round(abs(float(v) * 100), d) for d in (0, 1, 2)}
    return found


def check(sc: dict, res: dict) -> list[str]:
    fails = []
    cmds = [c["args"].get("command", "") for c in res["calls"] if c["tool"] == "bash"]
    analyze = [c for c in cmds if " analyze" in c]
    exp = sc.get("expect", {})
    if exp.get("clarify"):
        if analyze:
            fails.append("ran analyze instead of asking which languages")
        if "?" not in res["answer"]:
            fails.append("no clarifying question in answer")
        return fails
    if not analyze:
        return ["analyze was never run"]
    last = analyze[-1]
    for l in exp.get("langs", []):
        if not re.search(rf"--langs[ =][^-]*\b{l}\b", last):
            fails.append(f"language {l} missing in command")
    if exp.get("months") and not re.search(rf"--months[ =]{exp['months']}\b", last):
        fails.append(f"expected --months {exp['months']}")
    if exp.get("pdf"):
        if "--no-pdf" in last:
            fails.append("PDF was switched off with --no-pdf")
        pdfs = re.findall(r'"pdf":"([^"]+)"', "\n".join(res["outputs"]))
        if pdfs and not any(pdf in res["answer"] or Path(pdf).parent.name in res["answer"] for pdf in pdfs):
            fails.append("answer does not give the PDF path")
    if exp.get("question") and "--question" not in last:
        fails.append("expected --question (the PDF title)")
    if len(res["calls"]) > exp.get("max_tool_calls", 6):
        fails.append(f"too many tool calls: {len(res['calls'])}")
    low = res["answer"].lower()
    for group in exp.get("mention_any", []):
        if not any(w.lower() in low for w in group):
            fails.append(f"answer mentions none of {group}")
    ok = allowed_percents(res["outputs"])
    bad = [p for p in re.findall(PCT_RE, res["answer"]) if _pct_value(p) not in ok]
    if bad:
        fails.append(f"numbers not found in tool output (possible hallucination): {sorted(set(bad))[:6]}")
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument(
        "--model",
        default=os.environ.get("EVAL_MODEL", DEFAULT_MODEL),
        help=f"OpenRouter model id (default: {DEFAULT_MODEL})",
    )
    ap.add_argument("--base-url", default=os.environ.get("EVAL_BASE_URL", "https://openrouter.ai/api/v1"))
    ap.add_argument("--fake-api", action="store_true", help="offline synthetic Wikimedia data")
    ap.add_argument("--only", help="comma-separated scenario ids")
    ap.add_argument("--repeats", type=int, default=1)
    a = ap.parse_args()
    key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("EVAL_API_KEY")
    if not key:
        sys.exit("set OPENROUTER_API_KEY (or EVAL_API_KEY for another OpenAI-compatible endpoint)")
    env = dict(os.environ, WI_OUT=str(SKILL_DIR / "evals" / "out"))
    if a.fake_api:
        env["WI_FAKE_API"] = "1"
    scenarios = json.loads((SKILL_DIR / "evals" / "scenarios.json").read_text())
    if a.only:
        scenarios = [s for s in scenarios if s["id"] in a.only.split(",")]
    TRACES.mkdir(parents=True, exist_ok=True)
    total, passed = 0, 0
    for sc in scenarios:
        for rep in range(a.repeats):
            res = run_scenario(sc, lambda m: chat(a.base_url, key, a.model, m), env)
            fails = check(sc, res)
            total += 1
            passed += not fails
            tag = re.sub(r"\W+", "_", a.model)
            (TRACES / f"{sc['id']}_{tag}_{rep}.json").write_text(
                json.dumps({"scenario": sc, "fails": fails, **res}, ensure_ascii=False, indent=1)
            )
            print(
                f"{'PASS' if not fails else 'FAIL'}  {sc['id']:<22} calls={len(res['calls'])} "
                f"tokens={res['usage']['prompt_tokens']}+{res['usage']['completion_tokens']}  {'; '.join(fails)}"
            )
    print(f"\n{passed}/{total} passed on {a.model}")
    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
