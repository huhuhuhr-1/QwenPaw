import re

_TAG = "redacted_thinking"
_START = f"<{_TAG}>"
_END = f"</{_TAG}>"


def _find_ci(haystack: str, needle: str, start: int = 0) -> int:
    return haystack.lower().find(needle.lower(), start)


def strip_thinking_blocks(text: str) -> str:
    """Remove MiniMax-style <think>...</think> blocks and orphan tags."""
    if not text:
        return text

    low = text.lower()
    if _TAG not in low:
        return text.strip()

    out: list[str] = []
    pos = 0
    while pos < len(text):
        start = _find_ci(text, _START, pos)
        if start == -1:
            out.append(text[pos:])
            break
        out.append(text[pos:start])
        end = _find_ci(text, _END, start + len(_START))
        if end == -1:
            break
        pos = end + len(_END)

    cleaned = "".join(out)

    cleaned = re.sub(r"<\s*redacted_thinking\s*>", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"<\s*/\s*redacted_thinking\s*>", "", cleaned, flags=re.IGNORECASE)

    return cleaned.strip()


def sanitize_polish_text(text: str) -> str:
    """Clean text before/after polish API calls."""
    return strip_thinking_blocks(text)
