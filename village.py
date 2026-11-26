from store import Store
from villager import build_villager
from persistence import open_run, LatestCheckpointSaver, RunLock
from sandbox import Sandbox, docker_available

from dotenv import load_dotenv
load_dotenv()
from models import make_models, MODEL_IDS
import json
import sys
import sqlite3
from dataclasses import asdict

MODEL_NAME = ["claude", "chatgpt", "deepseek", "gemini"]
ROLES = {"claude": "leader", "chatgpt": "worker", "deepseek": "worker", "gemini": "worker"}

def budget_left(balance: dict) -> bool:
    return balance["remaining_input_tokens"] > 0 and balance["remaining_output_tokens"] > 0

def end_session(store: Store, reason: str, turns: int, failed: int) -> dict:
    outcome = {"reason": reason, "turns": turns, "ok": turns - failed, "failed": failed}
    store.log("village", "session_end", json.dumps(outcome))
    return outcome

def run_turns(villagers: dict, store: Store, limits, step: int) -> dict:
    config = {"recursion_limit": 4 * limits.max_tool_rounds + 10}
    end_step = step + limits.rounds * len(MODEL_NAME)
    turns = failed = failures = 0
    while step < end_step:
        if not budget_left(store.check_balance(limits.input_budget, limits.output_budget)):
            return end_session(store, "budget_exhausted", turns, failed)
        name = MODEL_NAME[step % len(MODEL_NAME)]
        turn = {"step": step, "round": step // len(MODEL_NAME) + 1}
        print(f"round {turn['round']}: {name}", file=sys.stderr)
        store.log(name, "turn_start", json.dumps(turn))
        turns += 1
        try:
            villagers[name].invoke({"messages": []}, {**config, "configurable": {"thread_id": name}})
            failures = 0
            store.log(name, "turn_end", json.dumps({**turn, "status": "ok"}))
        except Exception as error:
            failures += 1
            failed += 1
            store.log(name, "turn_error", f"{type(error).__name__}: {error}")
            store.log(name, "turn_end", json.dumps({**turn, "status": "error"}))
            print(f"{name}: turn failed ({type(error).__name__}: {error})", file=sys.stderr)
        step += 1
        store.update_step()
        if failures >= len(MODEL_NAME):
            print(f"Stopping: {failures} consecutive failed turns", file=sys.stderr)
            return end_session(store, "consecutive_failures", turns, failed)
    return end_session(store, "rounds_done", turns, failed)

def run_model():
    run, args = open_run(sys.argv[1:])
    lock = RunLock(run.directory)
    if not lock.acquire():
        raise SystemExit(f"Run {run.run_id} is already in use by another village.py process ({lock.path} is "
                         "locked); wait for that process to end before resuming this run.")
    try:
        run_session(run, args.goal is not None)
    finally:
        lock.release()

def run_session(run, new: bool):
    limits = run.limits
    if not docker_available():
        raise SystemExit("Docker is not available; start Docker Desktop and check that `docker info` works.")
    print(f"Run {run.run_id}: {run.directory}", file=sys.stderr)
    path = run.db_path
    store = Store(path)
    store.log("village", "run_config", json.dumps({
        "mode": "start" if new else "resume", "step": run.step,
        "round": run.step // len(MODEL_NAME) + 1, "goal": run.goal,
        "models": {name: MODEL_IDS[name] for name in MODEL_NAME}, "roles": ROLES,
        "limits": asdict(limits), "network": run.network}))
    checkpointer = LatestCheckpointSaver(sqlite3.connect(path, check_same_thread=False))
    models = make_models()
    sandbox = Sandbox(run.run_id, run.repo_dir, network=run.network)
    try:
        if budget_left(store.check_balance(limits.input_budget, limits.output_budget)):
            sandbox.start(MODEL_NAME)
            store.log("village", "containers", f"started {len(MODEL_NAME)} containers, network {'on' if run.network else 'off'}")
            villagers = {name: build_villager(name, ROLES[name], run.goal, models[name], path, store, limits,
                                              checkpointer, sandbox)
                         for name in MODEL_NAME}
            outcome = run_turns(villagers, store, limits, run.step)
        else:
            outcome = end_session(store, "budget_exhausted", 0, 0)
    finally:
        removed = sandbox.close()
        store.log("village", "containers", f"removed {removed} containers")
        print(f"Removed {removed} containers. The shared project is in {run.repo_dir}", file=sys.stderr)
    if outcome["reason"] == "consecutive_failures":
        raise SystemExit(f"Run {run.run_id} stopped because {len(MODEL_NAME)} turns in a row failed "
                         f"({outcome['failed']} of {outcome['turns']} turns failed in this invocation).")
    if outcome["turns"] == 0:
        balance = store.check_balance(limits.input_budget, limits.output_budget)
        spent_input = limits.input_budget - balance["remaining_input_tokens"]
        spent_output = limits.output_budget - balance["remaining_output_tokens"]
        raise SystemExit(f"Run {run.run_id} has no budget left, so no turn was run: {spent_input:,} of "
                         f"{limits.input_budget:,} input tokens and {spent_output:,} of {limits.output_budget:,} "
                         "output tokens are spent. Resume with a larger --input-budget or --output-budget.")

if __name__ == "__main__":
    run_model()
