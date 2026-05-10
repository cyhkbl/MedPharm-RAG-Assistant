from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Awaitable, Callable

import aiofiles
from fastapi import APIRouter, HTTPException, UploadFile

from backend.core.parser.docx_parser import parse_docx
from backend.core.parser.md_parser import parse_markdown
from backend.core.parser.pdf_parser import parse_pdf
from backend.core.parser.txt_parser import parse_txt
from backend.models.database import delete_textbook, get_all_textbooks, get_data_paths, get_textbook, save_textbook
from backend.models.schemas import Textbook

router = APIRouter()
MAX_UPLOAD_BYTES = 500 * 1024 * 1024
PARSERS: dict[str, Callable[[str], Awaitable[dict]]] = {
    ".pdf": parse_pdf,
    ".md": parse_markdown,
    ".markdown": parse_markdown,
    ".txt": parse_txt,
    ".docx": parse_docx,
}


@router.post("/api/upload")
async def upload_textbook(file: UploadFile) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    parser = PARSERS.get(suffix)
    if parser is None:
        raise HTTPException(status_code=400, detail="Unsupported format. Use PDF, MD, TXT, or DOCX.")

    saved_path = await _save_upload(file)
    parsed = await parser(str(saved_path))
    textbook = Textbook.model_validate(parsed)
    await save_textbook(textbook)
    await _write_textbooks_index()
    return textbook.model_dump(mode="json")


@router.get("/api/textbooks")
async def list_textbooks() -> list[dict]:
    textbooks = await get_all_textbooks()
    return [textbook.model_dump(mode="json", exclude={"chapters"}) for textbook in textbooks]


@router.get("/api/textbooks/{textbook_id}/chapters")
async def textbook_chapters(textbook_id: str) -> dict:
    textbook = await get_textbook(textbook_id)
    if textbook is None:
        raise HTTPException(status_code=404, detail="Textbook not found")
    return {"textbook_id": textbook.id, "chapters": [chapter.model_dump(mode="json") for chapter in textbook.chapters]}


@router.delete("/api/textbooks/{textbook_id}")
async def remove_textbook(textbook_id: str) -> dict:
    textbook = await get_textbook(textbook_id)
    deleted = await delete_textbook(textbook_id)
    if textbook is not None:
        upload_path = get_data_paths()["textbooks"] / textbook.filename
        if upload_path.exists():
            upload_path.unlink()
    await _write_textbooks_index()
    if not deleted:
        raise HTTPException(status_code=404, detail="Textbook not found")
    return {"deleted": True, "textbook_id": textbook_id}


async def _save_upload(file: UploadFile) -> Path:
    filename = Path(file.filename or "upload.bin").name
    target = get_data_paths()["textbooks"] / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    size = 0
    async with aiofiles.open(target, "wb") as output:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                await output.close()
                target.unlink(missing_ok=True)
                raise HTTPException(status_code=413, detail="File too large. Limit is 500MB.")
            await output.write(chunk)
    await file.close()
    return target


async def _write_textbooks_index() -> None:
    textbooks = await get_all_textbooks()
    path = get_data_paths()["base"] / "textbooks.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [textbook.model_dump(mode="json") for textbook in textbooks]
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.move(str(tmp_path), str(path))
