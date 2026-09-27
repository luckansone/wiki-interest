"""The eval harness itself: scripted 'model' drives the real CLI (fake API) and checks fire."""

import json
import os

import run_eval  # evals/ is on pytest's pythonpath (pyproject.toml)


def scripted(steps):
    it = iter(steps)

    def chat(messages):
        step = next(it)
        if step == "ANSWER_FROM_TOOL":  # copy summary_text of the last tool output = honest answer
            out = json.loads(messages[-1]["content"])
            return {"choices": [{"message": {"role": "assistant", "content": out["summary_text"]}}]}
        if isinstance(step, str):
            return {"choices": [{"message": {"role": "assistant", "content": step}}]}
        name, args = step
        return {
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [
                            {"id": "c1", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}
                        ],
                    }
                }
            ]
        }

    return chat


def env(tmp_path):
    return dict(os.environ, WI_FAKE_API="1", WI_OUT=str(tmp_path))


SC = {"id": "t", "prompt": "x", "expect": {"langs": ["pl", "cs"], "months": 24, "mention_any": [["довіра"]]}}
CMD = 'bash scripts/wi analyze --topic "Intermittent fasting" --langs pl,cs --months 24'


def test_honest_run_passes(tmp_path):
    res = run_eval.run_scenario(
        SC,
        scripted([("read_file", {"path": "SKILL.md"}), ("bash", {"command": CMD}), "ANSWER_FROM_TOOL"]),
        env(tmp_path),
    )
    assert run_eval.check(SC, res) == []


def test_hallucinated_number_is_caught(tmp_path):
    res = run_eval.run_scenario(
        SC, scripted([("bash", {"command": CMD}), "pl росте на +57%, довіра висока"]), env(tmp_path)
    )
    assert any("hallucination" in f for f in run_eval.check(SC, res))


def test_disallowed_command_is_blocked(tmp_path):
    assert "not allowed" in run_eval.run_tool("bash", {"command": "rm -rf /"}, env(tmp_path))
    assert "not allowed" in run_eval.run_tool("bash", {"command": "bash scripts/wi -h; rm -rf x"}, env(tmp_path))


def test_unsigned_percent_of_a_decline_is_not_a_hallucination():
    res = {
        "outputs": ['{"summary_text":"uk: спадає — -17% за останні 12 міс.","results":{"uk":{"yoy_norm":-0.1665}}}'],
        "answer": "Інтерес впав на 17% (точніше 16.65%), довіра висока",
        "calls": [{"tool": "bash", "args": {"command": "bash scripts/wi analyze --langs uk --months 24"}}],
    }
    assert run_eval.check({"expect": {"langs": ["uk"]}}, res) == []


def test_shell_tricks_and_outside_paths_are_blocked(tmp_path):
    e = env(tmp_path)
    for cmd in [
        "ls\necho INJECTED",
        "cat SKILL.md > x.txt",
        "cat /etc/passwd",
        "cat ../../x",
        "head $HOME/.ssh/id_rsa",
        "lsof",
        "python3 -c 'print(1)'",
    ]:
        out = run_eval.run_tool("bash", {"command": cmd}, e)
        assert out.startswith("error:"), (cmd, out)
    assert "wiki-interest" in run_eval.run_tool("bash", {"command": "cat SKILL.md"}, e)


def test_pdf_path_and_question_are_required_when_expected(tmp_path):
    sc = {"id": "t", "prompt": "x", "expect": {"langs": ["pl", "cs"], "pdf": True, "question": True}}
    cmd = CMD + ' --pdf --question "Q?"'
    res = run_eval.run_scenario(sc, scripted([("bash", {"command": cmd}), "ANSWER_FROM_TOOL"]), env(tmp_path))
    assert run_eval.check(sc, res) == ["answer does not give the PDF path"]
    pdf = json.loads(res["outputs"][-1])["files"]["pdf"]
    res["answer"] += f"\nPDF: {pdf}"
    assert run_eval.check(sc, res) == []
    res["calls"][-1]["args"]["command"] = CMD + " --no-pdf"
    assert run_eval.check(sc, res) == ["PDF was switched off with --no-pdf", "expected --question (the PDF title)"]
