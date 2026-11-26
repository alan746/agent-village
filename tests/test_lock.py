import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from persistence import RunLock
from store import Store
from test_settings import FakeSandbox, run_village, runs

HOLDER = """
import os, sys, time
sys.path.insert(0, sys.argv[1])
from persistence import RunLock
lock = RunLock(sys.argv[2])
print(os.getpid() if lock.acquire() else "busy", flush=True)
time.sleep(60)
"""


def test_lock_refuses_a_second_holder_until_released(tmp_path):
    first, second = RunLock(tmp_path), RunLock(tmp_path)
    assert first.acquire()
    assert not second.acquire()
    first.release()
    assert second.acquire()
    second.release()
    assert first.acquire()
    first.release()


def test_lock_is_released_when_the_holder_process_dies(tmp_path):
    root = str(Path(__file__).resolve().parent.parent)
    holder = subprocess.Popen([sys.executable, "-c", HOLDER, root, str(tmp_path)], stdout=subprocess.PIPE, text=True)
    try:
        pid = holder.stdout.readline().strip()
        assert pid.isdigit()
        assert not RunLock(tmp_path).acquire()
        os.kill(int(pid), getattr(signal, "SIGKILL", signal.SIGTERM))
        holder.wait(30)
    finally:
        holder.kill()
        holder.stdout.close()
    lock = RunLock(tmp_path)
    deadline = time.monotonic() + 10
    while not lock.acquire():
        assert time.monotonic() < deadline, "the lock was not released after its holder was killed"
        time.sleep(0.1)
    lock.release()


def test_second_village_on_the_same_run_exits_before_touching_containers(runs, monkeypatch):
    run_village(monkeypatch, ["--goal", "locked", "--rounds", "1"])
    run_dir = next(runs.iterdir())
    FakeSandbox.created = []
    store = Store(str(run_dir / "village.db"))
    events_before = len(store.read_event())

    lock = RunLock(run_dir)
    assert lock.acquire()
    try:
        with pytest.raises(SystemExit) as info:
            run_village(monkeypatch, ["--resume", run_dir.name])
    finally:
        lock.release()
    assert info.value.code not in (0, None)
    assert f"Run {run_dir.name} is already in use" in str(info.value.code)
    assert FakeSandbox.created == []
    assert len(store.read_event()) == events_before

    run_village(monkeypatch, ["--resume", run_dir.name, "--rounds", "1"])
    assert [sandbox.calls for sandbox in FakeSandbox.created] == [["start", "close"]]
    modes = [json.loads(e.content)["mode"] for e in store.read_event() if e.type == "run_config"]
    assert modes == ["start", "resume"]
