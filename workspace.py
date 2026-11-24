import threading
import sqlite3
from dataclasses import dataclass

@dataclass
class Task:
    id: int
    creator: str
    description: str
    max_workers: int
    done: bool
    workers: list[str]

    @property
    def status(self) -> str:
        if self.done:
            return "done"
        if not self.workers:
            return "open"
        if len(self.workers) < self.max_workers:
            return "in progress, can take more workers"
        return "in progress, full"

@dataclass
class Submission:
    id: int
    task_id: int
    worker: str
    result: str
    version: int

class Workspace():
    def __init__(self, path:str = "village.db"):
        self._conn = sqlite3.connect(path, check_same_thread = False)
        self._lock = threading.RLock()
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS workspace(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                creator TEXT, description TEXT, max_workers INTEGER DEFAULT 2,
                status TEXT CHECK (status IN ('assigned', 'done', 'not_assigned')));
                CREATE TABLE IF NOT EXISTS submission(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER, worker TEXT, result TEXT, version INTEGER DEFAULT 1,
                UNIQUE (task_id, worker));
                CREATE TABLE IF NOT EXISTS task_worker(
                task_id INTEGER, worker TEXT,
                PRIMARY KEY (task_id, worker))
                """
            )
            self._conn.commit()

    def post_task(self, creator: str, description: str, max_workers: int) -> str:
        if max_workers < 1:
            return "max_workers must be at least 1."
        with self._lock:
            cur = self._conn.execute("""
            INSERT INTO workspace
            (creator, description, max_workers, status) VALUES (?,?,?,?)""",
            (creator, description, max_workers, "not_assigned"))
            task_id = cur.lastrowid
            self._conn.commit()
        return f"You posted task {task_id}."

    def workers_of(self, task_id: int) -> list[str]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT worker FROM task_worker WHERE task_id = ? ORDER BY rowid", (task_id,)).fetchall()
        return [row[0] for row in rows]

    def read_task(self) -> list[Task]:
        with self._lock:
            rows = self._conn.execute("""
            SELECT id, creator, description, max_workers, status FROM workspace ORDER BY id""").fetchall()
            return [Task(id, creator, description, max_workers, status == "done", self.workers_of(id))
                    for id, creator, description, max_workers, status in rows]

    def check_belong(self, worker: str, task_id: int) -> bool:
        return worker in self.workers_of(task_id)

    def take_task(self, worker: str, task_id: int) -> str|int:
        with self._lock:
            row = self._conn.execute("""
            SELECT max_workers, status FROM workspace WHERE id = ?""", (task_id,)).fetchone()
            if row is None:
                return f"Task {task_id} does not exist."
            max_workers, status = row
            workers = self.workers_of(task_id)
            if status == "done":
                return f"Task {task_id} is already done."
            if worker in workers:
                return f"You have already taken task {task_id}."
            if len(workers) >= max_workers:
                return f"Task {task_id} already has the maximum of {max_workers} workers: {', '.join(workers)}."
            self._conn.execute("""
            INSERT INTO task_worker (task_id, worker) VALUES(?, ?)""", (task_id, worker))
            if len(workers) + 1 >= max_workers:
                self._conn.execute("""
                UPDATE workspace SET status = ? WHERE id = ?""", ("assigned", task_id))
            self._conn.commit()
        return task_id

    def submit_task(self, worker: str, task_id: int, result: str) -> str:
        with self._lock:
            row = self._conn.execute("SELECT status FROM workspace WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                return f"Task {task_id} does not exist."
            if row[0] == "done":
                return f"Task {task_id} is already done and no longer accepts submissions."
            if not self.check_belong(worker, task_id):
                return f"You have not taken task {task_id}; take it before submitting."
            self._conn.execute("""
            INSERT INTO submission(task_id, worker, result) VALUES(?, ?, ?)
            ON CONFLICT(task_id, worker) DO UPDATE SET result = excluded.result, version = version + 1""",
            (task_id, worker, result))
            version = self._conn.execute(
                "SELECT version FROM submission WHERE task_id = ? AND worker = ?", (task_id, worker)).fetchone()[0]
            self._conn.commit()
        if version == 1:
            return f"Your result for task {task_id} was submitted."
        return f"Your result for task {task_id} was updated to version {version}; it replaces your previous submission."

    def read_submission(self, task_id: int | None = None, worker: str | None = None) -> list[Submission]:
        query = "SELECT id, task_id, worker, result, version FROM submission WHERE 1 = 1"
        params = []
        if task_id is not None:
            query += " AND task_id = ?"
            params.append(task_id)
        if worker is not None:
            query += " AND worker = ?"
            params.append(worker)
        with self._lock:
            rows = self._conn.execute(query + " ORDER BY id", params).fetchall()
        return [Submission(*row) for row in rows]

    def done_task(self, task_id: int) -> str:
        with self._lock:
            row = self._conn.execute("SELECT status FROM workspace WHERE id = ?", (task_id,)).fetchone()
            if row is None:
                return f"Task {task_id} does not exist."
            if row[0] == "done":
                return f"Task {task_id} is already done."
            if not self.read_submission(task_id):
                return (f"Task {task_id} has no submissions yet, so it was not marked done. "
                        "Wait for a worker to submit, or take it and submit a note yourself.")
            self._conn.execute("UPDATE workspace SET status = ? WHERE id = ?", ("done", task_id))
            self._conn.commit()
        return f"Task {task_id} is marked done."
