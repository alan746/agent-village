import argparse
import json
import os
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from langgraph.checkpoint.sqlite import SqliteSaver
from store import Store

if os.name == "nt":
    import msvcrt
else:
    import fcntl

GOAL = ("Together, build and maintain an open-source tool that is useful to "
        "university students. You decide what to build and how to organize.")
RUNS_DIR = Path("runs")
DB_NAME = "village.db"
REPO_NAME = "repo"
LOCK_NAME = "village.lock"

@dataclass
class Limits:
    rounds: int = 10
    max_tool_rounds: int = 15
    input_budget: int = 3_000_000
    output_budget: int = 300_000
    compact_trigger: int = 40_000
    command_timeout: int = 120

@dataclass
class Run:
    run_id: str
    directory: Path
    goal: str
    step: int
    limits: Limits
    network: bool

    @property
    def db_path(self) -> str:
        return str(self.directory / DB_NAME)

    @property
    def repo_dir(self) -> Path:
        return self.directory / REPO_NAME

class LatestCheckpointSaver(SqliteSaver):
    def put(self, config, checkpoint, metadata, new_versions):
        saved = super().put(config, checkpoint, metadata, new_versions)
        key = (str(saved["configurable"]["thread_id"]), saved["configurable"]["checkpoint_ns"], checkpoint["id"])
        with self.cursor() as cur:
            for table in ("checkpoints", "writes"):
                cur.execute(f"DELETE FROM {table} WHERE thread_id = ? AND checkpoint_ns = ? AND checkpoint_id < ?", key)
        return saved

class RunLock:
    def __init__(self, directory: Path):
        self.path = Path(directory) / LOCK_NAME
        self.fd = None

    def acquire(self) -> bool:
        fd = os.open(self.path, os.O_RDWR | os.O_CREAT)
        try:
            if os.name == "nt":
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            os.close(fd)
            return False
        self.fd = fd
        return True

    def release(self):
        if self.fd is None:
            return
        if os.name == "nt":
            os.lseek(self.fd, 0, os.SEEK_SET)
            msvcrt.locking(self.fd, msvcrt.LK_UNLCK, 1)
        os.close(self.fd)
        self.fd = None

def positive_int(value: str) -> int:
    number = int(value.replace("_", ""))
    if number < 1:
        raise argparse.ArgumentTypeError(f"{value} is not a positive integer")
    return number

SAVED_LIMITS = {
    "max_tool_rounds": "model calls with tool use a villager may make in one turn",
    "input_budget": "input tokens the whole village may spend, cached tokens included",
    "output_budget": "output tokens the whole village may spend",
    "compact_trigger": "approximate context size in tokens above which a villager's memory is compacted",
    "command_timeout": "longest time in seconds a shell command in a container may run",
}

def make_parser() -> argparse.ArgumentParser:
    defaults = Limits()
    parser = argparse.ArgumentParser(prog="village.py", description="Run a village of LLM agents.",
                                     formatter_class=argparse.ArgumentDefaultsHelpFormatter,
                                     epilog="The defaults shown are for a new run. On --resume, the run's earlier "
                                            "limits are kept unless given again, --rounds counts only this "
                                            "invocation, and the network setting cannot change after a run "
                                            "has started.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--goal", nargs="*", metavar="WORD",
                      help="start a new run with this goal; without words the default goal is used")
    mode.add_argument("--resume", nargs="?", const="", metavar="RUN",
                      help="resume a run, given as a run id, run directory or database path; "
                           "without a value the latest run is used")
    parser.add_argument("--rounds", type=positive_int, default=defaults.rounds,
                        help="rounds to run in this invocation; in one round every villager takes one turn")
    for name, text in SAVED_LIMITS.items():
        parser.add_argument(f"--{name.replace('_', '-')}", type=positive_int, default=argparse.SUPPRESS,
                            help=f"{text} (default: {getattr(defaults, name)}; on --resume the run's earlier value)")
    parser.add_argument("--offline", action="store_true",
                        help="start the villagers' containers without network access; "
                             "fixed when the run is created")
    return parser

def limits_from(args: argparse.Namespace, saved: dict | None = None) -> Limits:
    values = asdict(Limits())
    if isinstance(saved, dict):
        values.update({name: value for name, value in saved.items()
                       if name in SAVED_LIMITS and isinstance(value, int) and value > 0})
    values.update({name: getattr(args, name) for name in SAVED_LIMITS if hasattr(args, name)})
    values["rounds"] = args.rounds
    return Limits(**values)

def saved_config(store: Store) -> dict:
    content = store.last_event("run_config")
    try:
        data = json.loads(content) if content else {}
    except ValueError:
        data = {}
    return data if isinstance(data, dict) else {}

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
        run = Run(run_id, directory, " ".join(args.goal) or GOAL, 0, limits_from(args), not args.offline)
        Store(run.db_path).set_goal(run.goal)
        return run, args
    directory = find_run(args.resume)
    if directory is None:
        parser.error(f"no run found for {args.resume!r}" if args.resume else "there is no run to resume in runs/")
    (directory / REPO_NAME).mkdir(exist_ok=True)
    store = Store(str(directory / DB_NAME))
    run_state = store.read_run_state()
    saved = saved_config(store)
    network = saved.get("network")
    if not isinstance(network, bool):
        network = not args.offline
    elif network and args.offline:
        parser.error(f"run {directory.name} was started with network access, and the network setting cannot "
                     "change after a run has started; resume it without --offline")
    return Run(directory.name, directory, run_state["goal"], run_state["step"],
               limits_from(args, saved.get("limits")), network), args
