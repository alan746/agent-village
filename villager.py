from typing import Annotated, Literal, TypedDict
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode

from tool import make_tools
from store import Store

MAX_STEPS_PER_TURN = 3

ROLE_PROMPTS = {
    "leader": (
        "Your role: leader. Break the goal into concrete tasks with post_task, "
        "read the results with read_submission, and mark a task done with done_task "
        "once its result is good enough. You may also take tasks yourself."
    ),
    "worker": (
        "Your role: worker. Check the task board with read_task, take a task with take_task, "
        "and submit your result with submit_task. You cannot post tasks; "
        "if you think a task is missing, suggest it in the chat."
    ),
}

class VillageState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    cursor: int
    steps_this_turn: int

def build_villager(name:str, role: str, goal: str, model, path: str, store: Store,
                    input_tokens_limit: int, output_tokens_limit: int,checkpointer):
    tools = make_tools(name, role, path, store, input_tokens_limit, output_tokens_limit)
    model_with_tools = model.bind_tools(tools)
    system = SystemMessage(
        f"You are {name}, one of several AI agents living in a village. "
        f"The village goal: {goal} "
        f"{ROLE_PROMPTS[role]} "
        "Coordinate with the others through post_chat. "
        f"You act in turns, with at most {MAX_STEPS_PER_TURN} tool rounds per turn. "
        f"All agents share one token budget: {input_tokens_limit} input tokens and "
        f"{output_tokens_limit} output tokens in total. Every model call spends from it, "
        "and when either runs out the whole village stops. "
        "The remaining budget is shown at the start of each turn; you can also call check_balance. "
        "When you have nothing useful to do, reply without calling any tool."
    )

    def wake(state: VillageState) -> dict:
        cursor = state.get("cursor", 0)
        new_messages = store.read_chat(cursor)
        other_messages = []
        for new_message in new_messages:
            if new_message.actor != name:
                other_messages.append(new_message)
        lines = ("\n".join(f"{other_message.actor}:{other_message.content}" for other_message in other_messages)) or "(none)"
        store.log(name, "wake", f"{len(other_messages)} new messages")
        balance = store.check_balance(input_tokens_limit, output_tokens_limit)
        budget_line = (f"Shared budget left: {balance['remaining_input_tokens']} input tokens, "
                       f"{balance['remaining_output_tokens']} output tokens.")
        return {"messages": [HumanMessage(f"{budget_line}\nNew chat messages since your last turn:\n{lines}")],
                "cursor" : new_messages[-1].id if new_messages else cursor,
                "steps_this_turn": 0}

    def thinking(state: VillageState) -> dict:
        response = model_with_tools.invoke([system, *state["messages"]])
        usage = response.usage_metadata if response.usage_metadata else {}
        store.spend(name, usage.get("input_tokens", 0), usage.get("output_tokens", 0))
        for call in response.tool_calls:
            store.log(name, "tool_use", f"{call["name"]}: {call["args"]}")
        return {
            "messages": response,
            "steps_this_turn": state["steps_this_turn"] + 1
        }

    act = ToolNode(tools)

    def after_think(state: VillageState) -> Literal["act", "__end__"]:
        return "act" if state["messages"][-1].tool_calls else "__end__"

    def after_act(state:VillageState) -> Literal["thinking", "__end__"]:
        balance = store.check_balance(input_tokens_limit, output_tokens_limit)
        if (state["steps_this_turn"] >= MAX_STEPS_PER_TURN or balance["remaining_input_tokens"] <= 0
            or balance["remaining_output_tokens"] <= 0):
            return "__end__"
        else:
            return "thinking"

    builder = StateGraph(VillageState)
    builder.add_node("wake", wake)
    builder.add_node("thinking", thinking)
    builder.add_node("act", act)
    builder.add_edge(START, "wake")
    builder.add_edge("wake", "thinking")
    builder.add_conditional_edges("thinking", after_think)
    builder.add_conditional_edges("act", after_act)
    return builder.compile(checkpointer = checkpointer)
