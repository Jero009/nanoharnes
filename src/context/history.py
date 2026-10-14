def trim_history(messages: list[dict], max_turns: int) -> list[dict]:
    """Keep the system message and the newest complete user turns."""
    system_message = messages[:1]
    turns = []
    current_turn = []

    for message in messages[1:]:
        if message["role"] == "user":
            if current_turn:
                turns.append(current_turn)
            current_turn = [message]
        else:
            current_turn.append(message)

    if current_turn:
        turns.append(current_turn)

    kept_turns = turns[-max_turns:]
    return system_message + [
        message
        for turn in kept_turns
        for message in turn
    ]