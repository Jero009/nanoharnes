# Nano Harness

A small local agent harness for OpenAI-compatible servers such as LM Studio.
It provides file tools, directory tools, isolated shell commands, summaries, and persistent memory.

## Requirements

- Python 3.10+
- LM Studio or another OpenAI-compatible local server
- `bubblewrap` for isolated shell commands
- Python packages: `openai`, `rich`, and `typer`

Install the packages with:

```bash
pip install openai rich typer
```

## Run

Start the local model server, then run:

```bash
python main.py
```

The harness connects to:

```text
http://localhost:1234/v1
```

The first available model is used automatically.

## Commands

Inside the chat:

- `/help` show commands
- `/new` start a new chat
- `/yolo` allow destructive file and shell actions without approval
- `/reasoning` show or hide model reasoning output
- `/memory` switch between fast trimming and summary memory
- `/bye` exit

## Configuration

Edit `config/settings.py` to change local server and agent limits:

- `BASE_URL` local OpenAI-compatible server URL
- `MAX_TOKENS` maximum response tokens
- `MAX_TOOL_ROUNDS` maximum tool rounds per request
- `MAX_MEMORY_CHARS` persistent memory size
- `MAX_FILE_SIZE_BYTES` maximum file size for normal reads
- `CONTEXT_LENGTH` maximum text sent to summarization
- `MAX_OUTPUT_CHARS` maximum shell output returned to the model

## Workspace

File and directory tools are restricted to the `workspace/` directory.
Shell commands run inside a Bubblewrap namespace with the workspace as the writable area and network access disabled.

Use relative paths such as:

```text
notes/todo.md
src/example.py
```

## Persistent Memory

Important facts can be saved with the `save_memory` tool.
They are stored in:

```text
memory/core_memory.md
```

The main system prompt loads this memory when a chat starts.

## Project Layout

```text
main.py                    Main chat entrypoint
config/                    Settings, sandbox rules, and prompts
skills/                    Agent tools
memory/                    Context trimming and persistent memory
workspace/                 Agent working directory
dev/                       Notes and development files
```

## Safety

Destructive file, directory, and shell actions ask for approval by default.
Use `/yolo` only when you understand the command and its consequences.
