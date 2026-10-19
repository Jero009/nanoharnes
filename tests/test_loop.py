import copy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

with patch.dict("os.environ", {"BASE_URL": "http://127.0.0.1:1/v1", "API_KEY": "test"}):
    import loop as agent_loop

def text_chunk(content: str, finish_reason: str | None = "stop"):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=content,
                    tool_calls=None,
                ),
                finish_reason=finish_reason,
            )
        ]
    )

def tool_chunk(
    *,
    index: int,
    call_id: str | None,
    name: str | None,
    arguments: str,
    finish_reason: str | None = "tool_calls",
):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=None,
                    tool_calls=[
                        SimpleNamespace(
                            index=index,
                            id=call_id,
                            function=SimpleNamespace(
                                name=name,
                                arguments=arguments,
                            ),
                        )
                    ],
                ),
                finish_reason=finish_reason,
            )
        ]
    )

class LoopTests(unittest.TestCase):
    def test_summary_is_in_live_request_without_internal_marker(self):
        messages = agent_loop.new_messages()
        for index in range(8):
            messages.extend([{"role": "user", "content": f"earlier-{index}"},
                             {"role": "assistant", "content": f"reply-{index}"}])
        summary = SimpleNamespace(choices=[SimpleNamespace(
            finish_reason="stop", message=SimpleNamespace(content="Earlier topic: telescope"))])
        requests = []
        def respond(**kwargs):
            requests.append(copy.deepcopy(kwargs))
            return summary if not kwargs.get("stream") else [text_chunk("done")]
        with patch.object(agent_loop.client.chat.completions, "create", side_effect=respond):
            agent_loop.run_turn(messages, "new question", model_name="test-model")
        self.assertEqual(len(requests), 2)
        self.assertFalse(requests[0]["stream"])
        self.assertEqual(requests[0]["max_tokens"], 300)
        self.assertTrue(requests[1]["stream"])
        sent = requests[1]["messages"]
        self.assertIn("Earlier topic: telescope", sent[1]["content"])
        self.assertEqual(sent[1]["role"], "assistant")
        self.assertTrue(all("is_summary" not in item for item in sent))
        self.assertEqual(sent[-1]["content"], "new question")
        self.assertEqual(messages[-1]["content"], "done")

    def test_summary_includes_every_turn_that_retention_would_drop(self):
        messages = agent_loop.new_messages()
        for index in range(12):
            messages.extend([{"role": "user", "content": f"earlier-{index}"},
                             {"role": "assistant", "content": f"reply-{index}"}])
        summary = SimpleNamespace(choices=[SimpleNamespace(
            finish_reason="stop", message=SimpleNamespace(content="All earlier facts"))])
        requests = []
        def respond(**kwargs):
            requests.append(copy.deepcopy(kwargs))
            return summary if not kwargs.get("stream") else [text_chunk("done")]
        with patch.object(agent_loop.client.chat.completions, "create", side_effect=respond):
            agent_loop.run_turn(messages, "current", model_name="test-model")
        source = requests[0]["messages"][1]["content"]
        self.assertIn("earlier-4", source)
        self.assertNotIn("earlier-5", source)
        sent = requests[1]["messages"]
        self.assertIn("All earlier facts", sent[1]["content"])
        self.assertEqual(sent[2]["content"], "earlier-5")
        self.assertEqual(sent[-1]["content"], "current")

    def test_failed_summary_does_not_stop_followup_request(self):
        messages = agent_loop.new_messages()
        for index in range(8):
            messages.extend([{"role": "user", "content": f"earlier-{index}"},
                             {"role": "assistant", "content": f"reply-{index}"}])
        events = []
        requests = []
        def respond(**kwargs):
            requests.append(copy.deepcopy(kwargs))
            if not kwargs.get("stream"):
                raise OSError("summarizer unavailable")
            return [text_chunk("recovered")]
        with patch.object(agent_loop.client.chat.completions, "create", side_effect=respond):
            agent_loop.run_turn(messages, "current", model_name="test-model",
                                emit=lambda kind, text: events.append((kind, text)))
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[1]["messages"][-1]["content"], "current")
        self.assertTrue(any(kind == "status" and "Summary failed" in text for kind, text in events))
        self.assertEqual(messages[-1]["content"], "recovered")

    def test_missing_or_invalid_tool_metadata_rejects_entire_batch(self):
        for malformed in (
            tool_chunk(index=1, call_id=None, name="dangerous", arguments="{}"),
            tool_chunk(index=1, call_id="  ", name="dangerous", arguments="{}"),
            tool_chunk(index=1, call_id="id", name=None, arguments="{}"),
            tool_chunk(index=1, call_id="id", name="  ", arguments="{}"),
            tool_chunk(index=None, call_id="id", name="dangerous", arguments="{}"),
            tool_chunk(index=-1, call_id="id", name="dangerous", arguments="{}"),
            tool_chunk(index="0", call_id="id", name="dangerous", arguments="{}"),
        ):
            with self.subTest(malformed=malformed):
                tool = Mock()
                messages = agent_loop.new_messages()
                events = []
                valid = tool_chunk(index=0, call_id="valid", name="dangerous",
                                   arguments="{}", finish_reason=None)
                with patch.object(agent_loop.client.chat.completions, "create",
                                  return_value=[valid, malformed]), patch.object(
                                      agent_loop, "TOOL_FUNCTIONS", {"dangerous": tool}):
                    agent_loop.run_turn(messages, "question", model_name="test-model",
                                        emit=lambda kind, text: events.append((kind, text)))
                tool.assert_not_called()
                self.assertEqual(messages[-1], {"role": "user", "content": "question"})
                self.assertTrue(any(kind == "status" and "invalid" in text.lower()
                                    for kind, text in events))

    def test_stop_finish_reason_discards_tool_fragments(self):
        tool = Mock()
        messages = agent_loop.new_messages()
        events = []
        with patch.object(agent_loop.client.chat.completions, "create", return_value=[
            tool_chunk(index=0, call_id="id", name="dangerous", arguments="{}",
                       finish_reason="stop"),
        ]), patch.object(agent_loop, "TOOL_FUNCTIONS", {"dangerous": tool}):
            agent_loop.run_turn(messages, "question", model_name="test-model",
                                emit=lambda kind, text: events.append((kind, text)))
        tool.assert_not_called()
        self.assertEqual(messages[-1], {"role": "user", "content": "question"})
        self.assertTrue(any(kind == "status" for kind, _ in events))

    def test_discovery_failure_preserves_question(self):
        messages = agent_loop.new_messages()
        events = []
        with patch.object(agent_loop, "get_model_name", side_effect=RuntimeError("offline")):
            agent_loop.run_turn(messages, "question", emit=lambda kind, text: events.append((kind, text)))
        self.assertEqual(messages[-1], {"role": "user", "content": "question"})
        self.assertTrue(any(kind == "status" and "offline" in text for kind, text in events))

    def test_empty_choice_chunk_is_ignored(self):
        messages = agent_loop.new_messages()
        with patch.object(agent_loop.client.chat.completions, "create", return_value=[
            SimpleNamespace(choices=[]), text_chunk("Answer")
        ]):
            agent_loop.run_turn(messages, "question", model_name="test-model")
        self.assertEqual(messages[-1], {"role": "assistant", "content": "Answer"})

    def test_request_budget_drops_oversized_prior_tool_turn(self):
        messages = agent_loop.new_messages() + [
            {"role": "user", "content": "old"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "id", "type": "function",
                "function": {"name": "echo", "arguments": "{}"}}]},
            {"role": "tool", "tool_call_id": "id", "content": "x" * 200_000},
            {"role": "assistant", "content": "old reply"},
        ]
        with patch.object(agent_loop.client.chat.completions, "create",
                          return_value=[text_chunk("Answer")]) as create:
            agent_loop.run_turn(messages, "current question", model_name="test-model")
        sent = create.call_args.kwargs["messages"]
        self.assertEqual([m["role"] for m in sent], ["system", "user"])
        self.assertEqual(sent[-1]["content"], "current question")
        self.assertLess(len(str(sent)), agent_loop.MAX_CONTEXT_CHARS)

    def test_oversized_current_question_reports_status_without_request(self):
        messages = agent_loop.new_messages()
        events = []
        with patch.object(agent_loop, "MAX_CONTEXT_CHARS", 100), patch.object(
            agent_loop.client.chat.completions, "create") as create:
            agent_loop.run_turn(messages, "x" * 200, model_name="test-model",
                                emit=lambda kind, text: events.append((kind, text)))
        create.assert_not_called()
        self.assertEqual(messages[-1]["content"], "x" * 200)
        self.assertTrue(any(kind == "status" and "context" in text.lower()
                            for kind, text in events))

    def test_oversized_current_tool_round_truncates_result_and_continues(self):
        messages = agent_loop.new_messages()
        requests = []
        streams = iter([
            [tool_chunk(index=0, call_id="id", name="echo", arguments="{}")],
            [text_chunk("done")],
        ])
        def respond(**kwargs):
            requests.append(copy.deepcopy(kwargs["messages"]))
            return next(streams)
        with patch.object(agent_loop, "MAX_CONTEXT_CHARS", 1000), patch.object(
            agent_loop.client.chat.completions, "create", side_effect=respond
        ), patch.object(agent_loop, "TOOL_FUNCTIONS", {"echo": lambda: "x" * 2000}):
            agent_loop.run_turn(messages, "question", model_name="test-model")
        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[1][-1]["tool_call_id"], "id")
        self.assertIn("TRUNCATED", requests[1][-1]["content"])
        self.assertLessEqual(len(str(requests[1])), 1000)

    def test_file_at_read_limit_still_returns_result_to_model(self):
        from tools import file_tools

        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "large.txt").write_text("x" * file_tools.MAX_FILE_SIZE_BYTES)
            messages = agent_loop.new_messages()
            requests = []
            streams = iter([
                [tool_chunk(index=0, call_id="read-1", name="read_file",
                            arguments='{"file_path":"large.txt"}')],
                [text_chunk("Read complete")],
            ])
            def respond(**kwargs):
                requests.append(copy.deepcopy(kwargs["messages"]))
                return next(streams)
            with patch.object(file_tools, "ALLOWED_DIR", Path(directory)), patch.object(
                agent_loop, "TOOL_FUNCTIONS", {"read_file": file_tools.read_file}
            ), patch.object(agent_loop.client.chat.completions, "create", side_effect=respond):
                agent_loop.run_turn(messages, "read the file", model_name="test-model")
        self.assertEqual(len(requests), 2)
        result = requests[1][-1]
        self.assertEqual(result["tool_call_id"], "read-1")
        self.assertIn("TRUNCATED", result["content"])
        self.assertLessEqual(len(str(requests[1])), agent_loop.MAX_CONTEXT_CHARS)

    def test_multiple_large_tool_results_keep_every_call_pair(self):
        messages = agent_loop.new_messages()
        requests = []
        streams = iter([
            [tool_chunk(index=i, call_id=f"id-{i}", name="large", arguments="{}",
                        finish_reason="tool_calls" if i == 2 else None)
             for i in range(3)],
            [text_chunk("done")],
        ])
        def respond(**kwargs):
            requests.append(copy.deepcopy(kwargs["messages"]))
            return next(streams)
        with patch.object(agent_loop, "MAX_CONTEXT_CHARS", 5000), patch.object(
            agent_loop, "TOOL_FUNCTIONS", {"large": lambda: "x" * 4000}
        ), patch.object(agent_loop.client.chat.completions, "create", side_effect=respond):
            agent_loop.run_turn(messages, "question", model_name="test-model")
        self.assertEqual(len(requests), 2)
        self.assertEqual([m["tool_call_id"] for m in requests[1] if m["role"] == "tool"],
                         ["id-0", "id-1", "id-2"])
        self.assertLessEqual(len(str(requests[1])), 5000)

    def run_one_turn(self, streams, tool_functions=None, max_tool_rounds=5, approve=None):
        requests = []
        stream_iterator = iter(streams)

        def create_completion(*args, **kwargs):
            # loop.py keeps mutating messages after each completion.
            # Save an independent snapshot for assertions.
            requests.append(copy.deepcopy(kwargs["messages"]))
            return next(stream_iterator)

        with (
            patch.object(
                agent_loop.client.chat.completions,
                "create",
                side_effect=create_completion,
            ),
            patch.object(
                agent_loop,
                "TOOL_FUNCTIONS",
                tool_functions or {},
            ),
            patch.object(
                agent_loop,
                "MAX_TOOL_ROUNDS",
                max_tool_rounds,
            ),
        ):
            agent_loop.run_turn(
                agent_loop.new_messages(),
                "test request",
                model_name="test-model",
                approve=approve,
            )

        return requests

    def test_normal_response_ends_without_tool_result(self):
        requests = self.run_one_turn(
            streams=[
                [text_chunk("Normal answer")],
            ]
        )

        self.assertEqual(len(requests), 1)

        first_request_messages = requests[0]

        self.assertEqual(
            first_request_messages[-1],
            {
                "role": "user",
                "content": "test request",
            },
        )

        self.assertFalse(
            any(
                message["role"] == "tool"
                for message in first_request_messages
            )
        )

    def test_reasoning_streams_to_ui_but_not_history(self):
        chunks = [
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(
                content=None, tool_calls=None, reasoning_content="Let me ",
            ))]),
            SimpleNamespace(choices=[SimpleNamespace(delta=SimpleNamespace(
                content=None, tool_calls=None, reasoning="think.",
            ))]),
            text_chunk("Answer"),
        ]
        emitted = []
        messages = agent_loop.new_messages()
        with patch.object(agent_loop.client.chat.completions, "create", return_value=chunks):
            agent_loop.run_turn(messages, "question", model_name="test-model",
                                emit=lambda kind, value: emitted.append((kind, value)))
        self.assertEqual(emitted, [("thinking", "Let me "),
                                   ("thinking", "think."), ("assistant", "Answer")])
        self.assertEqual(messages[-1]["content"], "Answer")
        self.assertNotIn("think", str(messages))

    def test_reassembles_tool_arguments_and_sends_result(self):
        requests = self.run_one_turn(
            streams=[
                [
                    tool_chunk(
                        index=0,
                        call_id="call_1",
                        name="echo",
                        arguments='{"text":"hel',
                        finish_reason=None,
                    ),
                    tool_chunk(
                        index=0,
                        call_id=None,
                        name=None,
                        arguments='lo"}',
                    ),
                ],
                [text_chunk("Done")],
            ],
            tool_functions={
                "echo": lambda text: f"echo: {text}",
            },
        )

        self.assertEqual(len(requests), 2)

        second_request_messages = requests[1]
        assistant_tool_message = second_request_messages[-2]
        tool_result_message = second_request_messages[-1]

        self.assertEqual(assistant_tool_message["role"], "assistant")
        self.assertEqual(
            assistant_tool_message["tool_calls"][0]["function"]["name"],
            "echo",
        )
        self.assertEqual(
            assistant_tool_message["tool_calls"][0]["function"]["arguments"],
            '{"text":"hello"}',
        )

        self.assertEqual(tool_result_message["role"], "tool")
        self.assertEqual(tool_result_message["tool_call_id"], "call_1")
        self.assertEqual(tool_result_message["content"], "echo: hello")

    def test_unknown_tool_returns_error_without_execution(self):
        allowed_tool = Mock(return_value="this must not run")

        requests = self.run_one_turn(
            streams=[
                [
                    tool_chunk(
                        index=0,
                        call_id="call_unknown",
                        name="not_allowed",
                        arguments="{}",
                    ),
                ],
                [text_chunk("Done")],
            ],
            tool_functions={
                "allowed_tool": allowed_tool,
            },
        )

        allowed_tool.assert_not_called()

        second_request_messages = requests[1]
        tool_result_message = second_request_messages[-1]

        self.assertEqual(tool_result_message["role"], "tool")
        self.assertEqual(tool_result_message["tool_call_id"], "call_unknown")
        self.assertIn("not_allowed", tool_result_message["content"])
        self.assertIn("not allowed", tool_result_message["content"])

    def test_invalid_tool_json_returns_error_without_execution(self):
        safe_tool = Mock(return_value="this must not run")

        requests = self.run_one_turn(
            streams=[
                [
                    tool_chunk(
                        index=0,
                        call_id="call_bad_json",
                        name="safe_tool",
                        arguments='{"broken":',
                    ),
                ],
                [text_chunk("Done")],
            ],
            tool_functions={
                "safe_tool": safe_tool,
            },
        )

        safe_tool.assert_not_called()

        second_request_messages = requests[1]
        tool_result_message = second_request_messages[-1]

        self.assertEqual(tool_result_message["role"], "tool")
        self.assertEqual(tool_result_message["tool_call_id"], "call_bad_json")
        self.assertIn("not valid JSON", tool_result_message["content"])

    def test_denied_delete_is_returned_to_model(self):
        from tools import file_tools

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "protected.txt"
            target.write_text("keep", encoding="utf-8")
            with patch.object(file_tools, "ALLOWED_DIR", Path(directory)):
                requests = self.run_one_turn(
                    streams=[
                        [tool_chunk(index=0, call_id="delete_1", name="delete_file",
                                    arguments='{"file_path":"protected.txt"}')],
                        [text_chunk("Denied")],
                    ],
                    tool_functions={"delete_file": file_tools.delete_file},
                )
            self.assertTrue(target.exists())
        self.assertEqual(requests[1][-1]["tool_call_id"], "delete_1")
        self.assertIn("denied", requests[1][-1]["content"])

    def test_approved_memory_creation_writes_and_returns_result(self):
        from memory import memory as store
        from tools import TOOL_FUNCTIONS

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memories.json"
            with patch.object(store, "MEMORY_FILE", path):
                requests = self.run_one_turn(
                    streams=[
                        [tool_chunk(index=0, call_id="memory_1", name="create_memory",
                                    arguments='{"key":"name","value":"Jerney"}')],
                        [text_chunk("Remembered")],
                    ],
                    tool_functions={"create_memory": TOOL_FUNCTIONS["create_memory"]},
                    approve=lambda _: True,
                )
                self.assertEqual(store.get_memory("name"), "Jerney")
        self.assertEqual(requests[1][-1]["tool_call_id"], "memory_1")
        self.assertIn("created", requests[1][-1]["content"].lower())

    def test_memory_creation_does_not_request_approval(self):
        from memory import memory as store
        from tools import TOOL_FUNCTIONS

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memories.json"
            approvals = []
            with patch.object(store, "MEMORY_FILE", path):
                requests = self.run_one_turn(
                    streams=[
                        [tool_chunk(index=0, call_id="memory_create", name="create_memory",
                                    arguments='{"key":"name","value":"Jerney"}')],
                        [text_chunk("Remembered")],
                    ],
                    tool_functions={"create_memory": TOOL_FUNCTIONS["create_memory"]},
                    approve=lambda description: approvals.append(description) or False,
                )
                self.assertEqual(store.get_memory("name"), "Jerney")
        self.assertEqual(approvals, [])
        self.assertEqual(requests[1][-1]["tool_call_id"], "memory_create")
        self.assertIn("created", requests[1][-1]["content"].lower())

    def test_memory_updates_are_automatic_but_deletes_need_approval(self):
        from memory import memory as store
        from tools import TOOL_FUNCTIONS

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memories.json"
            with patch.object(store, "MEMORY_FILE", path):
                path.write_text('{"name":"Jerney"}', encoding="utf-8")
                for name, arguments, approved, expected in (
                    ("update_memory", '{"key":"name","value":"Jernej"}', False, "Jernej"),
                    ("delete_memory", '{"key":"name"}', False, "Jernej"),
                    ("delete_memory", '{"key":"name"}', True, None),
                ):
                    with self.subTest(name=name, approved=approved):
                        approvals = []
                        requests = self.run_one_turn(
                            streams=[
                                [tool_chunk(index=0, call_id="memory_action", name=name,
                                            arguments=arguments)],
                                [text_chunk("Done")],
                            ],
                            tool_functions={name: TOOL_FUNCTIONS[name]},
                            approve=lambda description, decision=approved: approvals.append(description) or decision,
                        )
                        self.assertEqual(store.get_memory("name"), expected)
                        self.assertEqual(requests[1][-1]["tool_call_id"], "memory_action")
                        self.assertEqual(len(approvals), 0 if name == "update_memory" else 1)

    def test_memory_tool_schema_does_not_advertise_runtime_arguments(self):
        from tools import TOOLS

        for schema in TOOLS:
            if schema["function"]["name"] in ("create_memory", "update_memory", "delete_memory"):
                with self.subTest(tool=schema["function"]["name"]):
                    properties = schema["function"]["parameters"]["properties"]
                    self.assertNotIn("approve", properties)
                    self.assertNotIn("model_name", properties)

    def test_tool_round_limit_prevents_next_execution(self):
        echo = Mock(return_value="ok")

        requests = self.run_one_turn(
            streams=[
                [
                    tool_chunk(
                        index=0,
                        call_id="call_1",
                        name="echo",
                        arguments="{}",
                    ),
                ],
                [
                    tool_chunk(
                        index=0,
                        call_id="call_2",
                        name="echo",
                        arguments="{}",
                    ),
                ],
                [
                    tool_chunk(
                        index=0,
                        call_id="call_3",
                        name="echo",
                        arguments="{}",
                    ),
                ],
            ],
            tool_functions={
                "echo": echo,
            },
            max_tool_rounds=2,
        )

        # The third model request happens, but its requested tool must not run.
        self.assertEqual(len(requests), 3)
        self.assertEqual(echo.call_count, 2)

        third_request_messages = requests[2]
        previous_tool_result = third_request_messages[-1]

        self.assertEqual(previous_tool_result["role"], "tool")
        self.assertEqual(previous_tool_result["tool_call_id"], "call_2")
        self.assertEqual(previous_tool_result["content"], "ok")

    def test_tool_result_uses_original_call_id(self):
        requests = self.run_one_turn(
            streams=[
                [
                    tool_chunk(
                        index=0,
                        call_id="original_id",
                        name="status",
                        arguments="{}",
                    ),
                ],
                [text_chunk("Done")],
            ],
            tool_functions={
                "status": lambda: "healthy",
            },
        )

        self.assertEqual(len(requests), 2)

        second_request_messages = requests[1]
        tool_result_message = second_request_messages[-1]

        self.assertEqual(tool_result_message["role"], "tool")
        self.assertEqual(tool_result_message["tool_call_id"], "original_id")
        self.assertEqual(tool_result_message["content"], "healthy")

    def test_reasoning_limit_keeps_prior_conversation_and_marks_turn_incomplete(self):
        messages = agent_loop.new_messages() + [
            {"role": "user", "content": "My name is Jernej"},
            {"role": "assistant", "content": "Got it"},
        ]
        events = []
        reasoning_chunk = SimpleNamespace(choices=[SimpleNamespace(
            delta=SimpleNamespace(content=None, tool_calls=None, reasoning="thinking"),
            finish_reason="length",
        )])
        with patch.object(agent_loop.client.chat.completions, "create",
                          return_value=[reasoning_chunk]) as create:
            agent_loop.run_turn(messages, "What is my name?", model_name="test-model",
                                emit=lambda kind, value: events.append((kind, value)))
        self.assertEqual(create.call_count, 1)
        self.assertEqual(create.call_args.kwargs["max_tokens"], agent_loop.MAX_TOKENS)
        self.assertEqual(messages[-3:], [
            {"role": "user", "content": "My name is Jernej"},
            {"role": "assistant", "content": "Got it"},
            {"role": "user", "content": "What is my name?"},
        ])
        self.assertTrue(any(kind == "status" and "truncat" in text.lower()
                            for kind, text in events))

        # A later turn must still receive the earlier conversation and the failed question.
        sent = []
        def respond(**kwargs):
            sent.extend(copy.deepcopy(kwargs["messages"]))
            return [text_chunk("Your name is Jernej")]
        with patch.object(agent_loop.client.chat.completions, "create", side_effect=respond):
            agent_loop.run_turn(messages, "Try again", model_name="test-model")
        self.assertEqual(sent[-4:], [
            {"role": "user", "content": "My name is Jernej"},
            {"role": "assistant", "content": "Got it"},
            {"role": "user", "content": "What is my name?"},
            {"role": "user", "content": "Try again"},
        ])

    def test_truncated_tool_call_is_never_executed(self):
        tool = Mock(return_value="ran")
        messages = agent_loop.new_messages()
        events = []
        with patch.object(agent_loop.client.chat.completions, "create", return_value=[
            tool_chunk(index=0, call_id="call_1", name="dangerous",
                       arguments="{}", finish_reason="length"),
        ]), patch.object(agent_loop, "TOOL_FUNCTIONS", {"dangerous": tool}):
            agent_loop.run_turn(messages, "question", model_name="test-model",
                                emit=lambda kind, value: events.append((kind, value)))
        tool.assert_not_called()
        self.assertEqual(messages[-1], {"role": "user", "content": "question"})
        self.assertTrue(any(kind == "status" and "truncat" in text.lower()
                            for kind, text in events))

    def test_empty_reasoning_response_is_not_a_successful_answer(self):
        messages = agent_loop.new_messages()
        events = []
        chunk = SimpleNamespace(choices=[SimpleNamespace(
            delta=SimpleNamespace(content=None, tool_calls=None, reasoning="thinking"),
            finish_reason="stop",
        )])
        with patch.object(agent_loop.client.chat.completions, "create", return_value=[chunk]):
            agent_loop.run_turn(messages, "question", model_name="test-model",
                                emit=lambda kind, value: events.append((kind, value)))
        self.assertEqual(messages[-1], {"role": "user", "content": "question"})
        self.assertTrue(any(kind == "status" and "no answer" in text.lower()
                            for kind, text in events))

if __name__ == "__main__":
    unittest.main()