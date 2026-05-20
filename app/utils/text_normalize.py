import re
import sys
import os
from typing import List


def fix_console_encoding():
    """Set console encoding for CJK systems (Japanese/Chinese)."""
    if sys.platform == "win32":
        # Try UTF-8 first, fall back to system locale
        for encoding in ["utf-8", "cp932", "cp936", "shift_jis", "gbk"]:
            try:
                "test".encode(encoding)
                if hasattr(sys.stdout, "reconfigure"):
                    sys.stdout.reconfigure(encoding=encoding, errors="replace")
                if hasattr(sys.stderr, "reconfigure"):
                    sys.stderr.reconfigure(encoding=encoding, errors="replace")
                break
            except (LookupError, OSError):
                continue


def normalize_whitespace(text: str) -> str:
    """Collapse multiple spaces/tabs/newlines into single space, strip."""
    # Also handle full-width spaces (Japanese/Chinese)
    text = text.replace("　", " ")  # full-width space -> normal space
    return re.sub(r"\s+", " ", text).strip()


def normalize_unicode(text: str) -> str:
    """Normalize ligatures, smart quotes, dashes, CJK full-width to ASCII equivalents."""
    replacements = {
        # Soft hyphen & zero-width
        "­": "",       # soft hyphen
        "​": "",       # zero-width space
        "‌": "",       # zero-width non-joiner
        "‍": "",       # zero-width joiner
        "﻿": "",       # BOM / zero-width no-break space
        "⁠": "",       # word joiner

        # Quotes
        "‘": "'",      # left single quote
        "’": "'",      # right single quote
        "“": '"',      # left double quote
        "”": '"',      # right double quote

        # Dashes
        "–": "-",      # en dash
        "—": "-",      # em dash
        "―": "-",      # horizontal bar

        # Ellipsis
        "…": "...",    # ellipsis

        # Ligatures
        "ﬁ": "fi",     # fi ligature
        "ﬂ": "fl",     # fl ligature

        # Spaces
        " ": " ",      # non-breaking space
        "　": " ",      # full-width space (CJK)

        # Japanese full-width alphanumerics -> ASCII
        "０": "0", "１": "1", "２": "2", "３": "3", "４": "4",
        "５": "5", "６": "6", "７": "7", "８": "8", "９": "9",
        "Ａ": "A", "Ｂ": "B", "Ｃ": "C", "Ｄ": "D", "Ｅ": "E",
        "Ｆ": "F", "Ｇ": "G", "Ｈ": "H", "Ｉ": "I", "Ｊ": "J",
        "Ｋ": "K", "Ｌ": "L", "Ｍ": "M", "Ｎ": "N", "Ｏ": "O",
        "Ｐ": "P", "Ｑ": "Q", "Ｒ": "R", "Ｓ": "S", "Ｔ": "T",
        "Ｕ": "U", "Ｖ": "V", "Ｗ": "W", "Ｘ": "X", "Ｙ": "Y",
        "Ｚ": "Z",
        "ａ": "a", "ｂ": "b", "ｃ": "c", "ｄ": "d", "ｅ": "e",
        "ｆ": "f", "ｇ": "g", "ｈ": "h", "ｉ": "i", "ｊ": "j",
        "ｋ": "k", "ｌ": "l", "ｍ": "m", "ｎ": "n", "ｏ": "o",
        "ｐ": "p", "ｑ": "q", "ｒ": "r", "ｓ": "s", "ｔ": "t",
        "ｕ": "u", "ｖ": "v", "ｗ": "w", "ｘ": "x", "ｙ": "y",
        "ｚ": "z",

        # Japanese punctuation normalization
        "，": ",",      # full-width comma
        "．": ".",      # full-width period
        "：": ":",      # full-width colon
        "；": ";",      # full-width semicolon
        "（": "(",      # full-width left paren
        "）": ")",      # full-width right paren
        "［": "[",      # full-width left bracket
        "］": "]",      # full-width right bracket
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def remove_zero_width(text: str) -> str:
    """Remove zero-width characters."""
    return re.sub(r"[​‌‍﻿⁠­]", "", text)


def normalize_for_matching(text: str) -> str:
    """Full normalization pipeline for text anchor matching.

    Handles: English, Chinese, Japanese (hiragana/katakana/kanji).
    """
    text = normalize_unicode(text)
    text = remove_zero_width(text)
    text = normalize_whitespace(text)
    return text


# Regex for CJK + Japanese character extraction
# ぀-ゟ: Hiragana
# ゠-ヿ: Katakana
# 一-鿿: CJK Unified Ideographs
# 㐀-䶿: CJK Extension A
# ｦ-ﾟ: Half-width Katakana
# 々: Japanese iteration mark
# 〆: Japanese ideographic closing mark
_CJK_JAPANESE_PATTERN = re.compile(
    r"[\w぀-ゟ゠-ヿ一-鿿㐀-䶿"
    r"ｦ-ﾟ々〆〇]+",
    re.UNICODE,
)


def extract_search_tokens(text: str, min_length: int = 2) -> List[str]:
    """Break text into alphanumeric/CJK/Japanese tokens for fuzzy matching."""
    tokens = _CJK_JAPANESE_PATTERN.findall(text)
    return [t for t in tokens if len(t) >= min_length]


def chunk_text(text: str, chunk_size: int = 50) -> List[str]:
    """Split text into chunks at word boundaries.

    For CJK/Japanese text (no spaces between words), split by character count.
    For Latin text, split by word boundaries.
    """
    # Detect if text is primarily CJK/Japanese
    cjk_count = sum(1 for c in text if '぀' <= c <= '鿿' or
                    'ｦ' <= c <= 'ﾟ' or '一' <= c <= '鿿')
    total = len(text.replace(" ", ""))
    is_cjk = total > 0 and cjk_count / max(total, 1) > 0.3

    if is_cjk:
        # Split by character count for CJK text
        chunks = []
        for i in range(0, len(text), chunk_size):
            chunk = text[i:i + chunk_size].strip()
            if chunk:
                chunks.append(chunk)
        return chunks
    else:
        # Split by word boundaries for Latin text
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
