import hashlib
import posixpath
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path

ENV_DIR = Path(__file__).resolve().parent / "env"
IMAGE_NAME = "agent-village-env"
WORKDIR = "/repo"
MEMORY = "1g"
CPUS = "2"
PIDS = "256"
OUTPUT_LIMIT = 4000
READ_LIMIT = 20000
KILL_GRACE = 5
CLIENT_GRACE = 30
FILE_TIMEOUT = 30

class SandboxError(RuntimeError):
    pass

class PathError(ValueError):
    pass

@dataclass
class CommandResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool
    duration: float

class Capture:
    def __init__(self, head_limit: int, tail_limit: int):
        self.head_limit = head_limit
        self.tail_limit = tail_limit
        self.head = bytearray()
        self.tail = bytearray()
        self.total = 0

    def feed(self, chunk: bytes):
        self.total += len(chunk)
        room = self.head_limit - len(self.head)
        if room > 0:
            self.head += chunk[:room]
            chunk = chunk[room:]
        if chunk and self.tail_limit:
            self.tail += chunk
            del self.tail[:-self.tail_limit]

    def text(self) -> str:
        head = self.head.decode("utf-8", "replace")
        tail = self.tail.decode("utf-8", "replace")
        hidden = self.total - len(self.head) - len(self.tail)
        if hidden <= 0:
            return head + tail
        return f"{head}\n[... {hidden} bytes truncated ...]\n{tail}"

def clipped(limit: int) -> Capture:
    return Capture(limit // 2, limit - limit // 2)

def repo_path(path: str) -> str:
    if not path or "\0" in path:
        raise PathError("the path is empty or invalid")
    resolved = posixpath.normpath(posixpath.join(WORKDIR, path.replace("\\", "/")))
    if resolved == WORKDIR or not resolved.startswith(WORKDIR + "/"):
        raise PathError(f"{path} is not a file path inside {WORKDIR}")
    return resolved

def docker(*args: str, check: bool = True, timeout: float = 120) -> subprocess.CompletedProcess:
    result = subprocess.run(["docker", *args], capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)
    if check and result.returncode != 0:
        message = result.stderr.decode("utf-8", "replace").strip()
        raise SandboxError(f"docker {args[0]} failed: {message}")
    return result

def docker_available() -> bool:
    try:
        return docker("info", "--format", "{{.ServerVersion}}", check=False, timeout=30).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False

def image_tag() -> str:
    digest = hashlib.sha256((ENV_DIR / "Dockerfile").read_bytes()).hexdigest()[:12]
    return f"{IMAGE_NAME}:{digest}"

def ensure_image() -> str:
    tag = image_tag()
    if docker("image", "inspect", tag, check=False).returncode != 0:
        print(f"Building {tag} ...", file=sys.stderr)
        subprocess.run(["docker", "build", "-t", tag, str(ENV_DIR)], check=True, stdout=sys.stderr)
    return tag

def pump(stream, capture: Capture):
    for chunk in iter(lambda: stream.read(65536), b""):
        capture.feed(chunk)
    stream.close()

def feed_stdin(stream, data: bytes):
    try:
        stream.write(data)
    except OSError:
        pass
    finally:
        try:
            stream.close()
        except OSError:
            pass

def run_docker(args: list[str], data: bytes, timeout: float, out: Capture, err: Capture) -> int | None:
    process = subprocess.Popen(["docker", *args], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    threads = [threading.Thread(target=pump, args=(process.stdout, out), daemon=True),
               threading.Thread(target=pump, args=(process.stderr, err), daemon=True),
               threading.Thread(target=feed_stdin, args=(process.stdin, data), daemon=True)]
    for thread in threads:
        thread.start()
    try:
        code = process.wait(timeout)
    except subprocess.TimeoutExpired:
        code = None
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
    for thread in threads:
        thread.join(5)
    return code

class Sandbox:
    def __init__(self, run_id: str, repo_dir: Path, network: bool = True):
        self.run_id = run_id
        self.repo_dir = Path(repo_dir).resolve()
        self.network = network
        self.image = None

    def container(self, actor: str) -> str:
        return f"village-{self.run_id}-{actor}"

    def start(self, actors: list[str]):
        self.image = ensure_image()
        self.close()
        for actor in actors:
            docker("run", "-d", "--name", self.container(actor), "--hostname", actor,
                   "--label", f"village.run={self.run_id}", "--label", f"village.actor={actor}",
                   "--init", "--memory", MEMORY, "--memory-swap", MEMORY, "--cpus", CPUS,
                   "--pids-limit", PIDS, "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
                   "--network", "bridge" if self.network else "none",
                   "--mount", f"type=bind,source={self.repo_dir},target={WORKDIR}", "--workdir", WORKDIR,
                   "--env", f"GIT_AUTHOR_NAME={actor}", "--env", f"GIT_AUTHOR_EMAIL={actor}@village.local",
                   "--env", f"GIT_COMMITTER_NAME={actor}", "--env", f"GIT_COMMITTER_EMAIL={actor}@village.local",
                   self.image)

    def close(self) -> int:
        ids = docker("ps", "-aq", "--filter", f"label=village.run={self.run_id}", check=False).stdout.split()
        if ids:
            docker("rm", "-f", *[container_id.decode() for container_id in ids], check=False)
        return len(ids)

    def run(self, actor: str, command: str, timeout: int) -> CommandResult:
        out, err = clipped(OUTPUT_LIMIT), clipped(OUTPUT_LIMIT)
        started = time.monotonic()
        code = run_docker(["exec", "-i", "--workdir", WORKDIR, self.container(actor), "sh", "-c",
                           f'exec timeout --kill-after={KILL_GRACE} {int(timeout)} bash -c "$(cat)" < /dev/null'],
                          command.encode("utf-8"), timeout + KILL_GRACE + CLIENT_GRACE, out, err)
        duration = time.monotonic() - started
        if code is None:
            docker("restart", "--time", "0", self.container(actor), check=False)
        timed_out = code is None or (code in (124, 137) and duration >= timeout)
        return CommandResult(code, out.text(), err.text(), timed_out, duration)

    def write_file(self, actor: str, path: str, content: str) -> CommandResult:
        target = repo_path(path)
        out, err = clipped(OUTPUT_LIMIT), clipped(OUTPUT_LIMIT)
        started = time.monotonic()
        code = run_docker(["exec", "-i", self.container(actor), "sh", "-c",
                           'mkdir -p -- "$(dirname -- "$1")" && cat > "$1"', "sh", target],
                          content.encode("utf-8"), FILE_TIMEOUT, out, err)
        return CommandResult(code, out.text(), err.text(), code is None, time.monotonic() - started)

    def read_file(self, actor: str, path: str) -> CommandResult:
        target = repo_path(path)
        out, err = Capture(READ_LIMIT, 0), clipped(OUTPUT_LIMIT)
        started = time.monotonic()
        code = run_docker(["exec", "-i", self.container(actor), "cat", "--", target],
                          b"", FILE_TIMEOUT, out, err)
        return CommandResult(code, out.text(), err.text(), code is None, time.monotonic() - started)
