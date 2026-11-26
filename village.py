from store import Store
from villager import build_villager
from persistence import open_run, limits_from, LatestCheckpointSaver
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

def run_turns(villagers: dict, store: Store, limits, step: int):
    config = {"recursion_limit": 4 * limits.max_tool_rounds + 10}
    end_step = step + limits.rounds * len(MODEL_NAME)
    balance = store.check_balance(limits.input_budget, limits.output_budget)
    failures = 0
    while (step < end_step and balance["remaining_input_tokens"] > 0
            and balance["remaining_output_tokens"] > 0):
        name = MODEL_NAME[step % len(MODEL_NAME)]
        turn = {"step": step, "round": step // len(MODEL_NAME) + 1}
        print(f"round {turn['round']}: {name}", file=sys.stderr)
        store.log(name, "turn_start", json.dumps(turn))
        try:
            villagers[name].invoke({"messages": []}, {**config, "configurable": {"thread_id": name}})
            failures = 0
            store.log(name, "turn_end", json.dumps({**turn, "status": "ok"}))
        except Exception as error:
            failures += 1
            store.log(name, "turn_error", f"{type(error).__name__}: {error}")
            store.log(name, "turn_end", json.dumps({**turn, "status": "error"}))
            print(f"{name}: turn failed ({type(error).__name__}: {error})", file=sys.stderr)
        balance = store.check_balance(limits.input_budget, limits.output_budget)
        step += 1
        store.update_step()
        if failures >= len(MODEL_NAME):
            store.log("village", "stopped", f"{failures} consecutive failed turns")
            print(f"Stopping: {failures} consecutive failed turns", file=sys.stderr)
            break

def run_model():
    run, args = open_run(sys.argv[1:])
    limits = limits_from(args)
    if not docker_available():
        raise SystemExit("Docker is not available; start Docker Desktop and check that `docker info` works.")
    print(f"Run {run.run_id}: {run.directory}", file=sys.stderr)
    path = run.db_path
    store = Store(path)
    store.log("village", "run_config", json.dumps({
        "mode": "start" if args.goal is not None else "resume", "step": run.step,
        "round": run.step // len(MODEL_NAME) + 1, "goal": run.goal,
        "models": {name: MODEL_IDS[name] for name in MODEL_NAME}, "roles": ROLES,
        "limits": asdict(limits), "network": not args.offline}))
    checkpointer = LatestCheckpointSaver(sqlite3.connect(path, check_same_thread=False))
    models = make_models()
    sandbox = Sandbox(run.run_id, run.repo_dir, network=not args.offline)
    try:
        sandbox.start(MODEL_NAME)
        store.log("village", "containers", f"started {len(MODEL_NAME)} containers, network {'off' if args.offline else 'on'}")
        villagers = {name: build_villager(name, ROLES[name], run.goal, models[name], path, store, limits,
                                          checkpointer, sandbox)
                     for name in MODEL_NAME}
        run_turns(villagers, store, limits, run.step)
    finally:
        removed = sandbox.close()
        store.log("village", "containers", f"removed {removed} containers")
        print(f"Removed {removed} containers. The shared project is in {run.repo_dir}", file=sys.stderr)

if __name__ == "__main__":
    run_model()
