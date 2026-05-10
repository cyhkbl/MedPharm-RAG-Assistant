from __future__ import annotations

import re
import uuid
from collections import Counter
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover - compatibility with older installs
    import fitz  # type: ignore[no-redef]

from backend.utils.text_utils import clean_text, count_chars

CHAPTER_RE = re.compile(r"(第[一二三四五六七八九十百千万\d]+章[^\n]{0,80}|(?:Chapter|CHAPTER)\s+\d+[^\n]{0,80})")


async def parse_pdf(file_path: str) -> dict:
    """Parse a PDF textbook page by page using PyMuPDF."""

    path = Path(file_path)
    try:
        document = fitz.open(str(path))
    except Exception as exc:
        return _empty_textbook(path, "error", f"PDF 打开失败: {exc}")

    try:
        page_count = int(document.page_count)
        page_items: list[dict[str, Any]] = []
        edge_lines: Counter[str] = Counter()
        all_font_sizes: list[float] = []

        for page_index in range(page_count):
            page = document.load_page(page_index)
            lines, font_sizes = _extract_page_lines(page)
            all_font_sizes.extend(font_sizes)
            for line in _edge_candidates(lines):
                edge_lines[line["text"]] += 1
            page_items.append({"page": page_index + 1, "lines": lines})

        repeated = {line for line, freq in edge_lines.items() if page_count >= 3 and freq >= max(3, page_count // 2)}
        heading_threshold = _heading_threshold(all_font_sizes)
        pages: list[dict[str, Any]] = []
        for item in page_items:
            filtered = [line for line in item["lines"] if not _is_header_footer(line, repeated)]
            text = clean_text("\n".join(line["text"] for line in filtered))
            headings = _detect_headings(filtered, heading_threshold)
            pages.append({"page": item["page"], "text": text, "headings": headings})

        chapters = _build_chapters(pages, path.stem)
        status = "success" if chapters else "empty"
        total_chars = sum(chapter["char_count"] for chapter in chapters)
        return {
            "id": _textbook_id(path),
            "filename": path.name,
            "title": _detect_title(path, pages),
            "format": "pdf",
            "total_pages": page_count,
            "total_chars": total_chars,
            "chapters": chapters,
            "upload_time": datetime.utcnow().isoformat(),
            "parse_status": status,
        }
    except Exception as exc:
        return _empty_textbook(path, "error", f"PDF 解析失败: {exc}", document.page_count)
    finally:
        document.close()


def _extract_page_lines(page: Any) -> tuple[list[dict[str, Any]], list[float]]:
    raw = page.get_text("dict")
    lines: list[dict[str, Any]] = []
    font_sizes: list[float] = []
    page_height = float(page.rect.height)
    for block in raw.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            text = clean_text("".join(span.get("text", "") for span in spans))
            if not text:
                continue
            sizes = [float(span.get("size", 0)) for span in spans if span.get("size")]
            flags = [int(span.get("flags", 0)) for span in spans]
            font_sizes.extend(sizes)
            bbox = line.get("bbox", [0, 0, 0, 0])
            lines.append(
                {
                    "text": text,
                    "size": max(sizes) if sizes else 0.0,
                    "bold": any(flag & 16 for flag in flags),
                    "y0": float(bbox[1]),
                    "y1": float(bbox[3]),
                    "page_height": page_height,
                }
            )
    return lines, font_sizes


def _edge_candidates(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for line in lines:
        text = line["text"].strip()
        if line["y0"] < line["page_height"] * 0.12 or line["y1"] > line["page_height"] * 0.88:
            if text and len(text) <= 80:
                candidates.append(line)
    return candidates


def _is_header_footer(line: dict[str, Any], repeated: set[str]) -> bool:
    text = line["text"].strip()
    if text in repeated:
        return True
    if re.fullmatch(r"[-—]?\s*\d+\s*[-—]?", text):
        return True
    return False


def _heading_threshold(sizes: list[float]) -> float:
    if not sizes:
        return 16.0
    avg = mean(sizes)
    return max(avg * 1.25, sorted(sizes)[int(len(sizes) * 0.8)])


def _detect_headings(lines: list[dict[str, Any]], heading_threshold: float) -> list[str]:
    headings: list[str] = []
    for line in lines:
        text = line["text"].strip()
        if CHAPTER_RE.search(text):
            headings.append(text)
            continue
        if 2 <= len(text) <= 80 and line["size"] >= heading_threshold and (line["bold"] or count_chars(text) <= 40):
            if not re.fullmatch(r"\d+", text):
                headings.append(text)
    return headings


def _build_chapters(pages: list[dict[str, Any]], fallback_title: str) -> list[dict]:
    markers: list[tuple[int, str]] = []
    for page in pages:
        for heading in page["headings"]:
            if CHAPTER_RE.search(heading) or len(markers) == 0:
                markers.append((int(page["page"]), heading))
                break

    if not markers:
        content = clean_text("\n\n".join(page["text"] for page in pages if page["text"]))
        return [_chapter(1, fallback_title, 1, pages[-1]["page"] if pages else 1, content)] if content else []

    chapters: list[dict] = []
    for index, (start_page, title) in enumerate(markers):
        end_page = markers[index + 1][0] - 1 if index + 1 < len(markers) else (pages[-1]["page"] if pages else start_page)
        content = clean_text("\n\n".join(page["text"] for page in pages if start_page <= page["page"] <= end_page))
        if content:
            chapters.append(_chapter(index + 1, title, start_page, end_page, content))
    return chapters


def _chapter(index: int, title: str, page_start: int, page_end: int, content: str) -> dict:
    return {
        "chapter_id": f"ch_{index:03d}",
        "title": clean_text(title)[:120] or f"章节 {index}",
        "page_start": page_start,
        "page_end": page_end,
        "content": content,
        "char_count": count_chars(content),
    }


def _detect_title(path: Path, pages: list[dict[str, Any]]) -> str:
    for page in pages[:3]:
        for heading in page["headings"]:
            if heading and not CHAPTER_RE.search(heading):
                return heading[:120]
    return path.stem


def _empty_textbook(path: Path, status: str, message: str, total_pages: int = 0) -> dict:
    return {
        "id": _textbook_id(path),
        "filename": path.name,
        "title": path.stem,
        "format": "pdf",
        "total_pages": total_pages,
        "total_chars": 0,
        "chapters": [],
        "upload_time": datetime.utcnow().isoformat(),
        "parse_status": f"{status}: {message}",
    }


def _textbook_id(path: Path) -> str:
    return f"tb_{uuid.uuid5(uuid.NAMESPACE_URL, str(path.resolve()))}"
