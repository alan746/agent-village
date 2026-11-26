import sqlite3

from langchain_core.messages import AIMessage
from langgraph.checkpoint.base import empty_checkpoint

from persistence import LatestCheckpointSaver, Limits
from sandbox import Sandbox
from store import Store
from test_resume import ScriptedModel
from villager import build_villager


def chat_call(call_id):
    return AIMessage("", tool_calls=[{"name": "post_chat", "args": {"content": f"hi {call_id}"},
                                      "id": call_id, "type": "tool_call"}])


def rows(path, query):
    conn = sqlite3.connect(path)
    try:
        return conn.execute(query).fetchall()
    finally:
        conn.close()


def make_villager(name, path, store, model, checkpointer):
    return build_villager(name, "worker", "test goal", model, path, store, Limits(), checkpointer,
                          Sandbox("offline-test", "."))


def test_villager_keeps_only_latest_checkpoint(tmp_path):
    path = str(tmp_path / "village.db")
    store = Store(path)
    model = ScriptedModel(responses=[chat_call("call_1"), AIMessage("done"), AIMessage("nothing new"),
                                     chat_call("call_2"), AIMessage("done again")])
    villager = make_villager("alice", path, store, model,
                             LatestCheckpointSaver(sqlite3.connect(path, check_same_thread=False)))
    config = {"configurable": {"thread_id": "alice"}}
    for turn in range(3):
        villager.invoke({"messages": []}, config)

    checkpoints = rows(path, "SELECT thread_id, checkpoint_ns, checkpoint_id FROM checkpoints")
    assert len(checkpoints) == 1 and checkpoints[0][:2] == ("alice", "")
    assert rows(path, "SELECT checkpoint_id FROM writes WHERE checkpoint_id < "
                      f"'{checkpoints[0][2]}'") == []
    messages = villager.get_state(config).values["messages"]
    assert [m.type for m in messages] == ["human", "ai", "tool", "ai", "human", "ai", "human", "ai", "tool", "ai"]
    assert len([c for c in store.read_chat(0) if c.actor == "alice"]) == 2


def test_threads_sharing_saver_keep_their_own_checkpoint(tmp_path):
    path = str(tmp_path / "village.db")
    store = Store(path)
    checkpointer = LatestCheckpointSaver(sqlite3.connect(path, check_same_thread=False))
    villagers = {name: make_villager(name, path, store, ScriptedModel(responses=[
        chat_call(f"{name}_1"), AIMessage("done"), AIMessage("still here")]), checkpointer)
        for name in ("alice", "bob")}
    for turn in range(2):
        for name, villager in villagers.items():
            villager.invoke({"messages": []}, {"configurable": {"thread_id": name}})

    counts = rows(path, "SELECT thread_id, COUNT(*) FROM checkpoints GROUP BY thread_id ORDER BY thread_id")
    assert counts == [("alice", 1), ("bob", 1)]
    for name, villager in villagers.items():
        messages = villager.get_state({"configurable": {"thread_id": name}}).values["messages"]
        assert [m.type for m in messages] == ["human", "ai", "tool", "ai", "human", "ai"]


def test_late_writes_for_older_checkpoint_are_removed_by_next_put(tmp_path):
    path = str(tmp_path / "village.db")
    saver = LatestCheckpointSaver(sqlite3.connect(path, check_same_thread=False))
    base = {"configurable": {"thread_id": "alice", "checkpoint_ns": ""}}
    first = saver.put(base, empty_checkpoint(), {}, {})
    second = saver.put(first, empty_checkpoint(), {}, {})
    saver.put_writes(first, [("messages", "late")], "task_1")
    saver.put_writes(second, [("messages", "pending")], "task_2")
    assert len(rows(path, "SELECT * FROM writes")) == 2

    third = saver.put(second, empty_checkpoint(), {}, {})
    assert rows(path, "SELECT checkpoint_id FROM checkpoints") == [(third["configurable"]["checkpoint_id"],)]
    assert rows(path, "SELECT * FROM writes") == []
    assert saver.get_tuple(base).config == third
