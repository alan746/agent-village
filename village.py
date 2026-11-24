from store import Store
from villager import build_villager
from persistence import set_initial_values

from dotenv import load_dotenv
load_dotenv()
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_deepseek import ChatDeepSeek
from langgraph.checkpoint.sqlite import SqliteSaver
import time
import sys
from pathlib import Path
import sqlite3

MAX_STEP = 3
INPUT_LIMIT = 50_000
OUTPUT_LIMIT = 10_000
MAX_TOKENS = 10_000
MODEL_NAME = ["claude", "chatgpt", "deepseek"]
ROLES = {"claude": "leader", "chatgpt": "worker", "deepseek": "worker"}

def make_models() -> dict:
    return {
        "claude": ChatAnthropic(
            model="claude-haiku-5-5",
            max_tokens=MAX_TOKENS,
            effort="low",                       
        ),
        "chatgpt": ChatOpenAI(
            model="gpt-6-luna",
            max_tokens=MAX_TOKENS,
            reasoning={"effort": "low"},        
        ),
        "deepseek": ChatDeepSeek(
            model="deepseek-flash",
            max_tokens=MAX_TOKENS,
            extra_body={"thinking": {"type": "disabled"}},
        ),
    }


def run_model():
    initial_values = set_initial_values(sys.argv[1:])
    Path("runs").mkdir(exist_ok=True)
    if "path" in initial_values:
        path = initial_values.get("path")
        store = Store(path)
    else:
        path = f"runs/village_{time.strftime('%Y%m%d_%H%M%S')}.db"
        store =  Store(path)
    goal = initial_values["goal"]
    store.set_goal(goal)
    conn = sqlite3.connect(path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    models = make_models()
    balance = store.check_balance(INPUT_LIMIT, OUTPUT_LIMIT)
    villagers = {}
    for name in MODEL_NAME:
        villagers[name] = (build_villager(name, ROLES[name], goal, models[name], path, store, INPUT_LIMIT, OUTPUT_LIMIT, checkpointer))
    step = initial_values.get("step", 0)
    end_step = MAX_STEP + step
    failures = 0
    while (step < end_step and balance["remaining_input_tokens"] > 0
            and balance["remaining_output_tokens"] > 0):
        name = MODEL_NAME[step % len(MODEL_NAME)]
        try:
            villagers[name].invoke({"messages": []}, {"configurable": {"thread_id": name}, "recursion_limit": 50})
            failures = 0
        except Exception as error:
            failures += 1
            store.log(name, "turn_error", f"{type(error).__name__}: {error}")
            print(f"{name}: turn failed ({type(error).__name__}: {error})", file=sys.stderr)
        balance = store.check_balance(INPUT_LIMIT, OUTPUT_LIMIT)
        step += 1
        store.update_step()
        if failures >= len(MODEL_NAME):
            store.log("village", "stopped", f"{failures} consecutive failed turns")
            print(f"Stopping: {failures} consecutive failed turns", file=sys.stderr)
            break

if __name__ == "__main__":
    run_model()

