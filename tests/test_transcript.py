import sys

import pytest
from langchain_core.messages import AIMessage

import persistence
import transcript
import village
from sandbox import docker_available
from store import Store
from test_resume import ScriptedModel

BUGGY = "def mean(xs):\n    return sum(xs) / len(x)\n\nprint(mean([1, 2, 3]))\n"


def reply(content="", calls=(), input_tokens=100, output_tokens=10, cache_read=40):
    return AIMessage(content, tool_calls=[{"name": name, "args": args, "id": f"call_{name}_{n}", "type": "tool_call"}
                                          for n, (name, args) in enumerate(calls)],
                     usage_metadata={"input_tokens": input_tokens, "output_tokens": output_tokens,
                                     "total_tokens": input_tokens + output_tokens,
                                     "input_token_details": {"cache_read": cache_read}})


SCRIPTS = {
    "claude": [reply("I will set up the project.", [("post_chat", {"content": "Please write mean.py and run it."})]),
               reply("Waiting for the others.")],
    "chatgpt": [reply("", [("write_file", {"path": "mean.py", "content": BUGGY})], input_tokens=200),
                reply("Wrote mean.py.", input_tokens=200)],
    "deepseek": [reply("", [("run_command", {"command": "python mean.py"})], output_tokens=30),
                 reply("The script fails with a NameError.", output_tokens=30)],
    "gemini": [reply("Nothing for me to do yet.")],
}


@pytest.mark.skipif(not docker_available(), reason="Docker engine is not reachable (docker info failed)")
def test_transcript_of_a_scripted_run(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(village, "make_models",
                        lambda: {name: ScriptedModel(responses=list(SCRIPTS[name])) for name in village.MODEL_NAME})
    monkeypatch.setattr(sys, "argv", ["village.py", "--goal", "transcript", "test", "--offline", "--rounds", "1"])
    village.run_model()
    run_dir = next((tmp_path / "runs").iterdir())

    text = transcript.render(run_dir)

    order = ["**Goal:** transcript test",
             "| claude | 1 | 2 | 200 | 20 | 80 | 0 | 0 | 0 |",
             "| chatgpt | 1 | 2 | 400 | 20 | 80 | 0 | 0 | 0 |",
             "| deepseek | 1 | 2 | 200 | 60 | 80 | 0 | 1 | 1 |",
             "| gemini | 1 | 1 | 100 | 10 | 40 | 0 | 0 | 0 |",
             "| **village** | 4 | 7 | 900 | 110 | 280 | 0 | 1 | 1 |",
             "## Round 1",
             "> I will set up the project.",
             "> Please write mean.py and run it.",
             "**wrote** `mean.py` (66 bytes)",
             "**deepseek ran** `python mean.py` · **[FAILED]** exit code 1",
             "NameError: name 'x' is not defined",
             "> The script fails with a NameError.",
             "> Nothing for me to do yet."]
    positions = [text.find(snippet) for snippet in order]
    assert -1 not in positions, [s for s, p in zip(order, positions) if p == -1]
    assert positions == sorted(positions)
    assert text.count("python mean.py") == 1
    assert "**Rounds in which every turn succeeded:** 1 of 1 started" in text
    assert "**Turns:** 4 attempted, 4 succeeded, 0 failed" in text
    assert "| start | round 1 | 4 | 4 | 0 | the requested rounds were done |" in text

    files = transcript.render_split(run_dir)
    assert sorted(files) == ["README.md", "round-001.md"]
    index = files["README.md"]
    assert "| **village** | 4 | 7 | 900 | 110 | 280 | 0 | 1 | 1 |" in index
    assert "| [1](round-001.md) |" in index and "| 1 | 1 | 0 | 900 | 110 |" in index
    assert "## Timeline" not in index
    round_one = files["round-001.md"]
    assert "[Index](README.md)" in round_one
    assert "**[FAILED]** exit code 1" in round_one and "NameError" in round_one
    assert round_one.find("**Run started**") < round_one.find("### claude") < round_one.find("### deepseek")


def test_old_runs_without_turn_events_still_export(tmp_path):
    run_dir = tmp_path / "old"
    run_dir.mkdir()
    store = Store(str(run_dir / "village.db"))
    store.set_goal("old goal")
    for actor in ["claude", "chatgpt"]:
        store.log(actor, "wake", "0 new messages")
        store.spend(actor, 50, 5)
        store.log(actor, "tool_use", "post_task: {'description': 'x'}")
        store.log(actor, "post_task", "x (max_workers=2) -> You posted task 1.")
        store.log(actor, "say", f"hello from {actor}")
    text = transcript.render(run_dir)
    assert "rounds are inferred" in text
    assert "> hello from chatgpt" in text
    assert "| **village** | 2 | 2 | 100 | 10 |" in text
