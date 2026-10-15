import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from textual.widgets import Input
from textual.containers import VerticalScroll
from tui import NanoHarness, ApprovalModal
from tools import TOOLS


class TuiTests(unittest.TestCase):
    def test_send_stream_and_resize(self):
        def fake_turn(messages, text, *, emit, **kwargs):
            messages.append({"role": "user", "content": text})
            emit("assistant", "Hel")
            emit("assistant", "lo")

        async def check():
            with patch("tui.run_turn", side_effect=fake_turn) as turn:
                app = NanoHarness()
                async with app.run_test(size=(100, 28)) as pilot:
                    prompt = app.query_one("#prompt", Input)
                    prompt.focus()
                    await pilot.press(*"test", "enter")
                    await app.workers.wait_for_complete()
                    await pilot.pause()
                    chat = app.query_one("#chat", VerticalScroll)
                    self.assertIn("Hello", " ".join(str(child.render()) for child in chat.children))
                    self.assertEqual(prompt.value, "")
                    self.assertFalse(prompt.disabled)
                    self.assertEqual(turn.call_count, 1)
                    self.assertEqual(app.query_one("#bottom").region.bottom, app.screen.region.bottom)
                    await pilot.resize_terminal(64, 20)
                    self.assertEqual(app.query_one("#bottom").region.bottom, app.screen.region.bottom)
                    await pilot.press("ctrl+l")
                    self.assertEqual(len(app.messages), 1)
                    self.assertEqual(app.messages[0]["role"], "system")

        asyncio.run(check())

    def test_modal_escape_denies(self):
        async def check():
            app = NanoHarness()
            async with app.run_test() as pilot:
                results = []
                app.push_screen(ApprovalModal("Delete file: /workspace/a"), results.append)
                await pilot.pause()
                await pilot.press("escape")
                await pilot.pause()
                self.assertEqual(results, [False])
        asyncio.run(check())

    def test_worker_approval_denies_then_allows(self):
        def fake_turn(messages, text, *, approve, emit, **kwargs):
            result = approve("Delete file: /workspace/safe.txt")
            emit("status", "approved" if result else "denied")

        async def check():
            with patch("tui.run_turn", side_effect=fake_turn):
                app = NanoHarness()
                async with app.run_test() as pilot:
                    for button_id, expected in (("deny", "denied"), ("approve", "approved")):
                        prompt = app.query_one("#prompt", Input)
                        prompt.focus()
                        await pilot.press("x", "enter")
                        for _ in range(30):
                            await pilot.pause()
                            if isinstance(app.screen, ApprovalModal):
                                break
                        self.assertIsInstance(app.screen, ApprovalModal)
                        await pilot.click(f"#{button_id}")
                        await app.workers.wait_for_complete()
                        await pilot.pause()
                        chat = app.query_one("#chat", VerticalScroll)
                        self.assertIn(expected, str(list(chat.children)[-1].render()))

        asyncio.run(check())

    def test_approval_is_not_model_visible(self):
        for tool in TOOLS:
            self.assertNotIn("approve", tool["function"]["parameters"]["properties"])


if __name__ == "__main__":
    unittest.main()
