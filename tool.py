import json
from typing import Annotated
from langchain_core.tools import tool
from workspace import Workspace
from store import Store
from persistence import Limits
from sandbox import Sandbox, CommandResult, PathError, WORKDIR

def command_report(result: CommandResult, timeout: int) -> str:
    if result.timed_out:
        status = f"timed out after {timeout} seconds and was killed (exit code {result.exit_code})"
    else:
        status = f"exit code: {result.exit_code}"
    return f"{status}\nstdout:\n{result.stdout or '(empty)'}\nstderr:\n{result.stderr or '(empty)'}"

def make_tools(actor: str, role: str, path: str, store: Store, limits: Limits, sandbox: Sandbox):
    workspace = Workspace(path)

    def log_event(kind: str, **fields):
        store.log(actor, kind, json.dumps(fields, ensure_ascii=False))

    @tool
    def run_command(command: Annotated[str, "A bash command or script to run in your container"],
                    timeout_seconds: Annotated[int, f"Seconds before the command is killed, at most {limits.command_timeout}"] = limits.command_timeout) -> str:
        """Run a bash command in your own Linux container. The working directory is /repo, which is shared with every other agent. Returns the exit code, stdout and stderr; long output is cut in the middle. The command gets no stdin and is killed when it runs out of time, so do not start servers or interactive programs in the foreground."""
        timeout = max(1, min(int(timeout_seconds), limits.command_timeout))
        result = sandbox.run(actor, command, timeout)
        log_event("command", command=command, exit_code=result.exit_code, timed_out=result.timed_out,
                  duration=round(result.duration, 2), stdout=result.stdout, stderr=result.stderr)
        return command_report(result, timeout)

    @tool
    def write_file(path: Annotated[str, f"File path inside {WORKDIR}, absolute or relative to it"],
                   content: Annotated[str, "The complete new content of the file"]) -> str:
        """Create or overwrite a text file in /repo, creating missing directories. Use this instead of shell redirection or heredocs to write files."""
        try:
            result = sandbox.write_file(actor, path, content)
        except PathError as error:
            log_event("write_file", path=path, error=str(error))
            return f"Rejected: {error}."
        size = len(content.encode("utf-8"))
        log_event("write_file", path=path, bytes=size, exit_code=result.exit_code, stderr=result.stderr)
        if result.exit_code != 0:
            return f"Could not write {path} (exit code {result.exit_code}): {result.stderr}"
        return f"Wrote {size} bytes to {path}."

    @tool
    def read_file(path: Annotated[str, f"File path inside {WORKDIR}, absolute or relative to it"]) -> str:
        """Read a text file from /repo. Very long files are cut off; use run_command with sed or grep to look at parts of them."""
        try:
            result = sandbox.read_file(actor, path)
        except PathError as error:
            log_event("read_file", path=path, error=str(error))
            return f"Rejected: {error}."
        log_event("read_file", path=path, exit_code=result.exit_code, stderr=result.stderr)
        if result.exit_code != 0:
            return f"Could not read {path} (exit code {result.exit_code}): {result.stderr}"
        return result.stdout or "(the file is empty)"
    @tool
    def post_chat(content: Annotated[str, "The message to send to the shared village chat"]) -> str:
        """Post a message to the shared village chat. Every other agent sees it at the start of their next turn."""
        store.post_chat(actor, content)
        return "Message posted to the chat."

    @tool
    def check_balance() -> str:
        """Return remaining output tokens and remaining input tokens"""
        balance = store.check_balance(limits.input_budget, limits.output_budget)
        return (f"remaining output tokens are {balance['remaining_output_tokens']}, "
                f"remaining input tokens are {balance['remaining_input_tokens']}")
    
    @tool
    def read_task() -> str:
        """Return all tasks in the board"""
        results = workspace.read_task()
        if not results:
            return "There are no tasks on the board."
        lines = [f"task {t.id}: {t.description} (posted by {t.creator}, status: {t.status}, "
                 f"workers {len(t.workers)}/{t.max_workers}: {', '.join(t.workers) or 'none'})" for t in results]
        return "\n".join(lines)

    @tool
    def post_task(description: Annotated[str, "What needs to be done, clear enough for another agent to work on it"],
                  max_workers: Annotated[int, "How many agents can take this task at the same time"] = 2) -> str:
        """Post a new task on the task board so other agents can take it."""
        message = workspace.post_task(actor, description, max_workers)
        log_event("post_task", description=description, max_workers=max_workers, outcome=message)
        return message

    @tool
    def take_task(task_id: Annotated[int, "The id of the task you want to work on"]) -> str:
        """Take a task from the task board. You must take a task before you can submit a result for it."""
        outcome = workspace.take_task(actor, task_id)
        message = f"You took task {task_id}." if isinstance(outcome, int) else outcome
        log_event("take_task", task_id=task_id, outcome=message)
        return message

    @tool
    def submit_task(task_id: Annotated[int, "The id of the task you are submitting a result for"],
                    result: Annotated[str, "Your result for this task"]) -> str:
        """Submit your result for a task you have taken. Other agents can read it afterwards. Submitting again replaces your earlier result for that task."""
        message = workspace.submit_task(actor, task_id, result)
        log_event("submit_task", task_id=task_id, result=result, outcome=message)
        return message

    @tool
    def read_submission(task_id: Annotated[int | None, "Only show results for this task; leave empty for all tasks"] = None,
                        worker: Annotated[str | None, "Only show results from this agent; leave empty for everyone"] = None) -> str:
        """Read results that agents have submitted for tasks."""
        results = workspace.read_submission(task_id, worker)
        if not results:
            return "No matching submissions."
        lines = [f"submission {s.id} for task {s.task_id} by {s.worker} (version {s.version}):\n{s.result}" for s in results]
        return "\n\n".join(lines)

    @tool
    def done_task(task_id: Annotated[int, "The id of the task to mark as done"]) -> str:
        """Mark a task as done after checking its submitted results. A task needs at least one submission to be marked done. A done task cannot be taken or submitted to anymore."""
        message = workspace.done_task(task_id)
        log_event("done_task", task_id=task_id, outcome=message)
        return message

    common_tools = [run_command, write_file, read_file, post_chat, check_balance,
                    read_task, take_task, submit_task, read_submission]
    leader_tools = [post_task, done_task]
    if role == "leader":
        return common_tools + leader_tools
    else:
        return common_tools

