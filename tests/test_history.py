import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from context.history import trim_history, budget_history, trim_with_summary

class HistoryTests(unittest.TestCase):
    def test_budget_keeps_complete_recent_tool_turn_and_current_question(self):
        messages = [
            {"role": "system", "content": "rules"},
            {"role": "user", "content": "old"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "old"}]},
            {"role": "tool", "tool_call_id": "old", "content": "x" * 1000},
            {"role": "user", "content": "recent"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "new"}]},
            {"role": "tool", "tool_call_id": "new", "content": "result"},
            {"role": "user", "content": "current"},
        ]
        result = budget_history(messages, 500)
        self.assertEqual(result, messages[:1] + messages[4:])
        self.assertIsNone(budget_history(messages, 10))

    def test_budget_shortens_small_result_with_expensive_json_escaping(self):
        content = "\\" * 55
        messages = [
            {"role": "system", "content": "rules"},
            {"role": "user", "content": "question"},
            {"role": "assistant", "content": None, "tool_calls": [{"id": "call-1"}]},
            {"role": "tool", "tool_call_id": "call-1", "content": content},
        ]
        limit = len(json.dumps(messages, ensure_ascii=False)) - 1
        result = budget_history(messages, limit)
        self.assertIsNotNone(result)
        self.assertEqual(result[-1]["tool_call_id"], "call-1")
        self.assertIn("TRUNCATED", result[-1]["content"])
        self.assertLessEqual(len(json.dumps(result, ensure_ascii=False)), limit)
        self.assertEqual(messages[-1]["content"], content)

    def test_keeps_system_and_newest_turns(self):
        messages = [
            {"role": "system", "content": "system rules"},
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "first reply"},
            {"role": "user", "content": "second"},
            {"role": "assistant", "content": "second reply"},
            {"role": "user", "content": "third"},
            {"role": "assistant", "content": "third reply"},
        ]

        result = trim_history(messages, max_turns=2)

        self.assertEqual(
            result,
            [
                {"role": "system", "content": "system rules"},
                {"role": "user", "content": "second"},
                {"role": "assistant", "content": "second reply"},
                {"role": "user", "content": "third"},
                {"role": "assistant", "content": "third reply"},
            ],
        )

    def test_keeps_complete_tool_turn(self):
        messages = [
            {"role": "system", "content": "system rules"},
            {"role": "user", "content": "old question"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": "old-call"}],
            },
            {
                "role": "tool",
                "tool_call_id": "old-call",
                "content": "old result",
            },
            {"role": "assistant", "content": "old answer"},
            {"role": "user", "content": "new question"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": "new-call"}],
            },
            {
                "role": "tool",
                "tool_call_id": "new-call",
                "content": "new result",
            },
            {"role": "assistant", "content": "new answer"},
        ]

        result = trim_history(messages, max_turns=1)

        self.assertEqual(
            result,
            [
                {"role": "system", "content": "system rules"},
                {"role": "user", "content": "new question"},
                {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{"id": "new-call"}],
                },
                {
                    "role": "tool",
                    "tool_call_id": "new-call",
                    "content": "new result",
                },
                {"role": "assistant", "content": "new answer"},
            ],
        )

    def test_does_not_change_original_messages(self):
        messages = [
            {"role": "system", "content": "system rules"},
            {"role": "user", "content": "first"},
            {"role": "assistant", "content": "first reply"},
            {"role": "user", "content": "second"},
            {"role": "assistant", "content": "second reply"},
        ]
        original_messages = messages.copy()

        trim_history(messages, max_turns=1)

        self.assertEqual(messages, original_messages)

    def test_keeps_all_messages_when_under_limit(self):
        messages = [
            {"role": "system", "content": "system rules"},
            {"role": "user", "content": "question"},
            {"role": "assistant", "content": "answer"},
        ]

        result = trim_history(messages, max_turns=8)

        self.assertEqual(result, messages)

    def test_summary_keeps_complete_tool_turn_and_running_summary(self):
        client = Mock()
        client.chat.completions.create.return_value = SimpleNamespace(choices=[
            SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="A durable fact"))
        ])
        messages = [{"role": "system", "content": "rules"}]
        for index in range(7):
            messages.extend([
                {"role": "user", "content": f"ask-{index}"},
                {"role": "assistant", "content": None, "tool_calls": [{"id": f"id-{index}",
                    "type": "function", "function": {"name": "read_file", "arguments": "{}"}}]},
                {"role": "tool", "tool_call_id": f"id-{index}", "content": f"result-{index}"},
                {"role": "assistant", "content": f"answer-{index}"},
            ])
        messages.append({"role": "user", "content": "current"})
        result = trim_with_summary(client, "test-model", messages)
        self.assertEqual(result[0], messages[0])
        self.assertTrue(result[1]["is_summary"])
        self.assertIn("A durable fact", result[1]["content"])
        self.assertEqual(result[2], messages[9])  # batch ends after two full four-message turns
        self.assertEqual(result[-1], messages[-1])
        request = budget_history(result, 100_000)
        self.assertTrue(all("is_summary" not in item for item in request))
        self.assertEqual(request[1]["role"], "assistant")
        self.assertIn("UNTRUSTED", request[1]["content"])
        self.assertIn("result-0", client.chat.completions.create.call_args.kwargs["messages"][1]["content"])
        original = list(result)
        again = trim_with_summary(client, "test-model", result, max_messages=15)
        self.assertIn("A durable fact", client.chat.completions.create.call_args.kwargs["messages"][1]["content"])
        self.assertEqual(result, original)
        self.assertEqual(again[1]["content"], result[1]["content"])

    def test_summary_failure_or_truncation_preserves_history(self):
        messages = [{"role": "system", "content": "rules"}] + [
            {"role": "user" if n % 2 == 0 else "assistant", "content": str(n)}
            for n in range(18)
        ]
        client = Mock()
        client.chat.completions.create.return_value = SimpleNamespace(choices=[
            SimpleNamespace(finish_reason="length", message=SimpleNamespace(content="partial"))
        ])
        with self.assertRaises(ValueError):
            trim_with_summary(client, "test-model", messages)
        self.assertEqual(messages[-1]["content"], "17")
        self.assertEqual(len(messages), 19)

    def test_summary_does_not_call_model_under_threshold(self):
        client = Mock()
        messages = [{"role": "system", "content": "rules"}, {"role": "user", "content": "hi"}]
        self.assertIs(trim_with_summary(client, "model", messages), messages)
        client.chat.completions.create.assert_not_called()

if __name__ == "__main__":
    unittest.main()