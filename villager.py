from typing import Annotated, Literal, TypedDict
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.messages.utils import count_tokens_approximately

from tool import make_tools
from store import Store

MAX_STEPS_PER_TURN = 3
COMPACT_TRIGGER = 6000
COMPACT_KEEP_RATIO = 0.5

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

SUMMARY_PROMPT = (
    "You are compressing the memory of {name}, an AI agent living in a village with other agents. "
    "Merge the previous summary and the new transcript into one updated summary, written for {name}. "
    "Keep: decisions and why they were made, unfinished work, task and submission IDs, "
    "agreements with other agents, and concrete details such as formats, numbers and names. "
    "Drop small talk and finished work that no longer matters. "
    "Leave out budget numbers; the current budget is shown every turn. "
    "Write under 200 words.\n\n"
    "Previous summary:\n{old_summary}\n\n"
    "New transcript:\n{transcript}"
)

def messages_to_transcript(messages: list[AnyMessage]) -> str:
    lines = []
    for message in messages:
        if message.type == "human":
            lines.append(f"[new turn] {message.text}")
        elif message.type == "ai":
            if message.text:
                lines.append(f"[you said] {message.text}")
            for call in message.tool_calls:
                lines.append(f"[you called] {call['name']}({call['args']})")
        elif message.type == "tool":
            lines.append(f"[{message.name} returned] {message.text}")
    return "\n".join(lines)

class VillageState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    cursor: int
    steps_this_turn: int
    summary: str
    summarized_until: int

def build_villager(name:str, role: str, goal: str, model, path: str, store: Store,
                    input_tokens_limit: int, output_tokens_limit: int,checkpointer):
    tools = make_tools(name, role, path, store, input_tokens_limit, output_tokens_limit)
    model_with_tools = model.bind_tools(tools)
    system = SystemMessage(
        f"You are {name}, one of several AI agents living in a village. "
        f"The village goal: {goal}\n"
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
    
    def make_system(summary: str) -> SystemMessage:
        if not summary:
            return system
        return SystemMessage(system.content + f"\nSummary of earlier turns:\n{summary}")
    
    def compact(state: VillageState) -> dict:
        system_with_summary = make_system(state.get("summary"))
        summarized_until = state.get("summarized_until", 0)
        size = count_tokens_approximately([system_with_summary] + state["messages"][summarized_until:], tools=tools)
        if(size <= COMPACT_TRIGGER): return {}
        fixed = count_tokens_approximately([system], tools=tools)
        keep = int((COMPACT_TRIGGER - fixed) * COMPACT_KEEP_RATIO)
        tokens_current = 0
        for i in range(len(state["messages"]) - 1, summarized_until, -1):
            tokens_current += count_tokens_approximately([state["messages"][i]])
            if tokens_current >= keep:
                break
        compact_from = i
        while state["messages"][compact_from].type != "human" and compact_from > summarized_until:
            compact_from -= 1
        if compact_from <= summarized_until:
            return {}
        messages = state["messages"][summarized_until:compact_from]
        lines = messages_to_transcript(messages)

        prompt = SUMMARY_PROMPT.format(name=name, old_summary=state.get("summary") or "(none)", transcript=lines)
        response = model.invoke([HumanMessage(prompt)])
        usage = response.usage_metadata if response.usage_metadata else {}
        store.spend(name, usage.get("input_tokens", 0), usage.get("output_tokens", 0), event="compact")
        new_summary = str(response.text).strip()
        if not new_summary:
            store.log(name, "compact", "summary was empty, skipped")
            return {}
        store.log(name, "compact", f"summarized messages {summarized_until}-{compact_from - 1}")

        return {"summary": new_summary, "summarized_until": compact_from}


    def thinking(state: VillageState) -> dict:
        system_with_summary = make_system(state.get("summary"))
        summarized_until = state.get("summarized_until", 0)
        response = model_with_tools.invoke([system_with_summary, *state["messages"][summarized_until:]])
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

    def after_act(state: VillageState) -> Literal["compact", "__end__"]:
        balance = store.check_balance(input_tokens_limit, output_tokens_limit)
        if (state["steps_this_turn"] >= MAX_STEPS_PER_TURN or balance["remaining_input_tokens"] <= 0
            or balance["remaining_output_tokens"] <= 0):
            return "__end__"
        else:
            return "compact"

    builder = StateGraph(VillageState)
    builder.add_node("wake", wake)
    builder.add_node("compact", compact)
    builder.add_node("thinking", thinking)
    builder.add_node("act", act)
    builder.add_edge(START, "wake")
    builder.add_edge("wake", "compact")
    builder.add_edge("compact", "thinking")
    builder.add_conditional_edges("thinking", after_think)
    builder.add_conditional_edges("act", after_act)
    return builder.compile(checkpointer = checkpointer)
