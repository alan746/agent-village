import json
import sys
from dataclasses import asdict

import pytest
from langchain_core.messages import AIMessage

import persistence
import village
from persistence import Limits, open_run
from store import Store
from test_resume import ScriptedModel


class FakeSandbox:
    created = []

    def __init__(self, run_id, repo_dir, network=True):
        self.run_id = run_id
        self.network = network
        self.calls = []
        FakeSandbox.created.append(self)

    def start(self, actors):
        self.calls.append("start")

    def close(self):
        self.calls.append("close")
        return 0


@pytest.fixture
def runs(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "RUNS_DIR", tmp_path / "runs")
    monkeypatch.setattr(village, "docker_available", lambda: True)
    monkeypatch.setattr(village, "Sandbox", FakeSandbox)
    FakeSandbox.created = []
    return tmp_path / "runs"


def run_village(monkeypatch, argv, responses=lambda: [AIMessage("Nothing to do.") for _ in range(20)]):
    monkeypatch.setattr(village, "make_models",
                        lambda: {name: ScriptedModel(responses=responses()) for name in village.MODEL_NAME})
    monkeypatch.setattr(sys, "argv", ["village.py", *argv])
    village.run_model()


def configs(run_dir):
    return [json.loads(e.content) for e in Store(str(run_dir / "village.db")).read_event() if e.type == "run_config"]


def new_run(limits=None, network=True):
    run, _ = open_run(["--goal", "settings", "test"])
    if limits is not None:
        Store(run.db_path).log("village", "run_config", json.dumps({"mode": "start", "limits": limits,
                                                                      "network": network}))
    return run


def test_resume_keeps_saved_limits_unless_given(runs):
    saved = asdict(Limits(rounds=3, max_tool_rounds=7, input_budget=70_000_000, output_budget=2000,
                          compact_trigger=50_000, command_timeout=30))
    run = new_run(saved, network=False)

    resumed, _ = open_run(["--resume", run.run_id])
    assert asdict(resumed.limits) == {**saved, "rounds": Limits().rounds}
    assert resumed.network is False

    changed, _ = open_run(["--resume", run.run_id, "--output-budget", "5000", "--rounds", "2"])
    assert asdict(changed.limits) == {**saved, "output_budget": 5000, "rounds": 2}


def test_rounds_are_never_inherited(runs):
    run = new_run(asdict(Limits(rounds=40)))
    resumed, _ = open_run(["--resume", run.run_id])
    assert resumed.limits.rounds == Limits().rounds


def test_network_cannot_change_on_resume(runs, capsys):
    online = new_run(asdict(Limits()), network=True)
    with pytest.raises(SystemExit) as info:
        open_run(["--resume", online.run_id, "--offline"])
    assert info.value.code == 2
    assert "network setting cannot change after a run has started" in capsys.readouterr().err
    assert open_run(["--resume", online.run_id])[0].network is True


def test_offline_on_resume_of_offline_run_is_accepted(runs):
    offline = new_run(asdict(Limits()), network=False)
    assert open_run(["--resume", offline.run_id, "--offline"])[0].network is False
    assert open_run(["--resume", offline.run_id])[0].network is False


def test_run_without_run_config_falls_back_to_defaults(runs):
    run = new_run()
    resumed, _ = open_run(["--resume", run.run_id])
    assert resumed.limits == Limits()
    assert resumed.network is True
    given, _ = open_run(["--resume", run.run_id, "--input-budget", "9_000", "--offline"])
    assert given.limits == Limits(input_budget=9000)
    assert given.network is False


def test_resumed_village_logs_and_uses_the_inherited_settings(runs, monkeypatch):
    run_village(monkeypatch, ["--goal", "inherit", "--offline", "--rounds", "1", "--output-budget", "2000",
                              "--max-tool-rounds", "4"])
    run_dir = next(runs.iterdir())
    run_village(monkeypatch, ["--resume", run_dir.name, "--rounds", "2", "--command-timeout", "60"])

    first, second = configs(run_dir)
    assert second["mode"] == "resume"
    assert second["network"] is False
    assert second["limits"] == {**first["limits"], "rounds": 2, "command_timeout": 60}
    assert second["limits"]["output_budget"] == 2000 and second["limits"]["max_tool_rounds"] == 4
    assert [sandbox.network for sandbox in FakeSandbox.created] == [False, False]
