import json
import subprocess
import sys
import time

import pytest

import persistence
import village
from persistence import limits_from, open_run
from sandbox import Capture, PathError, Sandbox, docker_available, repo_path
from store import Store
from test_resume import ScriptedModel
from tool import make_tools

DOCKER = docker_available()
requires_docker = pytest.mark.skipif(not DOCKER, reason="Docker engine is not reachable (docker info failed)")

BUGGY = "def mean(xs):\n    return sum(xs) / len(x)\n\nprint(mean([1, 2, 3]))\n"
FIXED = "def mean(xs):\n    return sum(xs) / len(xs)\n\nprint(mean([1, 2, 3]))\n"


def containers(run_id):
    result = subprocess.run(["docker", "ps", "-aq", "--filter", f"label=village.run={run_id}"],
                            capture_output=True, text=True, check=True)
    return result.stdout.split()


def events(store, kind):
    return [(e.actor, json.loads(e.content)) for e in store.read_event() if e.type == kind]


@pytest.fixture
def village_env(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "RUNS_DIR", tmp_path / "runs")
    run, args = open_run(["--goal", "acceptance", "test", "--command-timeout", "20"])
    store = Store(run.db_path)
    sandbox = Sandbox(run.run_id, run.repo_dir, network=False)
    sandbox.start(["alice", "bob"])
    tools = {actor: {t.name: t for t in make_tools(actor, "worker", run.db_path, store, limits_from(args), sandbox)}
             for actor in ("alice", "bob")}
    try:
        yield run, store, sandbox, tools
    finally:
        sandbox.close()
        assert containers(run.run_id) == []


def test_repo_path_rejects_escapes():
    assert repo_path("app.py") == "/repo/app.py"
    assert repo_path("/repo/src/../app.py") == "/repo/app.py"
    for bad in ["../etc/passwd", "/etc/passwd", "src/../../x", "/repo", "", "..\\..\\x", "//etc/x"]:
        with pytest.raises(PathError):
            repo_path(bad)


def test_capture_keeps_head_and_tail():
    capture = Capture(5, 5)
    capture.feed(b"0123456789" * 3)
    assert capture.text() == "01234\n[... 20 bytes truncated ...]\n56789"
    small = Capture(5, 5)
    small.feed(b"abc")
    assert small.text() == "abc"


@requires_docker
def test_two_villagers_fix_a_bug_together(village_env):
    run, store, sandbox, tools = village_env
    alice, bob = tools["alice"], tools["bob"]

    assert alice["write_file"].invoke({"path": "stats/mean.py", "content": BUGGY}).startswith("Wrote")

    failed = bob["run_command"].invoke({"command": "python stats/mean.py"})
    assert failed.startswith("exit code: 1")
    assert "Traceback" in failed and "NameError" in failed

    assert "len(x)" in bob["read_file"].invoke({"path": "stats/mean.py"})
    assert bob["write_file"].invoke({"path": "/repo/stats/mean.py", "content": FIXED}).startswith("Wrote")

    passed = bob["run_command"].invoke({"command": "python stats/mean.py"})
    assert passed.startswith("exit code: 0")
    assert "2.0" in passed

    host_file = run.repo_dir / "stats" / "mean.py"
    assert host_file.read_text() == FIXED

    alice["write_file"].invoke({"path": "stats/__init__.py", "content": ""})
    alice["write_file"].invoke({"path": "tests/test_mean.py",
                                "content": "from stats.mean import mean\n\ndef test_mean():\n    assert mean([2, 4]) == 3\n"})
    assert bob["run_command"].invoke({"command": "pytest -q tests"}).startswith("exit code: 0")

    commands = events(store, "command")
    assert any(actor == "bob" and e["command"] == "python stats/mean.py" and e["exit_code"] == 1
               and "NameError" in e["stderr"] for actor, e in commands)
    assert any(actor == "bob" and e["exit_code"] == 0 for actor, e in commands)

    sandbox.close()
    assert containers(run.run_id) == []
    assert host_file.read_text() == FIXED


@requires_docker
def test_timeout_kills_the_command_inside_the_container(village_env):
    run, store, sandbox, tools = village_env
    started = time.monotonic()
    result = tools["alice"]["run_command"].invoke(
        {"command": "(sleep 4; touch /repo/background) & sleep 6; touch /repo/foreground", "timeout_seconds": 2})
    assert time.monotonic() - started < 15
    assert result.startswith("timed out after 2 seconds")
    time.sleep(6)
    assert not (run.repo_dir / "background").exists()
    assert not (run.repo_dir / "foreground").exists()
    assert events(store, "command")[-1][1]["timed_out"] is True


@requires_docker
def test_file_tools_reject_paths_outside_repo(village_env):
    run, store, sandbox, tools = village_env
    alice = tools["alice"]
    assert alice["write_file"].invoke({"path": "../etc/evil", "content": "x"}).startswith("Rejected")
    assert alice["write_file"].invoke({"path": "/tmp/evil", "content": "x"}).startswith("Rejected")
    assert alice["read_file"].invoke({"path": "/etc/passwd"}).startswith("Rejected")
    assert len([e for _, e in events(store, "write_file") if "error" in e]) == 2
    assert not (run.repo_dir.parent / "etc").exists()


@requires_docker
def test_isolation_and_output_truncation(village_env):
    run, store, sandbox, tools = village_env
    alice, bob = tools["alice"], tools["bob"]
    noisy = alice["run_command"].invoke({"command": "python -c \"print('x' * 200000)\""})
    assert "bytes truncated" in noisy and len(noisy) < 6000

    environment = alice["run_command"].invoke({"command": "env; id -u"})
    assert "API_KEY" not in environment and "\n1000\n" in environment

    alice["run_command"].invoke({"command": "echo secret > /tmp/private"})
    assert "No such file" in bob["run_command"].invoke({"command": "cat /tmp/private"})

    inspect = json.loads(subprocess.run(["docker", "inspect", sandbox.container("alice")],
                                        capture_output=True, text=True, check=True).stdout)[0]
    assert [m["Destination"] for m in inspect["Mounts"]] == ["/repo"]
    assert inspect["HostConfig"]["Privileged"] is False
    assert inspect["HostConfig"]["Memory"] > 0 and inspect["HostConfig"]["PidsLimit"] > 0
    assert inspect["HostConfig"]["NetworkMode"] == "none"
    assert "docker.sock" not in json.dumps(inspect["Mounts"])


class InterruptingModel(ScriptedModel):
    error: type = KeyboardInterrupt

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise self.error("simulated")


@requires_docker
def test_village_removes_containers_on_interrupt_and_errors(tmp_path, monkeypatch):
    monkeypatch.setattr(persistence, "RUNS_DIR", tmp_path / "runs")
    names = village.MODEL_NAME
    monkeypatch.setattr(village, "make_models",
                        lambda: {name: InterruptingModel(responses=[]) for name in names})
    monkeypatch.setattr(sys, "argv", ["village.py", "--goal", "test", "--offline"])
    with pytest.raises(KeyboardInterrupt):
        village.run_model()
    run_dir = next((tmp_path / "runs").iterdir())
    assert containers(run_dir.name) == []

    monkeypatch.setattr(village, "make_models",
                        lambda: {name: InterruptingModel(responses=[], error=RuntimeError) for name in names})
    monkeypatch.setattr(sys, "argv", ["village.py", "--resume", run_dir.name, "--offline", "--rounds", "2"])
    village.run_model()
    assert containers(run_dir.name) == []
    store = Store(str(run_dir / "village.db"))
    kinds = [e.type for e in store.read_event()]
    assert kinds.count("turn_error") == len(names)
    assert "stopped" in kinds
    configs = [json.loads(e.content) for e in store.read_event() if e.type == "run_config"]
    assert [c["mode"] for c in configs] == ["start", "resume"]
    assert configs[1]["limits"]["rounds"] == 2 and configs[1]["models"]["claude"]
    starts = [json.loads(e.content) for e in store.read_event() if e.type == "turn_start"]
    assert [s["round"] for s in starts] == [1] * (len(names) + 1)
    ends = [json.loads(e.content)["status"] for e in store.read_event() if e.type == "turn_end"]
    assert ends == ["error"] * len(names)
