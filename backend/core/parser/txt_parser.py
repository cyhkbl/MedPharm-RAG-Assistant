from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path

import aiofiles

from backend.utils.text_utils import clean_text, count_chars

CHAPTER_PATTERN = re.compile(
    r"(?m)^(?P<title>\s*(?:第[一二三四五六七八九十百千万\d]+章[^\n]*|"
    r"(?:Chapter|CHAPTER)\s+\d+[^\n]*|\d+(?:\.\d+)?\s+[^\n]{2,80}))$"
)


async def parse_txt(file_path: str) -> dict:
    """Parse a plain-text textbook with Chinese-friendly encoding detection."""

    path = Path(file_path)
    raw_bytes = path.read_bytes()
    encoding = _detect_encoding(raw_bytes)
    text = clean_text(raw_bytes.decode(encoding, errors="replace"))
    title = _first_nonempty_line(text) or path.stem
    chapters = _split_by_headings(text)
    if not chapters:
        chapters = _split_by_double_newlines(text, title)

    total_chars = sum(chapter["char_count"] for chapter in chapters)
    return {
        "id": _textbook_id(path),
        "filename": path.name,
        "title": title,
        "format": "txt",
        "total_pages": max(len(chapters), 1),
        "total_chars": total_chars,
        "chapters": chapters,
        "upload_time": datetime.utcnow().isoformat(),
        "parse_status": "success" if chapters else "empty",
    }


def _detect_encoding(raw_bytes: bytes) -> str:
    for encoding in ("utf-8", "gbk", "gb2312", "latin-1"):
        try:
            raw_bytes.decode(encoding)
            return encoding
        except UnicodeDecodeError:
            continue
    return "utf-8"


def _split_by_headings(text: str) -> list[dict]:
    matches = list(CHAPTER_PATTERN.finditer(text))
    if not matches:
        return []

    chapters: list[dict] = []
    for index, match in enumerate(matches):
        start = match.start()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        title = clean_text(match.group("title"))
        content = clean_text(text[start:end])
        if not content:
            continue
        chapters.append(_chapter(index + 1, title, content))
    return chapters


def _split_by_double_newlines(text: str, title: str) -> list[dict]:
    blocks = [clean_text(block) for block in re.split(r"\n\s*\n", text) if clean_text(block)]
    if not blocks:
        return []
    if len(blocks) <= 3:
        content = clean_text("\n\n".join(blocks))
        return [_chapter(1, title, content)]
    return [_chapter(index, _title_from_block(block, index), block) for index, block in enumerate(blocks, 1)]


def _chapter(index: int, title: str, content: str) -> dict:
    return {
        "chapter_id": f"ch_{index:03d}",
        "title": title[:120] or f"章节 {index}",
        "page_start": index,
        "page_end": index,
        "content": content,
        "char_count": count_chars(content),
    }


def _title_from_block(block: str, index: int) -> str:
    return (_first_nonempty_line(block) or f"章节 {index}")[:120]


def _first_nonempty_line(text: str) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:120]
    return None


def _textbook_id(path: Path) -> str:
    return f"tb_{uuid.uuid5(uuid.NAMESPACE_URL, str(path.resolve()))}"
