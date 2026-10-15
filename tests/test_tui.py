import asyncio
import html
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from textual.widgets import Input
from textual.containers import VerticalScroll
from tui import NanoHarness, ApprovalDialog
from tools import TOOLS


class TuiTests(unittest.TestCase):
    def test_send_stream_and_resize(self):
        def fake_turn(messages, text, *, emit, **kwargs):
            messages.append({"role": "user", "content": text})
            emit("thinking", "Checking ")
            emit("thinking", "context")
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
                    self.assertEqual(len(chat.query(".thinking")), 1)
                    self.assertIn("Checking context", str(chat.query_one(".thinking").render()))
                    self.assertEqual(chat.query_one(".thinking").styles.color.hex, "#888888")
                    self.assertEqual(chat.query_one(".user").styles.color.hex.lower(), "#add8e6")
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
                await app.screen.mount(ApprovalDialog("Delete file: /workspace/a", results.append))
                await pilot.pause()
                self.assertIsNotNone(app.query_one("#chat"))
                await pilot.press("escape")
                await pilot.pause()
                self.assertEqual(results, [False])
                self.assertEqual(len(app.query("ApprovalDialog")), 0)
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
                            if app.query("ApprovalDialog"):
                                break
                        self.assertEqual(len(app.query("ApprovalDialog")), 1)
                        await pilot.click(f"#{button_id}")
                        await app.workers.wait_for_complete()
                        await pilot.pause()
                        chat = app.query_one("#chat", VerticalScroll)
                        self.assertIn(expected, str(list(chat.children)[-1].render()))

        asyncio.run(check())

    def test_dialog_keeps_chat_visible_and_keyboard_works(self):
        async def check():
            app = NanoHarness()
            async with app.run_test(size=(100, 28)) as pilot:
                results = []
                await app.screen.mount(ApprovalDialog("Run sandboxed shell command: $ ls -la", results.append))
                await pilot.pause()
                self.assertEqual(app.focused.id, "deny")
                svg = html.unescape(app.export_screenshot()).replace("\xa0", " ")
                self.assertIn("NanoHarness is ready", svg)
                self.assertIn("Approve this action?", svg)
                await pilot.press("tab")
                self.assertEqual(app.focused.id, "approve")
                await pilot.press("tab")
                self.assertEqual(app.focused.id, "deny")
                await pilot.press("shift+tab")
                self.assertEqual(app.focused.id, "approve")
                await pilot.press("enter")
                await pilot.pause()
                self.assertEqual(results, [True])
                await pilot.resize_terminal(64, 20)
                await app.screen.mount(ApprovalDialog("Run sandboxed shell command: $ ls -la", results.append))
                await pilot.pause()
                self.assertLess(app.query_one("#approve").region.y, app.screen.region.bottom)
                narrow_svg = html.unescape(app.export_screenshot()).replace("\xa0", " ")
                self.assertIn("NanoHarness ", narrow_svg)
                self.assertIn(" Deny ", narrow_svg)
                self.assertIn(" Approve ", narrow_svg)
                await pilot.press("escape")
                self.assertEqual(results, [True, False])
        asyncio.run(check())

    def test_approval_is_not_model_visible(self):
        for tool in TOOLS:
            self.assertNotIn("approve", tool["function"]["parameters"]["properties"])


if __name__ == "__main__":
    unittest.main()
