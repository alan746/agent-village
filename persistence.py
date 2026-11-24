import argparse
from pathlib import Path
from store import Store

GOAL = ("Together, build and maintain an open-source tool that is useful to "
        "university students. You decide what to build and how to organize.")

def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="village.py", description="Run a village of LLM agents.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--goal", nargs="*", metavar="WORD",
                      help="start a new run with this goal; without words the default goal is used")
    mode.add_argument("--resume", nargs="?", const="", metavar="DB",
                      help="resume a run from its database; without a path the latest run is used")
    return parser

def set_initial_values(argv: list[str]) -> dict:
    parser = make_parser()
    args = parser.parse_args(argv)
    if args.goal is not None:
        return {"goal": " ".join(args.goal) or GOAL}
    if args.resume:
        path = Path(args.resume)
        if not path.is_file():
            parser.error(f"no run database at {path}")
    else:
        runs = sorted(Path("runs").glob("*.db"))
        if not runs:
            parser.error("there is no run to resume in runs/")
        path = runs[-1]
    return resume_initial_values(str(path))

def resume_initial_values(path: str) -> dict:
    run_state = Store(path).read_run_state()
    return {"path": path, "goal": run_state["goal"], "step": run_state["step"]}
