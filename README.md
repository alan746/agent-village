# agent-village

A small "village" of LLM agents from different providers that work on one goal together, loosely modelled on [AI Village](https://theaidigest.org/village). Each agent takes turns, has its own Docker container, and shares one `/repo` directory, one chat, one task board and one token budget with the others. Everything is stored in SQLite, so a run can be stopped and resumed, and exported afterwards as a readable transcript.

| Villager | Role | Model | Provider |
|---|---|---|---|
| claude | leader | `claude-sonnet-5-5` | Anthropic |
| chatgpt | worker | `gpt-6-luna` | OpenAI |
| deepseek | worker | `deepseek-flash` | DeepSeek |
| gemini | worker | `google/gemini-3.8-flash` | OpenRouter |

Model ids are set in `MODEL_IDS` in `models.py`.

## How it works

```mermaid
flowchart TB
    loop["village.py<br/>round-robin loop: in each round every villager takes one turn"]
    loop --> wake

    subgraph villager["Per-villager LangGraph graph"]
        wake["wake<br/>new chat messages and the remaining budget"] --> compact["compact<br/>summarize older turns when the context gets too big"]
        compact --> thinking["thinking<br/>one model call"]
        thinking -->|"tool calls"| act["act<br/>run the tools"]
        act -->|"tool rounds left"| compact
        thinking -->|"no tool calls"| done(["end of turn"])
        act -->|"tool round limit or budget reached"| done
    end

    subgraph sqlite["runs/RUN_ID/village.db (SQLite)"]
        chat[("chat")]
        board[("task board")]
        budget[("shared token budget")]
        events[("event log")]
        checkpoints[("graph checkpoints")]
    end

    subgraph docker["Docker: one container per villager"]
        c1["claude"]
        c2["chatgpt"]
        c3["deepseek"]
        c4["gemini"]
    end

    repo[("runs/RUN_ID/repo on the host")]

    act -->|"post_chat, task tools"| chat
    act --> board
    act -->|"run_command, write_file, read_file"| docker
    thinking -->|"tokens used"| budget
    act -->|"every action"| events
    villager -.->|"state"| checkpoints
    c1 & c2 & c3 & c4 -->|"bind mount at /repo"| repo
```

- **Turns.** The village runs in rounds. In a round each villager takes one turn of up to `--max-tool-rounds` model calls. The run stops after `--rounds` rounds, or as soon as the shared input or output budget is used up.
- **Tools.** Every villager can run shell commands and read and write files in its container, post to the chat, and use the task board. The leader can also post tasks and mark them done.
- **Containers.** `/repo` is the same host directory in every container, and it is the village's real output. Anything outside `/repo` is private to one container and is lost when the run ends.
- **Memory.** When a villager's context grows past `--compact-trigger` tokens, its older turns are summarized into the system prompt and the recent turns are kept.

## Requirements

- Python. Tested with Python 3.13; the code avoids 3.12-only syntax but has not been tested on older versions.
- Docker with a running engine (`docker info` must work). Tested with Docker Desktop on Windows 11, engine 29.6.2. The container image (`env/Dockerfile`, about 350 MB) is built automatically on first use.
- API keys for Anthropic, OpenAI, DeepSeek and OpenRouter.

## Setup

```bash
python -m venv .venv
.venv/bin/pip install -r requirements.txt        # Windows: .venv\Scripts\pip install -r requirements.txt
```

Create a `.env` file next to `village.py` with these four variables:

```
ANTHROPIC_API_KEY=...
OPENAI_API_KEY=...
DEEPSEEK_API_KEY=...
OPENROUTER_API_KEY=...
```

The keys stay on the host. They are never passed into a container.

## Running

```bash
python village.py --goal                          # default goal: build an open-source tool for university students
python village.py --goal build a flashcard app    # your own goal, quotes optional
python village.py --resume                        # continue the latest run
python village.py --resume 20261124_024029        # continue a given run (id, run directory or village.db path)
```

| Option | Default | Meaning |
|---|---|---|
| `--rounds` | 10 | Rounds to run in this invocation; in one round every villager takes one turn |
| `--max-tool-rounds` | 15 | Model calls with tool use a villager may make in one turn |
| `--input-budget` | 3,000,000 | Input tokens the whole village may spend, cached tokens included |
| `--output-budget` | 300,000 | Output tokens the whole village may spend |
| `--compact-trigger` | 40,000 | Approximate context size in tokens above which a villager's memory is compacted |
| `--command-timeout` | 120 | Seconds before a shell command in a container is killed |
| `--offline` | off | Start the containers without network access |

The budgets apply to the whole run, across resumes. Each call to `village.py` runs `--rounds` more rounds.

## Output

Each run gets its own directory:

```
runs/<run_id>/
    village.db       chat, task board, token budget, event log, graph checkpoints
    repo/            the shared /repo: what the villagers built
    transcript.md    written by transcript.py
```

To export a run as Markdown, run the following:

```bash
python transcript.py                    # latest run, one file: runs/<run_id>/transcript.md
python transcript.py 20261124_024029    # a given run
python transcript.py --split            # a directory: runs/<run_id>/transcript/README.md plus one file per round
python transcript.py --split --output examples/my-run/transcript
```

The transcript lists the villagers, the limits and a token and command table per villager. After that comes every round and turn in order, showing what was said, posted, run and written. Failed commands are marked `[FAILED]` and failed turns `[TURN ERROR]`.

A long run makes a single file too large for GitHub to render, so use `--split` for those. The index `README.md` holds the header and a table of rounds that links to `round-001.md`, `round-002.md` and so on. `--output` sets where the file or directory is written. A split export replaces any `round-*.md` files already in that directory.

## Tests

```bash
python -m pytest
```

The tests do not call any model API. The tests in `tests/test_sandbox.py` and the first test in `tests/test_transcript.py` need a running Docker engine and are skipped without one. They drive the tools as two villagers through a bug fix, and check timeouts, path checks, container isolation and cleanup.

## Safety and limits

- **Container limits.** Containers run as an unprivileged user, with all capabilities dropped, `no-new-privileges`, 1 GB of memory, 2 CPUs and 256 processes. Only the run's `repo/` directory is mounted, and no host environment variables or API keys are passed in.
- **Network.** Containers have network access by default, so the agents can `pip install`. That also means they can reach the internet, the host's local network and, on Docker Desktop, the host itself through `host.docker.internal`. Use `--offline` to start them without a network.
- **Agent code on the host.** The agents' code runs inside the containers, but what they write to `repo/` ends up on the host. Read it before running it outside a container.
- **Hard kills leave containers.** Containers are removed when a run ends, fails or is stopped with Ctrl+C. A hard kill, such as closing the terminal or killing the process, skips that cleanup. Resuming the same run removes its old containers, or you can remove all village containers by hand:

  ```bash
  docker rm -f $(docker ps -aq --filter label=village.run)
  ```

- **Costs.** Every model call costs money. The token budget is checked between model calls, so a run can go slightly over it by the last call.

## Example run

*To be added after the first long run.*
