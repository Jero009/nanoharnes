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

## SWE-bench Lite on your PC

This is a **coding-agent** evaluation, not a model-only test. Use a Linux PC (or WSL2 with Docker and working bubblewrap user namespaces), with `git`, `uv`, `bwrap`, Docker, and an OpenAI-compatible local model server. The official Docker evaluator recommends at least 120 GB free disk and 16 GB RAM. NanoHarness itself still needs its ordinary `BASE_URL` and `API_KEY` in `.env`; for LM Studio, start the server and load a tool-capable model first. Check the exact model ID with `curl http://localhost:1234/v1/models` rather than relying on its order. **Do not run this in your normal NanoHarness workspace.**

From your NanoHarness checkout, first test one of the 23 development instances:

```bash
uv sync --frozen
uv run --with datasets python export_swebench_lite.py --split dev \
  --revision 6ec7bb89b9342f664a54a6e0a6ea6501d3437cc2 --output dev.jsonl
head -n 1 dev.jsonl > dev-one.jsonl
uv run python benchmark_batch.py --manifest dev-one.jsonl \
  --run-dir dev-smoke --model 'EXACT_MODEL_ID'
```

The export writes **only** issue text, repository, base commit and instance ID; it omits solution and grading patches. The batch driver fetches only the base commit into a new temporary Git checkout per issue, runs the existing headless NanoHarness loop with 20 tool rounds (the interactive default stays 5), disables memory tools and automatically approves sandboxed shell/file operations **only inside the disposable checkout**, then writes `dev-smoke/predictions.jsonl`. Failures appear in `dev-smoke/failures.jsonl` as empty predictions. Empty patches are not successful fixes. Each run directory must be new; the temporary checkout is removed after each issue. The agent's shell has no network, a 30-second per-command timeout and no automatic access to repository-specific installed Python dependencies; the official evaluator runs tests separately. Check failure counts, tool-call behavior, and patch content before scaling up. Never put private data or secrets in the benchmark checkout.

Grade the smoke prediction with the official SWE-bench Docker evaluator installed in a **separate environment** on your PC (follow [its installation guide](https://www.swebench.com/SWE-bench/installation/), not NanoHarness's `.venv`):

```bash
python -m swebench.harness.run_evaluation \
  --dataset_name princeton-nlp/SWE-bench_Lite --split dev \
  --predictions_path /ABS/PATH/TO/dev-smoke/predictions.jsonl \
  --max_workers 1 --cache_level base --run_id nh-dev-smoke
```

When this passes end to end, export `--split test` to a new `test.jsonl`, run `benchmark_batch.py --manifest test.jsonl --run-dir base-run --model 'BASE_ID'`, and grade with `--split test --run_id nh-base`. After fine-tuning the **same base checkpoint**, load the tuned model in the same server and rerun the **same** `test.jsonl` with `--run-dir tuned-run --model 'TUNED_ID'`, then grade with `--run_id nh-tuned`. Never reuse evaluator `run_id` across different predictions: its result cache does not account for changed patches. Compare resolved instances and errors in each evaluator's `logs/evaluation/<run_id>/results.json` and per-instance reports. Pin the NanoHarness commit, dataset revision, evaluator version, model/server configuration, tool-round limit and prompt for both runs. Do not train on the test issues, gold patches, or grading results; use development data to choose the setup **before** scoring the test split.

This runner intentionally handles one issue per process and tasks sequentially to keep a local GPU from being oversubscribed. It does not install per-repository dependencies in the agent's bubblewrap shell; if you require in-agent test execution on SWE-bench environments, that needs a separately verified sandbox/environment integration rather than unsandboxed commands. Do not interpret a server/model error as a benchmark score improvement.

## Memory and context

These are cooperating mechanisms, **not selectable modes**. The model may save and retrieve persistent facts with memory tools; `.nanoharness/memories.json` survives `/new` and restarts. Creation and updates are automatic; deletion and size-triggered compaction require approval. Conversation summaries are session-only: after chat exceeds 15 messages, NanoHarness asks the model to summarize complete older turns before keeping the newest eight user turns. If summarization fails, it reports the failure and uses the eight-turn trim. A 100,000-character serialized request budget may omit older turns or shorten tool results even earlier. `/new` resets the conversation but not persistent memory; `/clear` only hides the visible chat.

There is no TUI switch among memory, summarization, and trimming. `src/config/settings.py` contains the eight-turn and request-size limits; `src/context/history.py` contains the 15-message summary trigger. Changing these requires editing source and restarting; it does not change what has already been summarized or forgotten.
