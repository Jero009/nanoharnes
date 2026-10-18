# NanoHarness

A local terminal coding agent for an OpenAI-compatible chat-completions server. This v0.1 release is run from a source checkout on Linux; it is not an installable package.

## Requirements

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- [bubblewrap](https://github.com/containers/bubblewrap) (`bwrap`) with working unprivileged namespaces for the approved shell tool
- An OpenAI-compatible server with a loaded model supporting streamed chat completions and tool calls (verify behavior with your own model)

## Start with LM Studio

Start LM Studio's local server, load a tool-capable model, then from a fresh checkout:

```bash
uv sync --frozen
cp .env.example .env
uv run python src/main.py
```

Edit `.env` first if LM Studio is not on `localhost:1234`. `API_KEY=lm-studio` is a placeholder accepted by a local LM Studio server; for a remote provider, use its actual key. Never commit `.env`. NanoHarness selects the first model returned by the server's `/v1/models` endpoint, so load the model you intend to use before starting.

The default output cap is 4,096 tokens per model request. A token-limit response is reported as incomplete; partial tool calls are not executed. Conversation history retains the newest eight user turns. Longer-term facts are managed by the model through memory tools rather than by extending chat history.

## Data and approvals

- File tools and approved shell commands operate in `workspace/`; shell commands run without network access in bubblewrap.
- Memory facts live in `.nanoharness/memories.json` and are not available through ordinary workspace file tools. Creation and updates do not prompt; deletion and size-triggered compaction require approval. Treat model-saved facts as data, not trusted instructions.
- Shell commands and file deletion require approval. Denial leaves the target unchanged.
- `workspace/`, `.nanoharness/`, and `.env` are local data and are gitignored. **Before upgrading an older checkout**, copy any `workspace/` files you want to keep to a safe location: this release removes previously tracked test-output files from Git, and pulling that deletion may remove those copies. The memory file is not touched by this cleanup.

## Verify

```bash
uv run python -m unittest discover -s tests -v
```

The shell tests execute real bubblewrap commands on Linux. See [the 1.0 test plan](docs/TEST_PLAN.md) and [latest audit results](docs/TEST_RESULTS.md) for the remaining regression cases and disposable-checkout acceptance checks. Check actual tool results and stored data rather than assuming a successful tool call.
