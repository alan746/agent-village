from store import Store
from villager import build_villager
from persistence import open_run, limits_from

from dotenv import load_dotenv
load_dotenv()
from models import make_models
from langgraph.checkpoint.sqlite import SqliteSaver
import sys
import sqlite3

MODEL_NAME = ["claude", "chatgpt", "deepseek", "gemini"]
ROLES = {"claude": "leader", "chatgpt": "worker", "deepseek": "worker", "gemini": "worker"}

def run_model():
    run, args = open_run(sys.argv[1:])
    limits = limits_from(args)
    print(f"Run {run.run_id}: {run.directory}", file=sys.stderr)
    path = run.db_path
    store = Store(path)
    checkpointer = SqliteSaver(sqlite3.connect(path, check_same_thread=False))
    models = make_models()
    villagers = {name: build_villager(name, ROLES[name], run.goal, models[name], path, store, limits, checkpointer)
                 for name in MODEL_NAME}
    config = {"recursion_limit": 4 * limits.max_tool_rounds + 10}
    step = run.step
    end_step = step + limits.rounds * len(MODEL_NAME)
    balance = store.check_balance(limits.input_budget, limits.output_budget)
    failures = 0
    while (step < end_step and balance["remaining_input_tokens"] > 0
            and balance["remaining_output_tokens"] > 0):
        name = MODEL_NAME[step % len(MODEL_NAME)]
        print(f"round {step // len(MODEL_NAME) + 1}: {name}", file=sys.stderr)
        try:
            villagers[name].invoke({"messages": []}, {**config, "configurable": {"thread_id": name}})
            failures = 0
        except Exception as error:
            failures += 1
            store.log(name, "turn_error", f"{type(error).__name__}: {error}")
            print(f"{name}: turn failed ({type(error).__name__}: {error})", file=sys.stderr)
        balance = store.check_balance(limits.input_budget, limits.output_budget)
        step += 1
        store.update_step()
        if failures >= len(MODEL_NAME):
            store.log("village", "stopped", f"{failures} consecutive failed turns")
            print(f"Stopping: {failures} consecutive failed turns", file=sys.stderr)
            break

if __name__ == "__main__":
    run_model()
