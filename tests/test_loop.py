import copy
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import loop as agent_loop

def text_chunk(content: str):
    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                delta=SimpleNamespace(
                    content=content,
                    tool_calls=None,
                )
            )
        ]
    )

def tool_chunk(
    *,
    index: int,
    call_id: str | None,
    name: str | None,
    arguments: str,
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
                )
            )
        ]
    )

class LoopTests(unittest.TestCase):
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

    def test_denied_memory_creation_leaves_no_file(self):
        from memory import memory as store
        from tools import TOOL_FUNCTIONS

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memories.json"
            with patch.object(store, "MEMORY_FILE", path):
                requests = self.run_one_turn(
                    streams=[
                        [tool_chunk(index=0, call_id="memory_deny", name="create_memory",
                                    arguments='{"key":"name","value":"Jerney"}')],
                        [text_chunk("Denied")],
                    ],
                    tool_functions={"create_memory": TOOL_FUNCTIONS["create_memory"]},
                    approve=lambda _: False,
                )
                self.assertFalse(path.exists())
        self.assertEqual(requests[1][-1]["tool_call_id"], "memory_deny")
        self.assertIn("denied", requests[1][-1]["content"].lower())

    def test_memory_updates_and_deletes_use_approval(self):
        from memory import memory as store
        from tools import TOOL_FUNCTIONS

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "memories.json"
            with patch.object(store, "MEMORY_FILE", path):
                path.write_text('{"name":"Jerney"}', encoding="utf-8")
                for name, arguments, approved, expected in (
                    ("update_memory", '{"key":"name","value":"Jernej"}', False, "Jerney"),
                    ("update_memory", '{"key":"name","value":"Jernej"}', True, "Jernej"),
                    ("delete_memory", '{"key":"name"}', False, "Jernej"),
                    ("delete_memory", '{"key":"name"}', True, None),
                ):
                    with self.subTest(name=name, approved=approved):
                        requests = self.run_one_turn(
                            streams=[
                                [tool_chunk(index=0, call_id="memory_action", name=name,
                                            arguments=arguments)],
                                [text_chunk("Done")],
                            ],
                            tool_functions={name: TOOL_FUNCTIONS[name]},
                            approve=lambda _, decision=approved: decision,
                        )
                        self.assertEqual(store.get_memory("name"), expected)
                        self.assertEqual(requests[1][-1]["tool_call_id"], "memory_action")

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

if __name__ == "__main__":
    unittest.main()