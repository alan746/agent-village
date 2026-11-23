from store import Store
import threading
import sqlite3
from dataclasses import dataclass

@dataclass 
class Task:
    id: int
    creator: str
    description: str
    max_workers: int
    status: str

@dataclass
class Submission:
    id: int
    task_id: int
    worker: str
    result: str

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
                task_id INTEGER, worker TEXT, result TEXT);
                CREATE TABLE IF NOT EXISTS task_worker(
                task_id INTEGER, worker TEXT,
                PRIMARY KEY (task_id, worker))
                """
            )
            self._conn.commit()

    def post_task(self, creator: str, description: str, max_workers: int) -> str:
        with self._lock:
            cur = self._conn.execute("""
            INSERT OR IGNORE INTO workspace
            (creator, description, max_workers, status) VALUES (?,?,?,?)""", 
            (creator, description, max_workers, "not_assigned"))
            task_id = cur.lastrowid
            self._conn.commit()
        return f"You successfully post task where id is {task_id}"

    def read_task(self) -> list[Task]:
        tasks = []
        with self._lock:
            rows = self._conn.execute("""
            SELECT id, creator, description, max_workers, status FROM workspace""").fetchall()
            self._conn.commit()
        for row in rows:
            tasks.append(Task(*row))
        return tasks

    def check_belong(self, worker: str, task_id: int):
        with self._lock:
            rows = self._conn.execute("""
            SELECT worker FROM task_worker WHERE task_id = ?""", (task_id,)).fetchall()
            for row in rows:
                if row[0] == worker:
                    return True
            self._conn.commit()
        return False


    def take_task(self, worker: str, task_id: int) -> str|int:
        with self._lock:
            row = self._conn.execute("""
            SELECT max_workers, status FROM workspace WHERE id = ?""", (task_id,)).fetchone()
            if row == None:
                return "This task_id does not exist"
            max_workers, status = row
            rows = self._conn.execute("""
            SELECT worker FROM task_worker WHERE task_id = ?""", (task_id,)).fetchall()
            if status == "done":
                return "This task has done"
            if self.check_belong(worker, task_id):
                return f"You have been taken this task already" 
            elif len(rows) >= max_workers:
                return f"The number of workers for this task reaches the limit"
            else:
                self._conn.execute("""
                INSERT OR IGNORE INTO task_worker (task_id, worker) VALUES(?, ?)""", (task_id, worker))
                if(len(rows) + 1) == max_workers:
                    self._conn.execute("""
                    UPDATE workspace SET status = ? WHERE id = ?""", ("assigned", task_id))
            self._conn.commit()
        return task_id
        
    def summbit_task(self, worker: str, task_id: int, result: str) -> str:
        if not (self.check_belong(worker, task_id)):
            return f"You do not have premission to sumbit the task for this task_id"
        else:
            self._conn.execute("""
            INSERT OR IGNORE INTO submission(worker, task_id, result) VALUES(?, ?, ?)""", (worker, task_id, result))
            self._conn.commit()
            return "Your result has successfully submitted"
        
    def read_submission(self, task_id: int = None, worker: str = None) -> list[Submission]:
        submissions = []
        if task_id == None and worker == None: 
            with self._lock:
                rows = self._conn.execute("""SELECT id, task_id, worker, result FROM submission""")
                self._conn.commit()
            for row in rows:
                submissions.append(Submission(*row))
        elif worker == None and task_id != None:
            with self._lock:
                rows = self._conn.execute("""SELECT id, task_id, worker, result FROM submission WHERE task_id = ?""", (task_id, ))
                self._conn.commit()
            for row in rows:
                submissions.append(Submission(*row))
        elif worker != None and task_id == None:
            with self._lock:
                rows = self._conn.execute("""SELECT id, task_id, worker, result FROM submission WHERE worker = ?""", (worker, ))
                self._conn.commit()
            for row in rows:
                submissions.append(Submission(*row))
        else:
            with self._lock:
                rows = self._conn.execute("""SELECT id, task_id, worker, result FROM submission WHERE task_id = ? AND worker = ?""", (task_id, worker))
                self._conn.commit()
            for row in rows:
                submissions.append(Submission(*row))
        return submissions
    
    def check_task_exist(self, id: int) -> bool:
        with self._lock:
            task_ids = self._conn.execute("SELECT id FROM workspace WHERE id = ?", (id,)).fetchall()
            self._conn.commit()
        if len(task_ids) == 0:
            return False
        return True

    def done_task(self, id: int) -> str:
        if not (self.check_task_exist(id)):
            return f"No such task exists"
        with self._lock:
            self._conn.execute("UPDATE workspace SET status = ? WHERE id = ?", ("done", id))
            self._conn.commit()
        return f"Set status to done for this task"
