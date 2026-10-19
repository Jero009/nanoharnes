# NanoHarness 1.0 test plan

This is a **finite release gate**, not a request to add more features. Target: source-run Linux NanoHarness with a tool-capable OpenAI-compatible model; LM Studio is the intended local setup. Cross-provider API compatibility is out of scope. Perform destructive tests only in a disposable checkout, never against your everyday `workspace/` or `.nanoharness/` data.

A test passes only when its **observed result** matches the expected result. A model's claim that it used a tool does not prove the tool ran: inspect tool events/results and the target file or memory store. Record model name, server version, git commit, OS, command/prompt, observed result, and pass/fail for live runs. Do not record API keys or private memory contents.

## A. Existing automated baseline — run on every change

From a fresh checkout, with no `.env` and no `BASE_URL`/`API_KEY` in the environment:

```bash
uv sync --frozen
uv run python -m unittest discover -s tests -v
git diff --check
```

The existing suite covers streamed text/reasoning, multi-chunk tool calls and call IDs, invalid JSON/unknown tools, tool-round and token limits, history trimming, TUI approvals, memory create/update/delete/compaction, workspace path checks, shell isolation/output, and missing configuration. **All tests must pass**; the current suite passing is not proof of the live-model workflow or the gaps below. The shell tests require working bubblewrap and unprivileged namespaces.

## B. Add focused automated regressions before 1.0

Write these as isolated tests in the existing `tests/` modules. For each, make the test fail for the relevant bug before changing production code. Avoid a test-only framework or a broad rewrite.

| ID | Test stimulus | Required result |
|---|---|---|
| L1 | Completed stream followed by a new turn; make prior tool output/history large enough to exceed a deliberately small input budget | Request context stays bounded while preserving the current question and valid assistant/tool-call pairs; report when it cannot fit rather than silently dropping the question. The existing eight-turn limit alone is not a token budget. |
| L2 | Stream raises a transport error after partial text or partial tool-call JSON | No partial tool executes, no fabricated completed assistant response is added; the current user question remains available for a successful retry and the UI shows an error. |
| L3 | Model request times out, or model discovery fails/returns no models | Clear recoverable error, no indefinitely busy composer, no destructive tool execution, and a subsequent attempt can succeed. |
| L4 | A streamed tool call is missing an ID/name or has an invalid/inconsistent index | Do not execute malformed calls or send an invalid assistant/tool pair to the next model request; surface a useful error. |
| L5 | Multiple tool calls arrive interleaved, including one malformed call | Preserve each valid original call ID and result ordering; malformed input cannot execute another tool accidentally. |
| L6 | Stream includes an informational chunk with no choices before a valid completion | Skip the empty chunk without losing the answer or crashing. |
| L7 | Stream contains a tool-call fragment but ends with `finish_reason=stop` rather than `tool_calls` | Do not execute the tool: require a completed tool-call finish reason before side effects. |
| S1 | File overwrite fails during a simulated write error | Existing content remains intact; error is reported. |
| S2 | Rename, create, edit, delete, and read through symlinks or traversal attempts | No access outside the allowed workspace; no outside file changes. Test each actual mutation path, not only `read_file`. |
| S3 | Shell command exceeds its time limit or starts a child that keeps its output pipe open | Return promptly, kill sandbox descendants, and leave no delayed workspace write after timeout. |
| S4 | Approver raises an exception or explicitly denies a shell/file/memory deletion | No mutation or command execution; fail closed with a clear result. |
| M1 | Memory write/compaction fails after making its temporary file or backup | Previous store remains readable; no partial JSON replaces it, and approved deletions can be recovered from the backup. |

Only add a test if the risk is real in the current execution path; if an existing test already proves an item, link to it rather than duplicate it. Fix failing P0 tests before proceeding to the live gate.

## C. Live LM Studio acceptance — optional follow-up in a disposable checkout

Jernej waived a separate LM Studio run for the 1.0 release decision. This checklist remains for later verification of the intended local setup; none of its unperformed items is marked passed. The prior OmniRoute run is supplemental live evidence, not LM Studio certification.

Make a separate checkout and configure its own `.env` for the running server. Confirm the model name shown/used is the intended loaded model. Use unique throwaway filenames and memory keys (for example `release_probe.txt` and `release_probe_fact`); do **not** point these tests at your normal checkout. Run this table in order, capturing the visible tool result and checking the filesystem or `.nanoharness/memories.json` after each write. Delete only test data in the disposable checkout.

| ID | Action / prompt | Pass condition |
|---|---|---|
| E1 | Ask a simple question requiring no tool. | A complete answer appears, no spurious tool call, next prompt remains usable. |
| E2 | Ask the model to create `release_probe.txt` in the workspace containing a unique phrase, then ask it to read the file and quote that phrase. | Actual workspace file matches the phrase; the tool result is linked to the right call; answer agrees with the file. |
| E3 | Ask for a safe sandbox command such as `pwd`; approve it. | Approval shows the exact command; it runs only after approval, returns the workspace path, and the UI recovers. |
| E4 | Ask for another harmless command (`pwd`), but deny approval. | No command executes; denial is returned to the model; no success is claimed. |
| E5 | Ask the model to save a harmless test fact under `release_probe_fact`. Restart NanoHarness and ask it to retrieve that key. | Memory is persisted across process restart, read from the actual store, and create did not ask for ordinary approval. |
| E6 | Ask to update that fact, then delete it and **deny** approval; verify it still exists. Ask again and **approve**; verify it is absent. | Update is automatic; both deletion decisions are honored and reflected in the store. |
| E7 | Ask to delete `release_probe.txt`, deny once, then approve. | The file survives denial and is removed only after explicit approval. |
| E8 | In the disposable checkout only, temporarily lower the completion limit to force `finish_reason=length` on a long response and a tool-call attempt, then restore the default. | UI marks the response incomplete; no partial tool executes. The next turn retains the preceding conversation and succeeds. Confirm the limit is restored before any commit. |
| E9 | Stop the server or sever the connection during a reply; restart it and retry. | Clear error; no partial tool executes; the composer becomes usable again and the conversation does not silently claim success. |
| E10 | Close and reopen the TUI; try `/help`, `/clear`, and `/new`, including a narrow terminal and keyboard-only approval. | TUI remains usable; `/clear` hides chat, `/new` resets context, and approval defaults to denial on Escape/close. Persistent memory is unaffected by `/new`. |

Model behavior is nondeterministic. If it chooses not to call the requested tool, record that as an inconclusive live probe and retry with an explicit tool request; do not mark tool execution passed based on a plausible answer alone.

An approved alternate OpenAI-compatible gateway (such as OmniRoute) can provide **supplemental** live integration evidence in a disposable checkout. Record its model and endpoint separately; it does not certify LM Studio or general provider compatibility. Obtain credentials only through an authorized path, never put them in the checkout or logs.

## D. Release decision

- All existing automated tests and the additional **applicable** P0 regressions pass in a clean checkout.
- The core live workflow has supplemental OmniRoute evidence recorded in [TEST_RESULTS.md](TEST_RESULTS.md); live file deletion, a server disconnect, and the newest running-summary change are **not verified**. Jernej waived a separate LM Studio test and requested a 1.0 release with these gaps recorded. Do not claim E1–E10 or the current revision passed live on LM Studio.
- No known critical/high data-loss, sandbox-escape, approval-bypass, or stuck-session bug remains.
- Setup from the documented fresh checkout succeeds. Inspect the final diff and source-release contents for secrets and generated user data.
- Only then tag the corrected source `v1.0.0` and publish a GitHub release titled **1.0**; read the remote release back to verify its tag and published state. Preserve the earlier pushed `v1.0` tag (it points to an older commit with package version `0.1.0`); do not silently move that public tag.

After this gate, stop feature work for 1.0 and switch to maintenance. Skills, broad provider certification, and speculative extension systems are not part of this test plan.
