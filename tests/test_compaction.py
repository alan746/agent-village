import json
import sqlite3

from langchain_core.messages import AIMessage
from langgraph.checkpoint.sqlite import SqliteSaver

import villager
from persistence import Limits
from store import Store
from test_resume import ScriptedModel


def thinking_signatures(message):
    if message.type != "ai" or not isinstance(message.content, list):
        return []
    return [block["signature"] for block in message.content
            if isinstance(block, dict) and block.get("type") == "thinking"]


def fingerprint(messages):
    return [(m.type, json.dumps(m.content, sort_keys=True, default=str),
             json.dumps(getattr(m, "tool_calls", []), sort_keys=True, default=str)) for m in messages]


class BindingCheckModel(ScriptedModel):
    bindings: dict = {}
    thinking_replayed: int = 0

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        for index, message in enumerate(messages):
            for signature in thinking_signatures(message):
                if self.bindings[signature] != fingerprint(messages[:index]):
                    raise ValueError("400: Invalid signature in thinking block, bound to a different conversation")
                self.thinking_replayed += 1
        result = super()._generate(messages, stop, run_manager, **kwargs)
        for signature in thinking_signatures(result.generations[0].message):
            self.bindings[signature] = fingerprint(messages)
        return result


def test_compaction_keeps_every_replayed_thinking_block_valid(tmp_path):
    path = str(tmp_path / "village.db")
    store = Store(path)
    responses = [AIMessage([{"type": "thinking", "thinking": "", "signature": f"sig{n}"},
                            {"type": "text", "text": f"reply {n} " + "words " * 300}]) for n in range(16)]
    model = BindingCheckModel(responses=responses)
    graph = villager.build_villager("alice", "worker", "test goal", model, path, store, Limits(compact_trigger=2500),
                                    SqliteSaver(sqlite3.connect(path, check_same_thread=False)))
    config = {"configurable": {"thread_id": "alice"}}
    for turn in range(6):
        graph.invoke({"messages": []}, config)

    summary_calls = [call for call in model.seen if call[0].type == "human"]
    assert len(summary_calls) >= 2
    assert model.thinking_replayed > 0
    assert graph.get_state(config).values["summarized_until"] > 0


def test_changed_system_prompt_on_resume_drops_old_thinking(tmp_path):
    path = str(tmp_path / "village.db")
    store = Store(path)
    responses = [AIMessage([{"type": "thinking", "thinking": "", "signature": f"sig{n}"},
                            {"type": "text", "text": f"reply {n}"}]) for n in range(4)]
    model = BindingCheckModel(responses=responses)
    config = {"configurable": {"thread_id": "alice"}}
    for goal in ["first goal", "first goal", "second goal", "second goal"]:
        graph = villager.build_villager("alice", "worker", goal, model, path, store, Limits(),
                                        SqliteSaver(sqlite3.connect(path, check_same_thread=False)))
        graph.invoke({"messages": []}, config)
    assert model.thinking_replayed == 2
