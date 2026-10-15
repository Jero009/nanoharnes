from threading import Event

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from loop import new_messages, run_turn
BANNER = r"""[bold]
  _  _   _   _  _  ___     _   ___ ___ _  _ _____
 | \| | /_\ | \| |/ _ \   /_\ / __| __| \| |_   _|
 | .` |/ _ \| .` | (_) | / _ \ (_ | _|| .` | | |
 |_|\_/_/ \_\_|\_|\___/ /_/ \_\___|___|_\_| |_|
[/bold]
[dim]           Local Agent Harness           [/dim]"""
class NanoHarness(App):
    TITLE = "NanoHarness"
    ansi_color = True
    CSS = """
    Screen {
        background: ansi_default;
        color: ansi_default;
    }
    #banner {
        height: auto;
        padding: 1 2 0 2;
        border-bottom: solid #555555;
    }
    #chat {
        height: 1fr;
        min-height: 0;
        padding: 1 2;
        scrollbar-background: ansi_default;
        scrollbar-color: #777777;
        scrollbar-color-hover: white;
    }
    .message {
        margin-bottom: 1;
        color: ansi_default;
    }
    .user {
        text-style: bold;
        color: #add8e6;
    }
    .thinking {
        color: #888888;
        text-style: dim;
    }
    .event {
        color: #aaaaaa;
    }
    #bottom {
        dock: bottom;
        height: auto;
        padding: 0 2 1 2;
        background: ansi_default;
        border-top: solid #555555;
    }
    #composer {
        height: 3;
        margin-top: 1;
    }
    #prompt {
        width: 1fr;
        background: ansi_default;
        color: ansi_default;
        border: solid #777777;
    }
    #prompt:focus {
        border: solid white;
    }
    #send {
        width: 5;
        min-width: 5;
        height: 1;
        min-height: 1;
        margin-left: 1;
        background: ansi_default;
        color: ansi_default;
        border: none;
        text-style: bold;
    }
    #send:hover, #send:focus {
        background: ansi_default;
        color: ansi_default;
        border: solid white;
    }
    #hint {
        color: #aaaaaa;
    }
    ApprovalModal {
        align: center middle;
        background: ansi_default 70%;
    }
    #approval {
        width: 70;
        max-width: 90%;
        height: auto;
        padding: 1 2;
        background: ansi_default;
        border: solid white;
    }
    #approval-text {
        height: auto;
        margin-bottom: 1;
    }
    #approval-actions {
        height: 3;
    }
    """
    BINDINGS = [("ctrl+l", "clear_chat", "Clear chat")]

    def __init__(self):
        super().__init__()
        self.messages = new_messages()
        self.busy = False
        self.reply = None
        self.thinking = None

    def compose(self) -> ComposeResult:
        yield Static(BANNER, id="banner")
        yield VerticalScroll(
            Static("NanoHarness is ready.", classes="message"),
            Static(
                "Workspace boundary enforced. Dangerous actions require approval.",
                classes="message event",
            ),
            id="chat",
        )
        with Vertical(id="bottom"):
            with Horizontal(id="composer"):
                yield Input(placeholder="Message NanoHarness…", id="prompt")
                yield Button("↵", id="send")
            yield Static("Enter send · Ctrl+L clear chat", id="hint")
    async def send_message(self) -> None:
        if self.busy:
            return
        prompt = self.query_one("#prompt", Input)
        text = prompt.value.strip()
        if not text:
            return
        chat = self.query_one("#chat", VerticalScroll)
        await chat.mount(Static(f"You: {text}", classes="message user", markup=False))
        prompt.value = ""
        chat.scroll_end()
        self.busy = True
        prompt.disabled = True
        self.query_one("#send", Button).disabled = True
        self.reply = None
        self.thinking = None
        self.run_agent(text)

    def show_event(self, kind: str, text: str) -> None:
        chat = self.query_one("#chat", VerticalScroll)
        if kind == "thinking":
            if self.thinking is None:
                self.thinking = Static("", classes="message thinking", markup=False)
                chat.mount(self.thinking)
            self.thinking.update(str(self.thinking.render()) + text)
        elif kind == "assistant":
            if self.reply is None:
                self.reply = Static("", classes="message", markup=False)
                chat.mount(self.reply)
            self.reply.update(str(self.reply.render()) + text)
        else:
            self.reply = None
            self.thinking = None
            chat.mount(Static(f"{kind}: {text}", classes="message event", markup=False))
        chat.scroll_end()

    def request_approval(self, description: str) -> bool:
        decision = Event()
        approved = False

        def finish(result: bool | None) -> None:
            nonlocal approved
            approved = result is True
            decision.set()

        self.call_from_thread(self.push_screen, ApprovalModal(description), finish)
        if not decision.wait(300):
            return False
        return approved

    @work(thread=True, exclusive=True)
    def run_agent(self, text: str) -> None:
        try:
            run_turn(
                self.messages,
                text,
                emit=lambda kind, value: self.call_from_thread(self.show_event, kind, value),
                approve=self.request_approval,
            )
        except Exception as error:
            self.call_from_thread(self.show_event, "error", str(error))
        finally:
            self.call_from_thread(self.finish_turn)

    def finish_turn(self) -> None:
        self.busy = False
        prompt = self.query_one("#prompt", Input)
        prompt.disabled = False
        self.query_one("#send", Button).disabled = False
        prompt.focus()
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        await self.send_message()
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send":
            await self.send_message()
    async def action_clear_chat(self) -> None:
        if self.busy:
            return
        self.messages = new_messages()
        chat = self.query_one("#chat", VerticalScroll)
        for child in list(chat.children):
            await child.remove()
        await chat.mount(Static("Chat cleared.", classes="message event"))


class ApprovalModal(ModalScreen[bool]):
    BINDINGS = [("escape", "deny", "Deny")]

    def __init__(self, description: str):
        super().__init__()
        self.description = description

    def compose(self) -> ComposeResult:
        with Vertical(id="approval"):
            yield Static("Approve this action?\n" + self.description, id="approval-text", markup=False)
            with Horizontal(id="approval-actions"):
                yield Button("Deny", id="deny")
                yield Button("Approve", id="approve")

    def on_mount(self) -> None:
        self.query_one("#deny", Button).focus()

    def action_deny(self) -> None:
        self.dismiss(False)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "approve")

if __name__ == "__main__":
    NanoHarness().run()
