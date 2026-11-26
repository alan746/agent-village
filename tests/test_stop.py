import json

import pytest

import transcript
import village
from store import Store
from test_resume import ScriptedModel
from test_settings import FakeSandbox, run_village, runs
from test_transcript import reply


class FailingModel(ScriptedModel):
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise ConnectionError("Connection error.")


def session_ends(run_dir):
    return [json.loads(e.content) for e in Store(str(run_dir / "village.db")).read_event() if e.type == "session_end"]


def fail_all(monkeypatch):
    monkeypatch.setattr(village, "make_models",
                        lambda: {name: FailingModel(responses=[]) for name in village.MODEL_NAME})


def test_requested_rounds_done_exits_normally(runs, monkeypatch):
    run_village(monkeypatch, ["--goal", "ok", "--rounds", "2"])
    run_dir = next(runs.iterdir())
    assert session_ends(run_dir) == [{"reason": "rounds_done", "turns": 8, "ok": 8, "failed": 0}]
    assert FakeSandbox.created[0].calls == ["start", "close"]


def test_all_turns_failing_exits_non_zero(runs, monkeypatch, capsys):
    fail_all(monkeypatch)
    monkeypatch.setattr("sys.argv", ["village.py", "--goal", "fail", "--rounds", "3"])
    with pytest.raises(SystemExit) as info:
        village.run_model()
    assert info.value.code not in (0, None)
    assert "turns in a row failed" in str(info.value.code)
    run_dir = next(runs.iterdir())
    assert session_ends(run_dir) == [{"reason": "consecutive_failures", "turns": 4, "ok": 0, "failed": 4}]
    assert FakeSandbox.created[0].calls == ["start", "close"]
    assert "stopped" not in [e.type for e in Store(str(run_dir / "village.db")).read_event()]


def test_budget_used_up_at_start_exits_non_zero(runs, monkeypatch):
    spend = lambda: [reply("Done.", input_tokens=600) for _ in range(10)]
    run_village(monkeypatch, ["--goal", "budget", "--input-budget", "1000"], spend)
    run_dir = next(runs.iterdir())
    assert session_ends(run_dir) == [{"reason": "budget_exhausted", "turns": 2, "ok": 2, "failed": 0}]

    with pytest.raises(SystemExit) as info:
        run_village(monkeypatch, ["--resume", run_dir.name], spend)
    message = str(info.value.code)
    assert "1,200 of 1,000 input tokens" in message
    assert "--input-budget" in message and "--output-budget" in message
    assert session_ends(run_dir)[-1] == {"reason": "budget_exhausted", "turns": 0, "ok": 0, "failed": 0}
    assert FakeSandbox.created[-1].calls == ["close"]

    run_village(monkeypatch, ["--resume", run_dir.name, "--input-budget", "2000", "--rounds", "1"], spend)
    assert session_ends(run_dir)[-1] == {"reason": "budget_exhausted", "turns": 2, "ok": 2, "failed": 0}


def test_summary_counts_failed_turns_and_stop_reasons(runs, monkeypatch):
    run_village(monkeypatch, ["--goal", "summary", "--rounds", "1"])
    run_dir = next(runs.iterdir())
    fail_all(monkeypatch)
    monkeypatch.setattr("sys.argv", ["village.py", "--resume", run_dir.name])
    with pytest.raises(SystemExit):
        village.run_model()

    text = transcript.render(run_dir)
    assert "**Rounds in which every turn succeeded:** 1 of 2 started" in text
    assert "**Turns:** 8 attempted, 4 succeeded, 4 failed\n" in text
    assert "| start | round 1 | 4 | 4 | 0 | the requested rounds were done |" in text
    assert "| resume | round 2 | 4 | 0 | 4 | too many consecutive turns failed |" in text
    assert "**[STOPPED]** too many consecutive turns failed (4 turns, 0 succeeded, 4 failed)" in text
    assert text.count("**[TURN ERROR]** ConnectionError") == 4
    index = transcript.render_split(run_dir)["README.md"]
    assert "1 of 2 started" in index and "| 4 | 0 | 4 | too many consecutive turns failed |" in index


def test_summary_of_old_run_without_stop_reasons(tmp_path):
    run_dir = tmp_path / "old"
    run_dir.mkdir()
    store = Store(str(run_dir / "village.db"))
    store.log("village", "run_config", json.dumps({"mode": "start", "step": 0, "round": 1,
                                                    "models": {"alice": "a", "bob": "b"}, "limits": {}}))
    for step, (actor, status) in enumerate([("alice", "ok"), ("bob", "error"), ("alice", "ok"), ("bob", None)]):
        turn = {"step": step, "round": step // 2 + 1}
        store.log(actor, "turn_start", json.dumps(turn))
        store.log(actor, "say", f"step {step}")
        if status:
            store.log(actor, "turn_end", json.dumps({**turn, "status": status}))
    store.log("village", "stopped", "2 consecutive failed turns")
    store.log("village", "run_config", json.dumps({"mode": "resume", "step": 3, "round": 2,
                                                    "models": {"alice": "a", "bob": "b"}, "limits": {}}))
    store.log("bob", "turn_start", json.dumps({"step": 3, "round": 2}))
    store.log("bob", "turn_end", json.dumps({"step": 3, "round": 2, "status": "ok"}))

    text = transcript.render(run_dir)
    assert "**Rounds in which every turn succeeded:** 1 of 2 started" in text
    assert "**Turns:** 5 attempted, 3 succeeded, 1 failed, 1 with no recorded end" in text
    assert "| start | round 1 | 4 | 2 | 1 | 2 consecutive failed turns |" in text
    assert "| resume | round 2 | 1 | 1 | 0 | not recorded |" in text
