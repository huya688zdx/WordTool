import re
from typing import List


def normalize_whitespace(text: str) -> str:
    """Collapse multiple spaces/tabs/newlines into single space, strip."""
    return re.sub(r"\s+", " ", text).strip()


def normalize_unicode(text: str) -> str:
    """Normalize ligatures, smart quotes, dashes to ASCII equivalents."""
    replacements = {
        "­": "",       # soft hyphen -> remove
        "‘": "'",      # left single quote
        "’": "'",      # right single quote
        "“": '"',      # left double quote
        "”": '"',      # right double quote
        "–": "-",      # en dash
        "—": "-",      # em dash
        "…": "...",    # ellipsis
        "ﬁ": "fi",     # fi ligature
        "ﬂ": "fl",     # fl ligature
        " ": " ",      # non-breaking space
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def remove_zero_width(text: str) -> str:
    """Remove zero-width characters."""
    return re.sub(r"[​‌‍﻿]", "", text)


def normalize_for_matching(text: str) -> str:
    """Full normalization pipeline for text anchor matching."""
    text = normalize_unicode(text)
    text = remove_zero_width(text)
    text = normalize_whitespace(text)
    return text


def extract_search_tokens(text: str, min_length: int = 2) -> List[str]:
    """Break text into alphanumeric tokens for fuzzy matching."""
    tokens = re.findall(r"[\w一-鿿]+", text, re.UNICODE)
    return [t for t in tokens if len(t) >= min_length]


def chunk_text(text: str, chunk_size: int = 50) -> List[str]:
    """Split text into chunks at word boundaries."""
    words = text.split()
    chunks = []
    current = []
    current_len = 0

    for word in words:
        if current_len + len(word) + len(current) > chunk_size and current:
            chunks.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len += len(word)

    if current:
        chunks.append(" ".join(current))

    return chunks
