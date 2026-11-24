import hashlib
import json
from typing import Annotated, Literal, TypedDict
from langchain_core.utils.function_calling import convert_to_openai_tool
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode
from langchain_core.messages.utils import count_tokens_approximately

from tool import make_tools
from store import Store
from persistence import Limits

COMPACT_KEEP_RATIO = 0.5
THINKING_BLOCKS = ("thinking", "redacted_thinking")

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

def interrupted_tool_results(messages: list[AnyMessage]) -> list[ToolMessage]:
    answered = set()
    for message in reversed(messages):
        if message.type == "tool":
            answered.add(message.tool_call_id)
        elif message.type == "ai":
            return [ToolMessage("This tool call was interrupted when the village stopped, so it may not have run. "
                                "Check its effect before repeating it.", tool_call_id=call["id"], name=call["name"])
                    for call in message.tool_calls if call["id"] not in answered]
        else:
            return []
    return []

def record_usage(store: Store, name: str, response: AnyMessage, event: str):
    usage = response.usage_metadata or {}
    details = usage.get("input_token_details") or {}
    cache_write = sum(details.get(key) or 0 for key in
                      ("cache_creation", "ephemeral_5m_input_tokens", "ephemeral_1h_input_tokens"))
    store.spend(name, usage.get("input_tokens", 0), usage.get("output_tokens", 0), event,
                details.get("cache_read") or 0, cache_write)

def without_thinking(messages: list[AnyMessage]) -> list[AnyMessage]:
    stripped = []
    for message in messages:
        if message.type != "ai" or not isinstance(message.content, list):
            continue
        content = [block for block in message.content
                   if not (isinstance(block, dict) and block.get("type") in THINKING_BLOCKS)]
        if len(content) != len(message.content):
            stripped.append(message.model_copy(update={"content": content}))
    return stripped

def find_compact_boundary(messages: list[AnyMessage], start: int, keep: int) -> int:
    boundary = len(messages) - 1
    tokens = 0
    while boundary > start:
        tokens += count_tokens_approximately([messages[boundary]])
        if tokens >= keep:
            break
        boundary -= 1
    while boundary > start and messages[boundary].type != "human":
        boundary -= 1
    return boundary

class VillageState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    cursor: int
    steps_this_turn: int
    summary: str
    summarized_until: int
    prefix: str

def build_villager(name: str, role: str, goal: str, model, path: str, store: Store, limits: Limits, checkpointer):
    tools = make_tools(name, role, path, store, limits)
    model_with_tools = model.bind_tools(tools)
    system = SystemMessage(
        f"You are {name}, one of several AI agents living in a village. "
        f"The village goal: {goal}\n"
        f"{ROLE_PROMPTS[role]} "
        "Coordinate with the others through post_chat. "
        f"You act in turns, with at most {limits.max_tool_rounds} tool rounds per turn. "
        f"All agents share one token budget: {limits.input_budget} input tokens and "
        f"{limits.output_budget} output tokens in total. Every model call spends from it, "
        "and when either runs out the whole village stops. "
        "The remaining budget is shown at the start of each turn; you can also call check_balance. "
        "When you have nothing useful to do, reply without calling any tool."
    )
    prefix = hashlib.sha256(json.dumps(
        [system.content, [convert_to_openai_tool(t) for t in tools]], sort_keys=True).encode()).hexdigest()

    def wake(state: VillageState) -> dict:
        cursor = state.get("cursor", 0)
        new_messages = store.read_chat(cursor)
        other_messages = []
        for new_message in new_messages:
            if new_message.actor != name:
                other_messages.append(new_message)
        lines = ("\n".join(f"{other_message.actor}:{other_message.content}" for other_message in other_messages)) or "(none)"
        store.log(name, "wake", f"{len(other_messages)} new messages")
        stripped = []
        if state.get("prefix") and state["prefix"] != prefix:
            stripped = without_thinking(state["messages"][state.get("summarized_until", 0):])
            store.log(name, "prefix_changed", f"system prompt or tools changed, removed thinking from {len(stripped)} messages")
        repairs = interrupted_tool_results(state["messages"])
        if repairs:
            store.log(name, "resume_repair", f"answered {len(repairs)} interrupted tool calls")
        balance = store.check_balance(limits.input_budget, limits.output_budget)
        budget_line = (f"Shared budget left: {balance['remaining_input_tokens']} input tokens, "
                       f"{balance['remaining_output_tokens']} output tokens.")
        return {"messages": [*stripped, *repairs, HumanMessage(f"{budget_line}\nNew chat messages since your last turn:\n{lines}")],
                "cursor" : new_messages[-1].id if new_messages else cursor,
                "steps_this_turn": 0,
                "prefix": prefix}
    
    def make_system(summary: str) -> SystemMessage:
        if not summary:
            return system
        return SystemMessage(system.content + f"\nSummary of earlier turns:\n{summary}")
    
    def compact(state: VillageState) -> dict:
        system_with_summary = make_system(state.get("summary"))
        summarized_until = state.get("summarized_until", 0)
        size = count_tokens_approximately([system_with_summary] + state["messages"][summarized_until:], tools=tools)
        if size <= limits.compact_trigger:
            return {}
        fixed = count_tokens_approximately([system], tools=tools)
        keep = int((limits.compact_trigger - fixed) * COMPACT_KEEP_RATIO)
        compact_from = find_compact_boundary(state["messages"], summarized_until, keep)
        if compact_from <= summarized_until:
            return {}
        messages = state["messages"][summarized_until:compact_from]
        lines = messages_to_transcript(messages)

        prompt = SUMMARY_PROMPT.format(name=name, old_summary=state.get("summary") or "(none)", transcript=lines)
        response = model.invoke([HumanMessage(prompt)])
        record_usage(store, name, response, "compact")
        new_summary = str(response.text).strip()
        if not new_summary:
            store.log(name, "compact", "summary was empty, skipped")
            return {}
        store.log(name, "compact", f"summarized messages {summarized_until}-{compact_from - 1}")
        stripped = without_thinking(state["messages"][compact_from:])
        return {"summary": new_summary, "summarized_until": compact_from, "messages": stripped}


    def thinking(state: VillageState) -> dict:
        system_with_summary = make_system(state.get("summary"))
        summarized_until = state.get("summarized_until", 0)
        response = model_with_tools.invoke([system_with_summary, *state["messages"][summarized_until:]])
        record_usage(store, name, response, "thinking")
        if response.text.strip():
            store.log(name, "say", response.text)
        for call in response.tool_calls:
            store.log(name, "tool_use", f"{call['name']}: {call['args']}")
        return {
            "messages": response,
            "steps_this_turn": state["steps_this_turn"] + 1
        }

    act = ToolNode(tools)

    def after_think(state: VillageState) -> Literal["act", "__end__"]:
        return "act" if state["messages"][-1].tool_calls else "__end__"

    def after_act(state: VillageState) -> Literal["compact", "__end__"]:
        balance = store.check_balance(limits.input_budget, limits.output_budget)
        if (state["steps_this_turn"] >= limits.max_tool_rounds or balance["remaining_input_tokens"] <= 0
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
