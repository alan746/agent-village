import argparse
import json
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path

from persistence import DB_NAME, find_run

TEXT_LIMIT = 3000
RESULT_LIMIT = 1500
COMMAND_LIMIT = 1500
COLLAPSE_LINES = 12
OWN_EVENT_TOOLS = {"run_command", "write_file", "read_file", "post_chat", "post_task", "take_task",
                   "submit_task", "done_task"}
VILLAGE_EVENTS = {"run_config", "containers", "stopped"}
QUIET_EVENTS = {"spend", "wake", "turn_start", "turn_end"}

@dataclass
class Event:
    id: int
    actor: str
    type: str
    content: str
    ts: float

    def data(self):
        try:
            value = json.loads(self.content)
        except (TypeError, ValueError):
            return None
        return value if isinstance(value, (dict, list)) else None

@dataclass
class Usage:
    calls: int = 0
    input: int = 0
    output: int = 0
    cache_read: int = 0
    cache_write: int = 0

    def add(self, input_tokens, output_tokens, cache_read, cache_write):
        self.calls += 1
        self.input += input_tokens or 0
        self.output += output_tokens or 0
        self.cache_read += cache_read or 0
        self.cache_write += cache_write or 0

@dataclass
class Turn:
    actor: str
    round: int
    step: int | None
    start: float
    events: list = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    status: str | None = None

def load(db_path: Path):
    conn = sqlite3.connect(db_path)
    events = [Event(*row) for row in conn.execute("SELECT id, actor, type, content, ts FROM event ORDER BY id")]
    columns = {row[1] for row in conn.execute("PRAGMA table_info(budget)")}
    cache = ("cache_read_tokens, cache_write_tokens" if "cache_read_tokens" in columns else "0, 0")
    budget = conn.execute(f"SELECT actor, input_tokens, output_tokens, {cache}, ts FROM budget ORDER BY id").fetchall()
    goal = conn.execute("SELECT goal FROM run_state").fetchone()
    conn.close()
    return events, budget, goal[0] if goal else ""

def build_timeline(events: list[Event]):
    marked = any(e.type == "turn_start" for e in events)
    starter = "turn_start" if marked else "wake"
    actors = []
    timeline, turns, current = [], [], None
    for event in events:
        if event.actor == "village" or event.type in VILLAGE_EVENTS:
            timeline.append(event)
            continue
        if event.type == starter:
            if marked:
                info = event.data() or {}
                current = Turn(event.actor, info.get("round", 0), info.get("step"), event.ts)
            else:
                if event.actor not in actors:
                    actors.append(event.actor)
                current = Turn(event.actor, len(turns) // max(len(actors), 1) + 1, None, event.ts)
            turns.append(current)
            timeline.append(current)
            continue
        if event.type == "turn_end" and current is not None:
            current.status = (event.data() or {}).get("status")
        if current is None or current.actor != event.actor:
            current = Turn(event.actor, current.round if current else 0, None, event.ts)
            turns.append(current)
            timeline.append(current)
        current.events.append(event)
    if not marked and actors:
        size = len(actors)
        for index, turn in enumerate(turns):
            turn.round = index // size + 1
    return timeline, turns, marked

def assign_usage(turns: list[Turn], budget: list) -> dict[str, Usage]:
    totals = {}
    for actor, input_tokens, output_tokens, cache_read, cache_write, ts in budget:
        totals.setdefault(actor, Usage()).add(input_tokens, output_tokens, cache_read, cache_write)
        owner = None
        for turn in turns:
            if turn.actor == actor and turn.start <= ts:
                owner = turn
        if owner is not None:
            owner.usage.add(input_tokens, output_tokens, cache_read, cache_write)
    return totals

def clip(text: str, limit: int) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return f"{text[:limit]}\n[... {len(text) - limit} more characters not shown ...]"

def fence(text: str, language: str = "") -> str:
    longest = max((len(run) for run in re.findall(r"`+", text)), default=0)
    ticks = "`" * max(3, longest + 1)
    return f"{ticks}{language}\n{text.rstrip()}\n{ticks}"

def quote(text: str) -> str:
    return "\n".join(f"> {line}" if line else ">" for line in text.strip().splitlines())

def inline(text: str) -> bool:
    return "\n" not in text and "`" not in text and len(text) <= 120

def stamp(ts: float, full: bool = False) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S UTC" if full else "%H:%M:%S", time.gmtime(ts))

def number(value: int) -> str:
    return f"{value:,}"

def failed(data: dict) -> bool:
    return bool(data.get("timed_out")) or data.get("exit_code") not in (0, None)

def render_command(actor: str, data: dict) -> str:
    if data.get("timed_out"):
        status = f"**[FAILED]** timed out, exit code {data.get('exit_code')}"
    elif failed(data):
        status = f"**[FAILED]** exit code {data.get('exit_code')}"
    else:
        status = f"exit code {data.get('exit_code')}"
    command = data.get("command", "")
    outputs = [(name, data.get(name) or "") for name in ("stdout", "stderr")]
    outputs = [(name, text) for name, text in outputs if text.strip()]
    if not outputs:
        status += ", no output"
    if inline(command):
        parts = [f"**{actor} ran** `{command}` · {status}"]
    else:
        parts = [f"**{actor} ran** · {status}", fence(clip(command, COMMAND_LIMIT), "bash")]
    if not outputs:
        return "\n\n".join(parts)
    lines = sum(text.count("\n") + 1 for _, text in outputs)
    body = "\n\n".join(f"{name}:\n\n{fence(text)}" for name, text in outputs)
    if failed(data) or lines <= COLLAPSE_LINES:
        parts.append(body)
    else:
        parts.append(f"<details><summary>output, {lines} lines</summary>\n\n{body}\n\n</details>")
    return "\n\n".join(parts)

def render_board(event: Event) -> str:
    data = event.data()
    if data is None:
        return f"**task board:** {event.type.replace('_', ' ')}: {event.content}"
    outcome = data.get("outcome", "")
    if event.type == "post_task":
        return f"**task board:** {outcome}\n\n{quote(clip(data.get('description', ''), RESULT_LIMIT))}"
    if event.type == "submit_task":
        return (f"**task board:** submitted to task {data.get('task_id')}: {outcome}\n\n"
                f"{quote(clip(data.get('result', ''), RESULT_LIMIT))}")
    return f"**task board:** {outcome}"

def render_event(event: Event) -> str | None:
    data = event.data()
    if event.type == "say":
        return f"**{event.actor} said:**\n\n{quote(clip(event.content, TEXT_LIMIT))}"
    if event.type == "post_chat":
        return f"**{event.actor} posted to chat:**\n\n{quote(clip(event.content, TEXT_LIMIT))}"
    if event.type == "command" and data:
        return render_command(event.actor, data)
    if event.type == "write_file" and data:
        if "error" in data:
            return f"**[REJECTED]** write to `{data.get('path')}`: {data['error']}"
        if data.get("exit_code") not in (0, None):
            return f"**[FAILED]** write to `{data.get('path')}`: {clip(data.get('stderr', ''), 500)}"
        return f"**wrote** `{data.get('path')}` ({number(data.get('bytes', 0))} bytes)"
    if event.type == "read_file" and data:
        if "error" in data:
            return f"**[REJECTED]** read of `{data.get('path')}`: {data['error']}"
        if data.get("exit_code") not in (0, None):
            return f"**[FAILED]** read of `{data.get('path')}`: {clip(data.get('stderr', ''), 500)}"
        return f"**read** `{data.get('path')}`"
    if event.type in ("post_task", "take_task", "submit_task", "done_task"):
        return render_board(event)
    if event.type == "compact":
        return f"**[COMPACTED]** memory compacted: {event.content}"
    if event.type == "turn_error":
        return f"**[TURN ERROR]** {clip(event.content, 1000)}"
    if event.type in ("resume_repair", "prefix_changed", "thinking_dropped"):
        return f"**[NOTE]** {event.type.replace('_', ' ')}: {clip(event.content, 500)}"
    return None

def tool_name(event: Event) -> str:
    return event.content.split(":", 1)[0].strip()

def render_turn(turn: Turn, roles: dict) -> str:
    role = f" ({roles[turn.actor]})" if turn.actor in roles else ""
    lines = [f"### {turn.actor}{role} · {stamp(turn.start)}"]
    checked = []
    for event in turn.events:
        if event.type == "tool_use":
            name = tool_name(event)
            if name not in OWN_EVENT_TOOLS:
                checked.append(name)
            continue
        if event.type in QUIET_EVENTS:
            continue
        if checked:
            lines.append(f"*checked: {', '.join(checked)}*")
            checked = []
        rendered = render_event(event)
        if rendered:
            lines.append(rendered)
    if checked:
        lines.append(f"*checked: {', '.join(checked)}*")
    if len(lines) == 1:
        lines.append("*did nothing visible this turn*")
    usage = turn.usage
    calls = "1 model call" if usage.calls == 1 else f"{usage.calls} model calls"
    lines.append(f"*{calls} · {number(usage.input)} input tokens "
                 f"({number(usage.cache_read)} cache read, {number(usage.cache_write)} cache write) · "
                 f"{number(usage.output)} output tokens*")
    return "\n\n".join(lines)

def render_village_event(event: Event) -> str:
    data = event.data() or {}
    if event.type == "run_config":
        mode = "Run started" if data.get("mode") == "start" else "Run resumed"
        return f"---\n\n**{mode}** at round {data.get('round')} (step {data.get('step')}), {stamp(event.ts, True)}"
    if event.type == "stopped":
        return f"**[STOPPED]** {event.content}"
    return f"*{event.content}*"

def summary_table(turns: list[Turn], totals: dict[str, Usage], events: list[Event], actors: list[str]) -> str:
    commands, failures = {}, {}
    for event in events:
        if event.type == "command" and event.data():
            commands[event.actor] = commands.get(event.actor, 0) + 1
            failures[event.actor] = failures.get(event.actor, 0) + failed(event.data())
    header = ("| Villager | Turns | Model calls | Input tokens | Output tokens | Cache read | Cache write "
              "| Commands | Failed commands |\n|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    rows = []
    village = Usage()
    turn_total = command_total = failure_total = 0
    for actor in actors:
        usage = totals.get(actor, Usage())
        turn_count = sum(1 for turn in turns if turn.actor == actor)
        rows.append(f"| {actor} | {turn_count} | {usage.calls} | {number(usage.input)} | {number(usage.output)} "
                    f"| {number(usage.cache_read)} | {number(usage.cache_write)} | {commands.get(actor, 0)} "
                    f"| {failures.get(actor, 0)} |")
        village.calls += usage.calls
        village.input += usage.input
        village.output += usage.output
        village.cache_read += usage.cache_read
        village.cache_write += usage.cache_write
        turn_total += turn_count
        command_total += commands.get(actor, 0)
        failure_total += failures.get(actor, 0)
    rows.append(f"| **village** | {turn_total} | {village.calls} | {number(village.input)} | {number(village.output)} "
                f"| {number(village.cache_read)} | {number(village.cache_write)} | {command_total} | {failure_total} |")
    return "\n".join([header, *rows])

def limits_table(configs: list[Event]) -> str:
    header = ("| Session | Started at | Rounds | Max tool rounds | Input budget | Output budget | Compact trigger "
              "| Command timeout | Network |\n|---|---|---:|---:|---:|---:|---:|---:|---|")
    rows = []
    for event in configs:
        data = event.data() or {}
        limits = data.get("limits", {})
        rows.append(f"| {data.get('mode')} | round {data.get('round')} | {limits.get('rounds')} "
                    f"| {limits.get('max_tool_rounds')} | {number(limits.get('input_budget', 0))} "
                    f"| {number(limits.get('output_budget', 0))} | {number(limits.get('compact_trigger', 0))} "
                    f"| {limits.get('command_timeout')} s | {'on' if data.get('network') else 'off'} |")
    return "\n".join([header, *rows])

def completed_rounds(turns: list[Turn], marked: bool, size: int) -> int:
    if not marked:
        return len(turns) // max(size, 1)
    finished = {turn.step for turn in turns if turn.status is not None and turn.step is not None}
    rounds = 0
    while all(step in finished for step in range(rounds * size, (rounds + 1) * size)):
        rounds += 1
    return rounds

def render(run_dir: Path) -> str:
    events, budget, goal = load(run_dir / DB_NAME)
    timeline, turns, marked = build_timeline(events)
    totals = assign_usage(turns, budget)
    configs = [e for e in events if e.type == "run_config"]
    latest = configs[-1].data() if configs else {}
    models = latest.get("models", {}) if latest else {}
    roles = latest.get("roles", {}) if latest else {}
    actors = list(models) or list(dict.fromkeys([t.actor for t in turns] + list(totals)))
    size = len(models) or len(dict.fromkeys(t.actor for t in turns)) or 1
    out = [f"# Village transcript: run {run_dir.name}", f"**Goal:** {goal}"]
    if events:
        out.append(f"**Started:** {stamp(events[0].ts, True)}  \n**Ended:** {stamp(events[-1].ts, True)}  \n"
                   f"**Rounds completed:** {completed_rounds(turns, marked, size)}  \n**Turns:** {len(turns)}")
    if not marked:
        out.append("> This run was recorded before turn and configuration events existed, so rounds are inferred "
                   "from the order of turns and models and limits are not known.")
    out.append("Search for `[FAILED]`, `[TURN ERROR]`, `[REJECTED]` and `[STOPPED]` to find problems.")
    if models:
        out.append("## Villagers\n\n| Villager | Role | Model |\n|---|---|---|\n" + "\n".join(
            f"| {actor} | {roles.get(actor, '')} | `{model}` |" for actor, model in models.items()))
    if configs:
        out.append("## Limits\n\n" + limits_table(configs))
    out.append("## Tokens and commands\n\n" + summary_table(turns, totals, events, actors) +
               "\n\nInput tokens count every prompt token, cached or not; model calls include the calls that "
               "summarize a villager's memory during compaction.")
    out.append("## Timeline")
    current_round = None
    for entry in timeline:
        if isinstance(entry, Event):
            out.append(render_village_event(entry))
            continue
        if entry.round != current_round:
            current_round = entry.round
            out.append(f"## Round {current_round}")
        out.append(render_turn(entry, roles))
    return "\n\n".join(out) + "\n"

def main():
    parser = argparse.ArgumentParser(prog="transcript.py", description="Export a village run as Markdown.")
    parser.add_argument("run", nargs="?", default="",
                        help="run id, run directory or database path; the latest run by default")
    args = parser.parse_args()
    run_dir = find_run(args.run)
    if run_dir is None:
        parser.error(f"no run found for {args.run!r}" if args.run else "there is no run in runs/")
    target = run_dir / "transcript.md"
    target.write_text(render(run_dir), encoding="utf-8")
    print(target)

if __name__ == "__main__":
    main()
