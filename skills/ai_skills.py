import textwrap
from pathlib import Path
from openai import OpenAI
from config import API_KEY, BASE_URL
from config.sandbox import ALLOWED_DIR, check_path_allowed, MAX_FILE_SIZE_BYTES

# Dedicated client for isolated sub-tasks
client = OpenAI(base_url=BASE_URL, api_key=API_KEY)

# Cached model name to avoid repetitive HTTP calls
_CACHED_MODEL: str | None = None


def _get_active_model() -> str: #gets the avaible model
    global _CACHED_MODEL
    if _CACHED_MODEL:
        return _CACHED_MODEL

    try:
        models = client.models.list()
        if models.data:
            _CACHED_MODEL = models.data[0].id
            return _CACHED_MODEL
    except Exception:
        pass
    return "local-model"


def summarize_file(file_path: str, focus: str = "general overview and key points") -> str:
    """
    Reads a large file, analyzes it and returns a concise summary.
    Use this instead of read_file when files are long.
    """
    target_path = (ALLOWED_DIR / file_path).resolve()

    # 1. Sandbox security checks
    error = check_path_allowed(target_path)
    if error:
        return error
    if not target_path.exists():
        return f"Error: File '{file_path}' not found."
    if not target_path.is_file():
        return f"Error: '{file_path}' is not a file."

    # 2. Read file safely
    try:
        content = target_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:
        return f"Error reading file: {exc!r}"

    if not content.strip():
        return "File is empty."

    # 3. Prevent side-call blowout on huge files (~8k-10k tokens max)
    # Adjust as needed for your model's context window
    if len(content) > CONTEXT_LENGTH:
        content = (
            content[:CONTEXT_LENGTH]
            + f"\n\n...[TRUNCATED: Exceeded {CONTEXT_LENGTH} characters for summarization]..."
        )

    # 4. Clean unindented prompts with separated system/user roles
    system_prompt = (
        "You are a specialized file analysis assistant. "
        "Review the provided file content and generate a dense, factual summary. "
        "Adhere strictly to the requested focus area."
    )

    user_prompt = textwrap.dedent(f"""\
        FOCUS: {focus}

        FILE CONTENT:
        {content}

        CONCISE SUMMARY:""")

    try:
        # Isolated side-call (does NOT pollute the main conversation history)
        response = client.chat.completions.create(
            model=_get_active_model(),
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.2  # Low temperature for factual precision
        )

        message = response.choices[0].message
        # Handles models that store thoughts separately
        summary = (message.content or "").strip()

        if not summary and hasattr(message, "reasoning_content"): #omit reasoning_content if not present
            summary = message.reasoning_content.strip()

        return f"--- SUMMARY OF '{file_path}' ---\n{summary}"

    except Exception as exc:
        return f"Error during model summarization: {exc!r}"