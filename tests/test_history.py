import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from context.history import trim_history

class HistoryTests(unittest.TestCase):
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

if __name__ == "__main__":
    unittest.main()