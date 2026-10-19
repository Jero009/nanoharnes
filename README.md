# NanoHarness

A local terminal coding agent for an OpenAI-compatible chat-completions server. Run it from a source checkout on Linux; `install.sh` installs checkout-local dependencies, not a system-wide package.

## Requirements

- Python 3.11+ and [uv](https://docs.astral.sh/uv/)
- [bubblewrap](https://github.com/containers/bubblewrap) (`bwrap`) with working unprivileged namespaces for the approved shell tool
- An OpenAI-compatible server with a loaded model supporting streamed chat completions and tool calls (verify behavior with your own model)

## Start with LM Studio

Start LM Studio's local server, load a tool-capable model, then from a fresh checkout:

```bash
git clone https://github.com/Jero009/nanoharnes.git
cd nanoharnes
./install.sh
uv run python src/main.py
```

`install.sh` checks Linux, `uv`, and `bwrap`, runs `uv sync --frozen` in this checkout, and copies `.env.example` to `.env` only when `.env` does not already exist. It never removes workspace files or replaces existing configuration. You can also install manually with `uv sync --frozen` and `cp .env.example .env`.

Edit `.env` first if LM Studio is not on `localhost:1234`. `API_KEY=lm-studio` is a placeholder accepted by a local LM Studio server; for a remote provider, use its actual key. Never commit `.env`. NanoHarness selects the first model returned by the server's `/v1/models` endpoint, so load the model you intend to use before starting.

The default output cap is 4,096 tokens per model request. A token-limit response is reported as incomplete; partial tool calls are not executed. When chat exceeds 15 messages, NanoHarness summarizes the oldest **complete** turns into a running summary (at least five messages, and all turns that would otherwise be dropped by the eight-turn retention limit). Summarization is an extra model request capped at 300 output tokens; if it fails or returns an incomplete response, the usual eight-turn trim applies and a status is shown. Summaries are approximate, session-only context, not durable memory or authoritative instructions. Requests remain subject to a 100,000-character serialized budget; tool results are truncated after 10,000 characters with a marker when sent to the model. This character budget is not an exact token count or a guarantee for every model context window. Longer-term facts belong in model-managed memory tools.

## Data and approvals

- File tools and approved shell commands operate in `workspace/`; shell commands run without network access in bubblewrap. File tools reject symlink paths (including symlinks pointing back into the workspace) and pin each parent directory before access, preventing a replacement symlink from redirecting the operation to an unrelated outside target. This is not a guarantee against a separate process moving an already-open directory.
- Memory facts live in `.nanoharness/memories.json` and are not available through ordinary workspace file tools. Creation and updates do not prompt; deletion and size-triggered compaction require approval. Treat model-saved facts as data, not trusted instructions.
- Shell commands and file deletion require approval. Denial leaves the target unchanged.
- `/yolo` toggles automatic approval of shell commands, file and memory deletion, and memory compaction for the current chat. `/yolo on` and `/yolo off` set it explicitly. It is **off by default**; a persistent `YOLO ON` hint warns when prompts are bypassed. `/new`, Ctrl+L, or exiting the app turns it off. `/clear` only hides chat and leaves the setting unchanged. Workspace and sandbox limits still apply, but a mistaken model action can delete data without a prompt: use this only with disposable data or a backup.
- `workspace/`, `.nanoharness/`, and `.env` are local data and are gitignored. **Before upgrading an older checkout**, copy any `workspace/` files you want to keep to a safe location: this release removes previously tracked test-output files from Git, and pulling that deletion may remove those copies. The memory file is not touched by this cleanup.

## Verify

```bash
uv run python -m unittest discover -s tests -v
```

The shell tests execute real bubblewrap commands on Linux. For the published 1.0 release's verification scope and remaining live-test gaps, see its [release notes](https://github.com/Jero009/nanoharnes/releases/tag/v1.0.0). The release tag retains the original audit documents. Check actual tool results and stored data rather than assuming a successful tool call.

## Memory and context

These are cooperating mechanisms, **not selectable modes**. The model may save and retrieve persistent facts with memory tools; `.nanoharness/memories.json` survives `/new` and restarts. Creation and updates are automatic; deletion and size-triggered compaction require approval. Conversation summaries are session-only: after chat exceeds 15 messages, NanoHarness asks the model to summarize complete older turns before keeping the newest eight user turns. If summarization fails, it reports the failure and uses the eight-turn trim. A 100,000-character serialized request budget may omit older turns or shorten tool results even earlier. `/new` resets the conversation but not persistent memory; `/clear` only hides the visible chat.

There is no TUI switch among memory, summarization, and trimming. `src/config/settings.py` contains the eight-turn and request-size limits; `src/context/history.py` contains the 15-message summary trigger. Changing these requires editing source and restarting; it does not change what has already been summarized or forgotten.
