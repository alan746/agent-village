import sqlite3
import threading
import time
from dataclasses import dataclass

@dataclass
class ChatMessage:
    id:int
    actor:str
    content:str

@dataclass
class Bill:
    id:int
    actor:str
    input_tokens:int
    output_tokens:int

@dataclass
class Event:
    id:int
    actor:str
    type:str
    content:str

class Store():
    def __init__(self, path:str = "village.db"):
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS chat(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT, content TEXT, ts REAL);
                CREATE TABLE IF NOT EXISTS budget(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT, input_tokens INTEGER, output_tokens INTEGER,
                ts REAL, event TEXT DEFAULT 'thinking');
                CREATE TABLE IF NOT EXISTS event(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                actor TEXT, type TEXT, content TEXT, 
                ts REAL);
                CREATE TABLE IF NOT EXISTS run_state(
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    step INTEGER, goal TEXT)
            """)
            self._conn.execute("INSERT OR IGNORE INTO run_state(id, step, goal) VALUES (?, ?, ?)", (1, 0 ,""))
            self._conn.commit()

    def log(self, actor:str, type:str, content:str):
        with self._lock:
            self._conn.execute("""
            INSERT INTO event
            (actor, type, content, ts) VALUES(?,?,?,?)""",
            (actor, type, content, time.time())
            )
            self._conn.commit()

    def post_chat(self, actor: str, content: str):
        with self._lock:
            self._conn.execute("""
            INSERT INTO chat(actor, content, ts) VALUES(?,?,?)""",
            (actor, content, time.time())
            )
            self._conn.commit()
        self.log(actor, "post_chat", content)

    def read_chat(self, cursor: int)-> list[ChatMessage]:
        messages = []
        with self._lock:
            rows = self._conn.execute("""
            SELECT id, actor, content FROM chat WHERE id > ? ORDER BY id""",
            (cursor, )).fetchall()
        for row in rows:
            messages.append(ChatMessage(*row))
        return messages

    def read_bill(self) -> list[Bill]:
        bills = []
        with self._lock:
            rows = (self._conn.execute("""SELECT id, actor, input_tokens, output_tokens FROM budget ORDER BY id""")).fetchall()
        for row in rows:
            bills.append(Bill(*row))
        return bills

    def check_balance(self, input_tokens_limit, output_tokens_limit) -> dict:
            """Return remaining output tokens and remaining input tokens"""
            remaining_output_tokens = output_tokens_limit
            remaining_input_tokens = input_tokens_limit
            bills = self.read_bill()
            for i in range(0, len(bills)):
                remaining_input_tokens -= bills[i].input_tokens
                remaining_output_tokens -= bills[i].output_tokens
            return {"remaining_input_tokens": remaining_input_tokens, "remaining_output_tokens": remaining_output_tokens}

    def spend(self, actor: str,input_tokens: int, output_tokens: int, event:str = "thinking"):
        with self._lock:
            self._conn.execute("INSERT INTO budget(actor, input_tokens, output_tokens, ts, event) VALUES(?,?,?,?,?)",
                               (actor, input_tokens, output_tokens, time.time(), event))
            self._conn.commit()
        self.log(actor, "spend", f"{event}: input_tokens = {input_tokens}, output_tokens = {output_tokens}")

    def read_event(self) -> list[Event]:
        events = []
        with self._lock:
            rows = (self._conn.execute("SELECT id, actor, type, content FROM event ORDER BY id")).fetchall()
        for row in rows:
            events.append(Event(*row))
        return events

    def read_run_state(self) -> dict:
        result = {}
        with self._lock:
            values = self._conn.execute("SELECT step, goal FROM run_state").fetchone()
        result["step"] = values[0]
        result["goal"] = values[1]
        return result

    def update_step(self):
        with self._lock:
            self._conn.execute("UPDATE run_state SET step = step + 1")
            self._conn.commit()

    def set_goal(self, goal: str):
        with self._lock:
            self._conn.execute("UPDATE run_state SET goal = ?", (goal,))
            self._conn.commit()



            
    


