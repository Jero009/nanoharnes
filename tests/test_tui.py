import asyncio
import html
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from textual.widgets import Input
from textual.containers import VerticalScroll
with patch.dict("os.environ", {"BASE_URL": "http://127.0.0.1:1/v1", "API_KEY": "test"}):
    from tui import NanoHarness, ApprovalDialog
from tools import TOOLS


class TuiTests(unittest.TestCase):
    def test_composer_uses_enter_without_send_button_or_chat_divider(self):
        async def check():
            app = NanoHarness()
            async with app.run_test(size=(100, 28)):
                self.assertEqual(len(app.query("#send")), 0)
                self.assertFalse(app.query_one("#bottom").styles.border)
                self.assertEqual(app.query_one("#prompt", Input).region.width,
                                 app.query_one("#composer").region.width)

        asyncio.run(check())

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

    def test_yolo_skips_approval_prompts_until_disabled_or_new_chat(self):
        approvals = []

        def fake_turn(messages, text, *, approve, emit, **kwargs):
            approvals.append(approve("Delete file: /workspace/safe.txt"))
            emit("status", "approved" if approvals[-1] else "denied")

        async def check():
            with patch("tui.run_turn", side_effect=fake_turn):
                app = NanoHarness()
                async with app.run_test() as pilot:
                    prompt = app.query_one("#prompt", Input)

                    async def submit(text):
                        prompt.focus()
                        await pilot.press(*text, "enter")
                        await pilot.pause()

                    await submit("/yolo")
                    self.assertTrue(app.yolo)
                    self.assertIn("YOLO ON", str(app.query_one("#hint").render()))
                    await submit("delete something")
                    await app.workers.wait_for_complete()
                    self.assertEqual(approvals, [True])
                    self.assertEqual(len(app.query("ApprovalDialog")), 0)

                    await submit("/yolo off")
                    self.assertFalse(app.yolo)
                    await submit("delete something else")
                    for _ in range(30):
                        await pilot.pause()
                        if app.query("ApprovalDialog"):
                            break
                    self.assertEqual(len(app.query("ApprovalDialog")), 1)
                    await pilot.click("#deny")
                    await app.workers.wait_for_complete()
                    self.assertEqual(approvals, [True, False])

                    await submit("/yolo on")
                    await submit("/new")
                    self.assertFalse(app.yolo)
                    self.assertNotIn("YOLO ON", str(app.query_one("#hint").render()))
                    await submit("delete after reset")
                    for _ in range(30):
                        await pilot.pause()
                        if app.query("ApprovalDialog"):
                            break
                    self.assertEqual(len(app.query("ApprovalDialog")), 1)
                    await pilot.click("#deny")
                    await app.workers.wait_for_complete()
                    self.assertEqual(approvals, [True, False, False])
                    await submit("/yolo on")
                    await submit("/clear")
                    self.assertTrue(app.yolo)
                    await pilot.press("ctrl+l")
                    self.assertFalse(app.yolo)
                    self.assertNotIn("YOLO ON", str(app.query_one("#hint").render()))

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
                actions = app.query_one("#approval-actions").region
                deny = app.query_one("#deny")
                approve = app.query_one("#approve")
                self.assertAlmostEqual((deny.region.x + approve.region.right) / 2,
                                       (actions.x + actions.right) / 2, delta=1)
                await pilot.hover("#approve")
                await pilot.pause()
                self.assertEqual(approve.region.height, 1)
                self.assertEqual(approve.styles.background.ansi, -1)
                self.assertFalse(approve.styles.border)
                self.assertEqual(approve.styles.background_tint.a, 0)
                self.assertEqual(approve.styles.tint.a, 0)
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

    def test_slash_commands_are_local_and_clear_differs_from_new(self):
        requests = []

        def fake_turn(messages, text, **kwargs):
            requests.append((list(messages), text))

        async def check():
            with patch("tui.run_turn", side_effect=fake_turn):
                app = NanoHarness()
                async with app.run_test() as pilot:
                    prompt = app.query_one("#prompt", Input)

                    async def submit(text):
                        prompt.focus()
                        await pilot.press(*text, "enter")
                        await pilot.pause()
                        self.assertEqual(prompt.value, "")

                    app.messages.extend([{"role": "user", "content": "old"},
                                         {"role": "assistant", "content": "answer"}])
                    await submit("/help")
                    chat = app.query_one("#chat", VerticalScroll)
                    self.assertIn("/clear", str(list(chat.children)[-1].render()))
                    await submit("/unknown")
                    self.assertIn("Unknown command", str(list(chat.children)[-1].render()))
                    await submit("/clear extra")
                    self.assertIn("Unknown command", str(list(chat.children)[-1].render()))
                    await submit("/clear")
                    self.assertEqual(len(chat.children), 0)
                    self.assertEqual(len(app.messages), 3)
                    await submit("hello")
                    await app.workers.wait_for_complete()
                    self.assertEqual(len(requests), 1)
                    self.assertEqual(requests[0][1], "hello")
                    self.assertEqual(requests[0][0], app.messages)
                    await submit("/new")
                    self.assertEqual(len(chat.children), 0)
                    self.assertEqual([message["role"] for message in app.messages], ["system"])
                    with patch.object(app, "exit") as exit_app:
                        await submit("/bye")
                        exit_app.assert_called_once_with()
                    self.assertEqual(len(requests), 1)

        asyncio.run(check())


if __name__ == "__main__":
    unittest.main()
