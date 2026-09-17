# Nano Harness

Nano Harness is a local AI agent for OpenAI-compatible APIs. It provides file, directory, shell, and persistent-memory tools with approval checks for destructive actions.

## Requirements

- Python 3.10+
- `uv`
- `bubblewrap` for isolated shell tools
- LM Studio, Ollama, or another OpenAI-compatible API

Install `bubblewrap` with your system package manager. For Debian or Ubuntu:

```bash
sudo apt install bubblewrap
```

## Install and Run

Clone the repository, enter the project directory, and run:

```bash
./install.sh
```

The installer creates `.venv` when needed and installs the packages from `requirements.txt`.

On the first launch, Nano Harness asks you to choose a provider and a model-size profile. The profiles configure the context window, response length, memory limits, tool rounds, and output limits:

- Under 15B
- Around 27B
- Over 50B

Settings are saved in `.env`, which is ignored by Git. The first available model from the selected server is used automatically.

To run it after setup without the installer:

```bash
.venv/bin/python main.py
```

## Commands

Commands are entered inside the chat:

| Command | Action |
| --- | --- |
| `/help` | Show available commands |
| `/new` | Start a new chat |
| `/settings` | View or edit individual saved settings |
| `/memory` | Toggle fast trimming or smart summary memory |
| `/reasoning` | Toggle reasoning output |
| `/yolo` | Toggle automatic approval for destructive actions |
| `/bye` | Exit Nano Harness |

Changes made through `/settings` are saved to `.env`. Restart Nano Harness for them to take effect.

## Configuration

The setup wizard and `/settings` manage these values:

- `API_KEY` and `BASE_URL`
- `MAX_TOKENS`
- `CONTEXT_LENGTH`
- `MAX_MEMORY_CHARS`
- `MAX_TOOL_ROUNDS`
- `MAX_OUTPUT_CHARS`
- `MAX_FILE_SIZE_BYTES`
- `DEFAULT_MEMORY_MODE`

To run first-time setup again:

```bash
rm -f .env
./install.sh
```

## Workspace and Safety

File and directory tools are restricted to `workspace/`. Shell commands run inside a Bubblewrap namespace with the workspace as the writable area and network access disabled.

Destructive file, directory, and shell actions ask for approval by default. Use `/yolo` only when you understand the command and its consequences.

## Project Layout

```text
main.py                    Chat entrypoint
config/                    Settings, setup wizard, prompts, and sandbox rules
skills/                    Agent tools
memory/                    Context trimming and persistent memory
workspace/                 Agent working directory
dev/                       Development notes
install.sh                 Environment setup and launcher
requirements.txt           Python dependencies
```
