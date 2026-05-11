import re

# Patterns that could attempt prompt injection
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"you\s+are\s+now\s+",
    r"system\s*:\s*",
    r"<\|im_start\|>",
    r"<\|im_end\|>",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]

MAX_INPUT_LENGTH = 2000


def sanitize_llm_input(text: str) -> str:
    """Sanitize user text before passing to LLM."""
    # Truncate
    text = text[:MAX_INPUT_LENGTH]
    # Remove control characters (except newlines and tabs)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    # Flag but don't remove injection patterns — the LLM's system prompt
    # should take precedence, but we strip the most egregious attempts
    for pattern in _COMPILED:
        text = pattern.sub("[filtered]", text)
    return text.strip()
