from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import Button, Input, Static
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
    """
    BINDINGS = [("ctrl+l", "clear_chat", "Clear chat")]
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
        prompt = self.query_one("#prompt", Input)
        text = prompt.value.strip()
        if not text:
            return
        chat = self.query_one("#chat", VerticalScroll)
        await chat.mount(Static(f"You: {text}", classes="message user", markup=False))
        prompt.value = ""
        chat.scroll_end()
        prompt.focus()
    async def on_input_submitted(self, event: Input.Submitted) -> None:
        await self.send_message()
    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "send":
            await self.send_message()
    async def action_clear_chat(self) -> None:
        chat = self.query_one("#chat", VerticalScroll)
        for child in list(chat.children):
            await child.remove()
        await chat.mount(Static("Visible chat cleared.", classes="message event"))
if __name__ == "__main__":
    NanoHarness().run()
