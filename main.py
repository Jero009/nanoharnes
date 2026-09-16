# 1. IMPORTS
import json
import time
import typer
from openai import OpenAI
from rich.console import Console
from pathlib import Path

from skills import ALL_TOOLS, TOOL_MAP, set_yolo_mode
from memory.memory_managment import trim_to_window, trim_with_summary #memory managment functions
from config import API_KEY, BASE_URL, MAX_MEMORY_CHARS

config_dir = Path(__file__).parent / "config"
memory_file = Path(__file__).parent / "memory" / "core_memory.md"

app = typer.Typer()
console = Console()

def build_system_prompt() -> str:
    """Combines system rules, user persona, and persistent core memory with capacity stats."""
    # 1. System rules
    system_md_path = config_dir / "system.md"
    system_rules = (
        system_md_path.read_text(encoding="utf-8").strip()
        if system_md_path.exists()
        else "You are a helpful AI assistant equipped with tools."
    )

    # 2. User persona
    agent_md_path = config_dir / "agent.md"
    user_persona = (
        agent_md_path.read_text(encoding="utf-8").strip()
        if agent_md_path.exists()
        else "You are a helpful and precise assistant."
    )

    # 3. Core memory
    core_mem = ""
    if memory_file.exists():
        core_mem = memory_file.read_text(encoding="utf-8").strip()
    if not core_mem:
        core_mem = "- No saved memories yet."

    # Hermes-style capacity calculation
    char_count = len(core_mem)
    pct = min(100, int((char_count / MAX_MEMORY_CHARS) * 100))
    memory_header = f"### PERMANENT CORE MEMORY [{pct}% — {char_count}/{MAX_MEMORY_CHARS:,} chars]:"

    # Clean, readable multi-line layout with proper Markdown spacing
    return f"""{system_rules}
            ---
            ### USER INSTRUCTIONS & PERSONA:
            {user_persona}
            ---
            {memory_header}
            {core_mem}
            """.strip()



BANNER = r"""
[bold cyan]
  _  _   _   _  _  ___     _   ___ ___ _  _ _____ 
 | \| | /_\ | \| |/ _ \   /_\ / __| __| \| |_   _|
 | .` |/ _ \| .` | (_) | / _ \ (_ | _|| .` | | |  
 |_|\_/_/ \_\_|\_|\___/ /_/ \_\___|___|_|\_| |_|  
[/bold cyan]
[dim]           Local Agent Harness           [/dim]
"""


@app.command()
def chat():
    console.clear()
    console.print(BANNER)
    try:
    # Connect to LM Studio via standard OpenAI client base_url
        client = OpenAI(base_url=BASE_URL, api_key=API_KEY)  # Use the imported API key

        # Fetch whatever model is currently loaded in LM Studio
        models_response = client.models.list()

        model_name = models_response.data[0].id
        if models_response.data is not None and len(models_response.data) > 0:
            model_name = models_response.data[0].id
        else:
            model_name = "local-model"

        console.print(f"[bold green]Connected to client[/bold green]")
        console.print(f"(Active Model: {model_name})\n")
    except Exception as e:
        console.print(f"[red]Error connecting to server:[/red] {e}")
        return
    messages = [{"role": "system", "content": build_system_prompt()}] # initialize chat messages history
    yolo_mode = False  # Track YOLO state locally
    reasoning_mode = True  # Track reasoning display state locally
    smart_memory_mode = False  # Track memory mode locally

    while True: # main chat loop

        try:
            console.print(f"[dim]Message count: {len(messages)}[/dim]")
            user_input = typer.prompt("User").strip() # user input prompt
            
        except (KeyboardInterrupt, typer.Abort):
            console.print("\n\nbye :)", style="cyan")
            break

        if not user_input: # skip loop if user input is empty
            continue    

        elif user_input.startswith("/"): # Check for commands
            cmd = user_input.lower()
            if cmd == "/bye":
                console.print("bye :)", style="cyan")
                break
            elif cmd == "/new":
                console.clear()
                console.print(BANNER)
                messages = [{"role": "system", "content": build_system_prompt()}] # reset messages history for new chat
                console.print("[dim]Started a new chat session.[/dim]\n")
            elif cmd == "/yolo":
                yolo_mode = not yolo_mode
                set_yolo_mode(yolo_mode)  # Update globally across all file/dir skills
                
                if yolo_mode:
                    console.print("[bold red]---YOLO MODE ENABLED---[/bold red]\n")
                else:
                    console.print("[bold yellow]---YOLO MODE DISABLED---[/bold yellow]\n")
            elif cmd == "/reasoning":
                console.print("[dim]Toggling display of reasoning content.[/dim]\n")
                reasoning_mode = not reasoning_mode
            elif cmd == "/memory":
                smart_memory_mode = not smart_memory_mode
                if smart_memory_mode:
                    console.print("[bold green]Memory Mode: SMART SUMMARY (Summarizes old context)[/bold green]\n")
                else:
                    console.print("[bold yellow]Memory Mode: FAST TRIM (Drops older turns instantly)[/bold yellow]\n")
            elif cmd == "/help":
                console.print("[bold cyan]Available Commands:[/bold cyan]")
                console.print("/bye   - Exit the chat")
                console.print("/new   - Start a new chat")
                console.print("/yolo  - Toggle auto-approval for destructive actions")
                console.print("/reasoning - Toggle display of reasoning content")
                console.print("/memory - Toggle memory mode (Fast Trim vs Smart Summary)")
                console.print("/help  - Show this help message\n")

            else:
                console.print(f"[red]Unknown command: {user_input} | try /help[/red]\n")

        else:
            # Check actual message length and trim if it exceeds 15
            if len(messages) > 15:
                if smart_memory_mode:
                    messages = trim_with_summary(client, model_name, messages, max_messages=15, batch_size=5)
                else:
                    messages = trim_to_window(messages, max_messages=15)

            messages.append({"role": "user", "content": user_input})
            console.print("[bold blue]Agent:[/bold blue]\n", end="")
            start = time.time()

            try:
                last_call_signature = None  # tack the last tool call signature to detect repetition loops
                while True:  # keep looping until the model responds without tool calls
                    response_stream = client.chat.completions.create(
                        model=model_name,
                        messages=messages,
                        tools=ALL_TOOLS,
                        tool_choice="auto",
                        stream=True,
                        # --- FIXES FOR REPETITION LOOPS ---
                        temperature=0.6,          # 0.6 - 0.7 prevents rigid deterministic loops
                        presence_penalty=0.3,     # Penalizes words the model has already used
                        frequency_penalty=0.3,    # Discourages repeating the exact same phrases
                        max_tokens=2048           # HARD CAP: stops it from streaming indefinitely
                    )

                    full_content = ""
                    full_reasoning = ""
                    tool_calls_data = {}

                    thinking_started = False

                    for chunk in response_stream:
                        delta = chunk.choices[0].delta
                        reasoning = getattr(delta, "reasoning_content", None)
                        
                        if reasoning:
                            if not thinking_started:
                                if reasoning_mode:
                                    console.print("[dim italic]Thinking: \n", end="")
                                else:
                                    console.print("[dim italic]Thinking...[/dim italic]\n", end="")
                                    console.print("\n", end="")
                                thinking_started = True

                            if reasoning_mode:
                                console.print(reasoning, style="dim italic", end="")

                            full_reasoning += reasoning


                        if delta.content:
                            console.print(delta.content, style="bold cyan", end="")
                            full_content += delta.content

                        if delta.tool_calls:
                            for tc in delta.tool_calls:
                                index = tc.index
                                if index not in tool_calls_data:
                                    tool_calls_data[index] = {
                                        "id": tc.id or "",
                                        "name": tc.function.name or "",
                                        "arguments": tc.function.arguments or ""
                                    }
                                else:
                                    if tc.function.name:
                                        tool_calls_data[index]["name"] += tc.function.name
                                    if tc.function.arguments:
                                        tool_calls_data[index]["arguments"] += tc.function.arguments

                    console.print()

                    if tool_calls_data:
                        formatted_tool_calls = [
                            {
                                "id": tc["id"],
                                "type": "function",
                                "function": {"name": tc["name"], "arguments": tc["arguments"]}
                            }
                            for tc in tool_calls_data.values()
                        ]
                    else:
                        formatted_tool_calls = None

                    assistant_content = full_content
                    if not assistant_content:
                        assistant_content = None

                    messages.append({
                        "role": "assistant",
                        "content": assistant_content,
                        #debationg if i shuld include reasoning content in the message history or not
                        "tool_calls": formatted_tool_calls
                    })

                    if not formatted_tool_calls:
                        break  # model gave a final answer with no tool calls — stop looping

                    for tool_call in formatted_tool_calls:
                        func_name = tool_call["function"]["name"]
                        try:
                            func_args = json.loads(tool_call["function"]["arguments"])
                        except (TypeError, json.JSONDecodeError) as error:
                            tool_result = f"Error: Invalid tool arguments ({error})."
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tool_call["id"],
                                "content": tool_result,
                            })
                            continue

                        call_signature = f"{func_name}:{json.dumps(func_args, sort_keys=True)}"

                        if call_signature == last_call_signature:  # atemts to stop model spiraling
                            console.print(f"\n[bold yellow]Loop detected: Repeated call to '{func_name}'. Intercepting...[/bold yellow]")
                            tool_result = (
                                f"Error: You called '{func_name}' with identical arguments on the previous turn. "
                                "This action has already succeeded. Do NOT repeat it. "
                                "Proceed to the next task or give your final answer to the user."
                            )
                        else:
                            last_call_signature = call_signature
                            console.print(f"\n[dim italic]Executing tool: {func_name}({func_args})[/dim italic]")

                            if func_name in TOOL_MAP:
                                try:
                                    tool_result = TOOL_MAP[func_name](**func_args)
                                    if func_name == "save_memory":
                                        messages[0]["content"] = build_system_prompt() # refreshes the memory mid convo

                                except Exception as tool_err:
                                    tool_result = f"Error executing tool: {tool_err}"
                            else:
                                tool_result = f"Error: Tool {func_name} not found."
                        console.print(f"[dim italic]Result: {tool_result}[/dim italic]\n")

                        messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": str(tool_result)
                        })
                    # loop again — model gets to see the tool results and respond

            except Exception as e:
                console.print(f"\n[red]Execution error:[/red] {e}")

            elapsed = time.time() - start
            console.print(f"\n[dim]Response time: {elapsed:.2f} seconds[/dim]\n")

# 4. ENTRYPOINT
if __name__ == "__main__":
    app()