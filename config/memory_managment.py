def trim_with_summary(client, model: str, messages: list, max_messages: int = 15, batch_size: int = 5) -> list:
    """Summarizes the oldest messages into a running summary when chat gets too long."""
    
    # 1. Do nothing if the chat is still short
    if len(messages) <= max_messages:
        return messages

    system_prompt = messages[0]

    # 2. Check if index 1 is already an existing summary from earlier
    if len(messages) > 1 and messages[1].get("is_summary"):
        old_summary = messages[1]["content"]
        chat_history = messages[2:]  # Skip system prompt and old summary
    else:
        old_summary = ""
        chat_history = messages[1:]  # Skip only system prompt

    # 3. Cut out the oldest batch (5 messages) to summarize, keep the rest
    to_summarize = chat_history[:batch_size]
    to_keep = chat_history[batch_size:]

    # SAFEGUARD: If 'to_keep' starts with a tool result, move it into 'to_summarize' 
    # so we don't leave a tool response without its question
    while to_keep and to_keep[0].get("role") == "tool":
        to_summarize.append(to_keep.pop(0))

    # 4. Convert those messages into simple text the model can read
    chat_text = ""
    for msg in to_summarize:
        if msg.get("content"):
            chat_text += f"{msg['role']}: {msg['content']}\n"

    # If there was no text (e.g. only tool data), skip summarization
    if not chat_text.strip():
        return messages

    console.print("\n[dim yellow]Summarizing oldest messages into memory...[/dim yellow]")

    # 5. Ask the local model to update or create the summary
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
            max_tokens=300
        )
        summary_text = response.choices[0].message.content.strip()
    except Exception as e:
        console.print(f"[dim red]Summary failed ({e}), using fallback.[/dim red]")
        summary_text = old_summary or "Older conversation was trimmed."

    # 6. Put everything back together: System + Pinned Summary + Kept Messages
    summary_message = {
        "role": "system",
        "content": f"--- CONVERSATION SUMMARY ---\n{summary_text}",
        "is_summary": True  # Tag so we can find it next time
    }

    return [system_prompt, summary_message] + to_keep