# NanoHarness 1.0 test results (pre-release audit)

Original audit source: `main` at `cdbb86a` plus the send-button/divider removal. The failures below describe that original audit; see the post-fix retest at the end. This is **not** a 1.0 certification. See [TEST_PLAN.md](TEST_PLAN.md) for the acceptance criteria. No production LM Studio server was reachable from this test machine; the user reported chat and tools working there. The alternate gateway probes below used OmniRoute `auto/best-chat` (routing may select different underlying models), in a disposable checkout with no existing user data. No credentials were saved to that checkout.

## Verified locally

- Fresh source snapshot: `uv sync --frozen` installed dependencies; all **85** unittest cases passed without provider configuration. `git diff --check` passed.
- Rendered Textual TUI (80×24) inspected: no send button or border dividing chat from composer; Enter still submits. UI error-injection probe showed a partial reply followed by an error, then a usable composer and successful next turn.
- OmniRoute live `run_turn`: normal answer; file creation and read with actual disk contents and matching tool-call IDs; memory creation without approval, read from a restarted process, update without approval, denied and approved deletion; denied and approved sandbox command (`pwd`); a short generation budget yielded a truncation status with no completed assistant history, and a follow-up recalled the prior phrase.
- Safety probes in disposable directories: symlink/traversal attempts against file and directory tools did not alter the outside file (no concurrent path-swap test); denials caused no mutation; memory failed atomic replacement preserved the prior store and its compaction backup was readable. A real shell deadline returned after about 30 seconds and did not create a delayed file; bounded output and network isolation are covered by the unit suite.

## Confirmed failures (do not mark release gate green)

| Severity | Reproduction and observed behavior | Correct behavior |
|---|---|---|
| High — data loss | Inject a write error after truncation in `edit_file(..., mode="overwrite")` with existing content `ORIGINAL`. It returns an error but the file contains `PARTIAL` (`src/tools/file_tools.py:92`). | Write a temporary sibling then atomically replace, preserving the original on failure. |
| High — unvalidated tool calls | A stream containing a valid tool name/JSON but **no call ID** still executes the tool and creates a tool result with a null ID (`src/loop.py:68–75, 87–145`). | Reject malformed call metadata before executing any side effect. |
| High — premature tool execution | A stream with tool-call data but `finish_reason="stop"` executes the tool anyway (`src/loop.py:80, 87–119`). A repeated mocked response invoked it five times before the round limit. | Execute only complete, validated tool calls with a matching `tool_calls` finish reason. |
| Medium — unbounded input | One retained tool result of 200,000 characters reached the next model request as a 200,903-character message payload despite the eight-turn cap (`src/context/history.py`, `src/loop.py:27–41`). | Budget request context without breaking assistant/tool pairs or dropping the current question. |
| Medium — lost question on discovery error | When `get_model_name()` raises, `run_turn()` has not yet appended the user question, so a retry cannot recover that turn (`src/loop.py:24–26`). | Preserve the question and report a recoverable error. |
| Medium — stream crash | A streamed chunk with `choices=[]` raised `IndexError` at `src/loop.py:49`. This occurred in one live OmniRoute coding-alias probe and in a deterministic mock. | Ignore empty informational chunks or handle them explicitly without losing the turn. |
| Low — approval callback exception | A raising approval callback prevents mutation, but direct `execute_command` and `delete_file` calls propagate `RuntimeError` instead of returning a denial. The model dispatcher catches it (`src/tools/shell_tools.py:16`, `src/tools/file_tools.py:116`). | Fail closed with a consistent user-facing result. |

The disposable loop probe suite had **2 passing, 4 failing, and 1 erroring** cases: partial-stream disconnect and valid interleaved call IDs passed; the five loop failures above are reproducible. These probes are intentionally outside the green repository suite until the underlying behavior is fixed.

## Not verified / inconclusive

- No direct live LM Studio run from this machine, despite the user's report that chat and tools work on their setup.
- OmniRoute did not reliably choose `delete_file` when requested with `tool_choice="auto"`; live file deletion approval/denial was inconclusive. The existing automated file-deletion tests passed.
- An actual mid-stream server disconnect was not induced; a deterministic simulated stream error and TUI worker error were tested.
- Concurrent symlink/path-swap races and a full UI smoke test on the user's terminal were not performed.
- One OmniRoute response after a successful `pwd` tool result gave unrelated prose; treat this as model/router variability, not proof of a harness bug. The TUI currently shows the tool name, not the returned result, which makes such misreporting harder for a user to spot.

## Post-fix retest

The subsequent bug-fix change addressed all seven confirmed failures above. The full suite now passes **103 tests** without provider configuration, including from a fresh source snapshot. All seven disposable loop probes pass. Fault-injected atomic replacement leaves the original file intact and cleans up the temporary sibling; literal `True` is now required for shell/file deletion approval. A supplemental OmniRoute tool call after the fixes created the expected file in a disposable checkout. A 100,000-character `read_file` result and multiple large results now reach the model as bounded, explicitly marked truncated tool messages with matching call IDs instead of stranding the turn. A regression test also covers short tool text whose JSON escaping makes it exceed the request budget.

Remaining limits: request budgeting uses serialized **characters**, not an exact model tokenizer; concurrent filesystem path-swap races have not been ruled out; live LM Studio and the inconclusive cases above still require their own acceptance evidence. Do not tag or publish 1.0 until the full [release gate](TEST_PLAN.md#d-release-decision) is met.
