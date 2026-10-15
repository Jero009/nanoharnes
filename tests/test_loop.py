import copy
import sys
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
    def run_one_turn(self, streams, tool_functions=None, max_tool_rounds=5):
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
            patch.object(
                agent_loop.console,
                "input",
                side_effect=["test request", KeyboardInterrupt()],
            ),
            patch.object(agent_loop.console, "print"),
        ):
            with self.assertRaises(KeyboardInterrupt):
                agent_loop.loop()

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