import argparse
import time
from dataclasses import dataclass
from pathlib import Path
from store import Store

GOAL = ("Together, build and maintain an open-source tool that is useful to "
        "university students. You decide what to build and how to organize.")
RUNS_DIR = Path("runs")
DB_NAME = "village.db"
REPO_NAME = "repo"

@dataclass
class Run:
    run_id: str
    directory: Path
    goal: str
    step: int

    @property
    def db_path(self) -> str:
        return str(self.directory / DB_NAME)

    @property
    def repo_dir(self) -> Path:
        return self.directory / REPO_NAME

@dataclass
class Limits:
    rounds: int = 10
    max_tool_rounds: int = 15
    input_budget: int = 3_000_000
    output_budget: int = 300_000
    compact_trigger: int = 40_000
    command_timeout: int = 120

def positive_int(value: str) -> int:
    number = int(value.replace("_", ""))
    if number < 1:
        raise argparse.ArgumentTypeError(f"{value} is not a positive integer")
    return number

def make_parser() -> argparse.ArgumentParser:
    defaults = Limits()
    parser = argparse.ArgumentParser(prog="village.py", description="Run a village of LLM agents.",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--goal", nargs="*", metavar="WORD",
                      help="start a new run with this goal; without words the default goal is used")
    mode.add_argument("--resume", nargs="?", const="", metavar="RUN",
                      help="resume a run, given as a run id, run directory or database path; "
                           "without a value the latest run is used")
    parser.add_argument("--rounds", type=positive_int, default=defaults.rounds,
                        help="rounds to run in this invocation; in one round every villager takes one turn")
    parser.add_argument("--max-tool-rounds", type=positive_int, default=defaults.max_tool_rounds,
                        help="model calls with tool use a villager may make in one turn")
    parser.add_argument("--input-budget", type=positive_int, default=defaults.input_budget,
                        help="input tokens the whole village may spend, cached tokens included")
    parser.add_argument("--output-budget", type=positive_int, default=defaults.output_budget,
                        help="output tokens the whole village may spend")
    parser.add_argument("--compact-trigger", type=positive_int, default=defaults.compact_trigger,
                        help="approximate context size in tokens above which a villager's memory is compacted")
    parser.add_argument("--command-timeout", type=positive_int, default=defaults.command_timeout,
                        help="longest time in seconds a shell command in a container may run")
    parser.add_argument("--offline", action="store_true",
                        help="start the villagers' containers without network access")
    return parser

def limits_from(args: argparse.Namespace) -> Limits:
    return Limits(args.rounds, args.max_tool_rounds, args.input_budget, args.output_budget,
                  args.compact_trigger, args.command_timeout)

def find_run(value: str) -> Path | None:
    if not value:
        runs = sorted(path.parent for path in RUNS_DIR.glob(f"*/{DB_NAME}"))
        return runs[-1] if runs else None
    path = Path(value)
    for candidate in (path, RUNS_DIR / value):
        if candidate.is_file() and candidate.name == DB_NAME:
            return candidate.parent
        if (candidate / DB_NAME).is_file():
            return candidate
    return None

def open_run(argv: list[str]) -> tuple[Run, argparse.Namespace]:
    parser = make_parser()
    args = parser.parse_args(argv)
    if args.goal is not None:
        run_id = time.strftime("%Y%m%d_%H%M%S")
        directory = RUNS_DIR / run_id
        if directory.exists():
            parser.error(f"run directory {directory} already exists")
        (directory / REPO_NAME).mkdir(parents=True)
        run = Run(run_id, directory, " ".join(args.goal) or GOAL, 0)
        Store(run.db_path).set_goal(run.goal)
        return run, args
    directory = find_run(args.resume)
    if directory is None:
        parser.error(f"no run found for {args.resume!r}" if args.resume else "there is no run to resume in runs/")
    (directory / REPO_NAME).mkdir(exist_ok=True)
    run_state = Store(str(directory / DB_NAME)).read_run_state()
    return Run(directory.name, directory, run_state["goal"], run_state["step"]), args
