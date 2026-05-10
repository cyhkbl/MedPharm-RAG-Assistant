from __future__ import annotations

import re
import uuid
from datetime import datetime
from pathlib import Path

import aiofiles

from backend.utils.text_utils import clean_text, count_chars


async def parse_markdown(file_path: str) -> dict:
    """Parse a Markdown textbook and split chapters by level-1 headings."""

    path = Path(file_path)
    async with aiofiles.open(path, encoding="utf-8") as file:
        raw_text = await file.read()

    text = clean_text(raw_text)
    title_match = re.search(r"^#\s+(.+)$", text, flags=re.MULTILINE)
    title = title_match.group(1).strip() if title_match else path.stem
    sections = re.split(r"(?m)^(#\s+.+)$", text)

    chapters: list[dict] = []
    if len(sections) == 1:
        content = clean_text(sections[0])
        if content:
            chapters.append(
                {
                    "chapter_id": "ch_001",
                    "title": title,
                    "page_start": 1,
                    "page_end": 1,
                    "content": content,
                    "char_count": count_chars(content),
                }
            )
    else:
        prefix = clean_text(sections[0])
        index = 1
        for i in range(1, len(sections), 2):
            heading = sections[i].lstrip("#").strip()
            body = clean_text(sections[i + 1] if i + 1 < len(sections) else "")
            content = clean_text(f"{heading}\n\n{body}")
            if not content:
                continue
            if index == 1 and prefix:
                content = clean_text(f"{prefix}\n\n{content}")
            chapters.append(
                {
                    "chapter_id": f"ch_{index:03d}",
                    "title": heading,
                    "page_start": index,
                    "page_end": index,
                    "content": content,
                    "char_count": count_chars(content),
                }
            )
            index += 1

    total_chars = sum(chapter["char_count"] for chapter in chapters)
    return {
        "id": _textbook_id(path),
        "filename": path.name,
        "title": title,
        "format": "md",
        "total_pages": max(len(chapters), 1),
        "total_chars": total_chars,
        "chapters": chapters,
        "upload_time": datetime.utcnow().isoformat(),
        "parse_status": "success" if chapters else "empty",
    }


def _textbook_id(path: Path) -> str:
    return f"tb_{uuid.uuid5(uuid.NAMESPACE_URL, str(path.resolve()))}"
