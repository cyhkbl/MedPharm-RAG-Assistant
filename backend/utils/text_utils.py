from __future__ import annotations

import re
from pathlib import Path

import tiktoken


def clean_text(text: str) -> str:
    """Normalize text and remove excessive whitespace."""

    normalized = text.replace("\ufeff", "").replace("\u3000", " ")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[ \t]+", " ", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def count_chars(text: str) -> int:
    """Count meaningful characters with Chinese-friendly semantics."""

    cleaned = clean_text(text)
    # 中文教材压缩统计通常不计空白字符。
    return len(re.sub(r"\s+", "", cleaned))


def detect_encoding(file_path: str | Path) -> str:
    """Detect common Chinese textbook encodings."""

    path = Path(file_path)
    sample = path.read_bytes()[:8192]
    for encoding in ("utf-8", "gbk", "gb2312"):
        try:
            sample.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "utf-8"


def truncate_to_tokens(text: str, max_tokens: int) -> str:
    """Truncate text to a token limit using tiktoken."""

    if max_tokens <= 0:
        return ""

    try:
        encoding = tiktoken.encoding_for_model("gpt-4o")
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")

    tokens = encoding.encode(text)
    if len(tokens) <= max_tokens:
        return text
    return encoding.decode(tokens[:max_tokens])
