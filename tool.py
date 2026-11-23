from typing import Annotated
from langchain_core.tools import tool
from workspace import Workspace, Task, Submission

from dataclasses import asdict

from store import Store

def make_tools(actor: str, role: str, path: str, store: Store, input_tokens_limit: int, output_tokens_limit: int):
    workspace = Workspace(path)
    @tool
    def post_chat(content: Annotated[str, "The content we want to send to the chat"]):
        """Post new messages into chat"""
        store.post_chat(actor, content)

    @tool
    def check_balance() -> str:
        """Return remaining output tokens and remaining input tokens"""
        balance = store.check_balance(input_tokens_limit, output_tokens_limit)
        return f"remaining output tokens are {balance["remaining_output_tokens"]}, remaining input tokens are {balance["remaining_input_tokens"]}"
    
    @tool
    def read_task() -> str:
        """Return all tasks in the board"""
        results = workspace.read_task()
        if not results:
            return "There are no tasks on the board."
        lines = [f"task {t.id}: {t.description} (posted by {t.creator}, "
                f"max {t.max_workers} workers, status: {t.status})" for t in results]
        return "\n".join(lines)

    @tool
    def post_task(description: Annotated[str, "What needs to be done, clear enough for another agent to work on it"],
                  max_workers: Annotated[int, "How many agents can take this task at the same time"] = 2) -> str:
        """Post a new task on the task board so other agents can take it."""
        message = workspace.post_task(actor, description, max_workers)
        store.log(actor, "post_task", f"{description} (max_workers={max_workers}) -> {message}")
        return message

    @tool
    def take_task(task_id: Annotated[int, "The id of the task you want to work on"]) -> str:
        """Take a task from the task board. You must take a task before you can submit a result for it."""
        outcome = workspace.take_task(actor, task_id)
        message = f"You took task {task_id}." if isinstance(outcome, int) else outcome
        store.log(actor, "take_task", f"task {task_id} -> {message}")
        return message

    @tool
    def submit_task(task_id: Annotated[int, "The id of the task you are submitting a result for"],
                    result: Annotated[str, "Your result for this task"]) -> str:
        """Submit your result for a task you have taken. Other agents can read it afterwards."""
        message = workspace.summbit_task(actor, task_id, result)
        store.log(actor, "submit_task", f"task {task_id} -> {message}")
        return message

    @tool
    def read_submission(task_id: Annotated[int | None, "Only show results for this task; leave empty for all tasks"] = None,
                        worker: Annotated[str | None, "Only show results from this agent; leave empty for everyone"] = None) -> str:
        """Read results that agents have submitted for tasks."""
        results = workspace.read_submission(task_id, worker)
        if not results:
            return "No matching submissions."
        lines = [f"submission {s.id} for task {s.task_id} by {s.worker}:\n{s.result}" for s in results]
        return "\n\n".join(lines)

    @tool
    def done_task(task_id: Annotated[int, "The id of the task to mark as done"]) -> str:
        """Mark a task as done after checking its submitted results. A done task cannot be taken anymore."""
        message = workspace.done_task(task_id)
        store.log(actor, "done_task", f"task {task_id} -> {message}")
        return message

    common_tools = [post_chat, check_balance, read_task, take_task, submit_task, read_submission]
    leader_tools = [post_task, done_task]
    if role == "leader":
        return common_tools + leader_tools
    else:
        return common_tools

