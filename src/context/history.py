import json


def budget_history(messages: list[dict], max_chars: int) -> list[dict] | None:
    """Select bounded complete turns, shortening tool results in the current turn if needed.

    Return None if the system message and current turn cannot fit even then.
    """
    system = messages[:1]
    turns = []
    for message in messages[1:]:
        if message["role"] == "user" or not turns:
            turns.append([])
        turns[-1].append(message)

    selected = turns[-1:] if turns else []

    def request() -> list[dict]:
        return system + [message for turn in selected for message in turn]

    def size() -> int:
        return len(json.dumps(request(), ensure_ascii=False))

    if size() > max_chars and selected:
        # A completed tool call must remain paired with its result. Shorten its
        # text in this request copy instead of dropping the current turn.
        selected[0] = [message.copy() if message["role"] == "tool" else message
                       for message in selected[0]]
        marker = "\n...[TRUNCATED: tool result shortened to fit request context]..."
        for message in selected[0]:
            if message["role"] != "tool" or not isinstance(message.get("content"), str):
                continue
            original = message["content"]
            if len(json.dumps(original, ensure_ascii=False)) <= len(json.dumps(marker, ensure_ascii=False)):
                continue
            message["content"] = marker
            if size() <= max_chars:
                # Restore as much of this result as fits, accounting for JSON escaping.
                low, high = 0, len(original)
                best = marker
                while low <= high:
                    middle = (low + high) // 2
                    message["content"] = (original[:middle] + marker
                                          if middle < len(original) else original)
                    if size() <= max_chars:
                        best = message["content"]
                        low = middle + 1
                    else:
                        high = middle - 1
                message["content"] = best
                break
    if size() > max_chars:
        return None
    for turn in reversed(turns[:-1]):
        selected.insert(0, turn)
        if size() > max_chars:
            selected.pop(0)
            break
    return request()


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