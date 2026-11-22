from pathlib import Path
from store import Store

GOAL = ("Together, build and maintain an open-source tool that is useful to "
        "university students. You decide what to build and how to organize.")

def set_initial_values(argv: list[str]):
    initial_values = {}
    if len(argv) < 2:
        raise SystemExit('Need more arguments')
    mode = argv[1]
    initial_values["mode"] = mode
    if len(argv) == 2:
        if mode == "--goal":
            initial_values["goal"] = GOAL
        elif mode == "--resume":
            if len(sorted(Path("runs").glob("*.db"))) == 0:
                    raise ValueError("no .db file exist")
            path = sorted(Path("runs").glob("*.db"))[-1]
            initial_values = resume_initial_values(path)
        else:
            raise ValueError("argument does not match --resume or --goal")
    if len(argv) == 3:
        if mode == "--goal":
            initial_values["goal"] = argv[2]
        elif mode == "--resume" and Path(argv[2]) in Path("runs").glob("*.db"):
            initial_values = resume_initial_values(argv[2])
        else:
            raise ValueError("either mode is not found or filename is not correct")
    return initial_values

def resume_initial_values(path: str) -> dict:
    initial_values = {}
    store = Store(path)
    goal = (store.read_run_state())["goal"]
    step = (store.read_run_state())["step"]
    initial_values["path"] = path
    initial_values["goal"] = goal
    initial_values["step"] = step
    return initial_values