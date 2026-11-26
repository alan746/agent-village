import sqlite3

import pytest
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from persistence import LatestCheckpointSaver, Limits
from sandbox import Sandbox
from store import Store
from villager import build_villager


def check_tool_calls_answered(messages):
    for index, message in enumerate(messages):
        if message.type != "ai" or not message.tool_calls:
            continue
        answered = set()
        for later in messages[index + 1:]:
            if later.type != "tool":
                break
            answered.add(later.tool_call_id)
        missing = {call["id"] for call in message.tool_calls} - answered
        if missing:
            raise ValueError(f"400: tool_calls without results: {sorted(missing)}")


class ScriptedModel(BaseChatModel):
    responses: list
    seen: list = []

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.seen.append(list(messages))
        check_tool_calls_answered(messages)
        return ChatResult(generations=[ChatGeneration(message=self.responses.pop(0))])


def make_villager(path, store, model):
    checkpointer = LatestCheckpointSaver(sqlite3.connect(path, check_same_thread=False))
    return build_villager("alice", "worker", "test goal", model, path, store, Limits(), checkpointer,
                          Sandbox("offline-test", "."))


def test_resume_after_crash_between_thinking_and_act(tmp_path, monkeypatch):
    path = str(tmp_path / "village.db")
    store = Store(path)
    config = {"configurable": {"thread_id": "alice"}}

    def crash(actor, content):
        raise KeyboardInterrupt

    monkeypatch.setattr(store, "post_chat", crash)
    first = ScriptedModel(responses=[AIMessage("", tool_calls=[
        {"name": "post_chat", "args": {"content": "hi"}, "id": "call_1", "type": "tool_call"}])])
    with pytest.raises(KeyboardInterrupt):
        make_villager(path, store, first).invoke({"messages": []}, config)
    monkeypatch.undo()
    conn = sqlite3.connect(path)
    assert conn.execute("SELECT COUNT(*) FROM checkpoints WHERE thread_id = 'alice'").fetchone()[0] == 1
    conn.close()

    resumed_store = Store(path)
    second = ScriptedModel(responses=[AIMessage("Nothing to do.")])
    villager = make_villager(path, resumed_store, second)
    assert villager.get_state(config).values["messages"][-1].tool_calls
    villager.invoke({"messages": []}, config)

    sent = second.seen[-1]
    check_tool_calls_answered(sent)
    assert sent[-1].type == "human"
    repaired = [m for m in sent if m.type == "tool" and m.tool_call_id == "call_1"]
    assert len(repaired) == 1
    assert "interrupted" in repaired[0].text
