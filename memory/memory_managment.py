from rich.console import Console

console = Console()


def _drop_incomplete_prefix(messages: list) -> list:
    """Remove leading tool messages or incomplete tool-call groups."""
    while messages:
        first = messages[0]
        if first.get("role") == "tool":
            messages.pop(0)
            continue

        if first.get("role") == "assistant":
            tool_calls = first.get("tool_calls")
        else:
            tool_calls = None
        if not tool_calls:
            break

        call_ids = {call.get("id") for call in tool_calls}
        result_ids = set()
        for message in messages[1:]:
            if message.get("role") != "tool":
                break
            result_ids.add(message.get("tool_call_id"))
        if call_ids.issubset(result_ids):
            break
        messages.pop(0)
    return messages


def trim_to_window(messages: list, max_messages: int = 15) -> list:
    """Keeps the system prompt and the most recent max_messages safely."""
    if len(messages) <= max_messages:
        return messages

    system_prompt = messages[0]
    tail = messages[-(max_messages - 1):]

    # SAFEGUARD: Never start the tail with a naked tool response or unfulfilled tool call
    tail = _drop_incomplete_prefix(tail)

    return [system_prompt] + tail


def trim_with_summary(client, model: str, messages: list, max_messages: int = 15, batch_size: int = 5) -> list:
    """Summarizes the oldest messages into a running summary when chat gets too long."""
    if len(messages) <= max_messages:
        return messages

    system_prompt = messages[0]

    # Check if index 1 is already an existing summary from earlier
    if len(messages) > 1 and messages[1].get("is_summary"):
        old_summary = messages[1]["content"]
        chat_history = messages[2:]
    else:
        old_summary = ""
        chat_history = messages[1:]

    # Cut out the oldest batch (5 messages) to summarize, keep the rest
    to_summarize = chat_history[:batch_size]
    to_keep = chat_history[batch_size:]

    # SAFEGUARD: Keep tool results paired with their caller
    while to_keep and to_keep[0].get("role") == "tool":
        to_summarize.append(to_keep.pop(0))
    if to_summarize and to_summarize[-1].get("tool_calls"):
        while to_keep and to_keep[0].get("role") == "tool":
            to_summarize.append(to_keep.pop(0))
    to_keep = _drop_incomplete_prefix(to_keep)

    # Convert messages into readable text for the model
    chat_text = ""
    for msg in to_summarize:
        if msg.get("content"):
            chat_text += f"{msg['role']}: {msg['content']}\n"

    if not chat_text.strip():
        return messages

    console.print("\n[dim yellow]Summarizing oldest messages into memory...[/dim yellow]")

    prompt = (
        f"PREVIOUS SUMMARY:\n{old_summary}\n\n"
        f"NEW MESSAGES TO ADD:\n{chat_text}\n\n"
        "Provide a concise, bullet-point summary of the key facts, decisions, and files discussed."
    )

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=300,
        )
        summary_text = response.choices[0].message.content.strip()
    except Exception as e:
        console.print(f"[dim red]Summary failed ({e}), using fallback.[/dim red]")
        summary_text = old_summary or "Older conversation was trimmed."

    summary_message = {
        "role": "system",
        "content": f"--- CONVERSATION SUMMARY ---\n{summary_text}",
        "is_summary": True,
    }

    return [system_prompt, summary_message] + to_keep