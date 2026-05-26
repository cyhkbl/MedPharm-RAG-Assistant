from __future__ import annotations

import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import aiofiles
from pydantic import BaseModel, TypeAdapter

from backend.config import get_settings
from backend.models.schemas import (
    ChatMessage,
    IntegrationDecision,
    KnowledgeEdge,
    KnowledgeNode,
    Textbook,
)


def get_data_dir() -> Path:
    """Return the configured data directory."""

    return Path(get_settings().DATA_DIR)


def get_data_paths() -> dict[str, Path]:
    """Return all storage paths used by the JSON persistence layer."""

    data_dir = get_data_dir()
    return {
        "base": data_dir,
        "textbooks": data_dir / "textbooks",
        "parsed": data_dir / "parsed",
        "kg": data_dir / "kg",
        "vectors": data_dir / "vectors",
        "decisions": data_dir / "kg" / "decisions.json",
        "chat_history": data_dir / "chat_history.json",
    }


async def ensure_data_dirs() -> None:
    """Create data directories if they do not exist."""

    paths = get_data_paths()
    for key in ("base", "textbooks", "parsed", "kg", "vectors"):
        paths[key].mkdir(parents=True, exist_ok=True)


def _json_default(value: Any) -> str:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _model_to_json(model: BaseModel) -> str:
    return model.model_dump_json(indent=2)


async def _read_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default

    async with aiofiles.open(path, encoding="utf-8") as file:
        content = await file.read()

    if not content.strip():
        return default
    return json.loads(content)


async def _write_json(path: Path, payload: Any) -> None:
    """Atomic write: write to a temp file in the same directory, then rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(payload, ensure_ascii=False, indent=2, default=_json_default)

    # Write to a temp file in the same filesystem (required for atomic rename)
    fd, tmp_path = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        async with aiofiles.open(fd, "w", encoding="utf-8", closefd=True) as file:
            await file.write(content)
        # Atomic rename (on POSIX systems)
        shutil.move(tmp_path, str(path))
    except Exception:
        # Clean up temp file on failure
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


async def save_textbook(textbook: Textbook) -> None:
    """Persist one textbook metadata and parsed chapters as JSON."""

    await ensure_data_dirs()
    path = get_data_paths()["parsed"] / f"{textbook.id}.json"
    await _write_json(path, textbook.model_dump(mode="json"))


async def get_textbook(id: str) -> Textbook | None:
    """Load one textbook by id."""

    path = get_data_paths()["parsed"] / f"{id}.json"
    if not path.exists():
        return None

    data = await _read_json(path, None)
    if data is None:
        return None
    return Textbook.model_validate(data)


async def get_all_textbooks() -> list[Textbook]:
    """Load all stored textbook records."""

    await ensure_data_dirs()
    parsed_dir = get_data_paths()["parsed"]
    textbooks: list[Textbook] = []
    for path in sorted(parsed_dir.glob("*.json")):
        data = await _read_json(path, None)
        if data is not None:
            textbooks.append(Textbook.model_validate(data))
    return textbooks


async def delete_textbook(id: str) -> bool:
    """Delete a textbook and its knowledge graph JSON if present."""

    paths = get_data_paths()
    deleted = False
    for path in (paths["parsed"] / f"{id}.json", paths["kg"] / f"{id}.json"):
        if path.exists():
            path.unlink()
            deleted = True
    return deleted


async def save_kg_data(
    textbook_id: str,
    nodes: list[KnowledgeNode],
    edges: list[KnowledgeEdge],
) -> None:
    """Persist knowledge graph data for one textbook."""

    await ensure_data_dirs()
    payload = {
        "textbook_id": textbook_id,
        "nodes": [node.model_dump(mode="json") for node in nodes],
        "edges": [edge.model_dump(mode="json") for edge in edges],
    }
    await _write_json(get_data_paths()["kg"] / f"{textbook_id}.json", payload)


async def get_kg_data(textbook_id: str) -> tuple[list[KnowledgeNode], list[KnowledgeEdge]]:
    """Load knowledge graph data for one textbook."""

    data = await _read_json(get_data_paths()["kg"] / f"{textbook_id}.json", {})
    node_adapter = TypeAdapter(list[KnowledgeNode])
    edge_adapter = TypeAdapter(list[KnowledgeEdge])
    return (
        node_adapter.validate_python(data.get("nodes", [])),
        edge_adapter.validate_python(data.get("edges", [])),
    )


async def save_decisions(decisions: list[IntegrationDecision]) -> None:
    """Persist integration decisions."""

    await ensure_data_dirs()
    payload = [decision.model_dump(mode="json") for decision in decisions]
    await _write_json(get_data_paths()["decisions"], payload)


async def get_decisions() -> list[IntegrationDecision]:
    """Load integration decisions."""

    data = await _read_json(get_data_paths()["decisions"], [])
    return TypeAdapter(list[IntegrationDecision]).validate_python(data)


async def save_chat_history(messages: list[ChatMessage]) -> None:
    """Persist full chat history."""

    await ensure_data_dirs()
    payload = [message.model_dump(mode="json") for message in messages]
    await _write_json(get_data_paths()["chat_history"], payload)


async def get_chat_history() -> list[ChatMessage]:
    """Load chat history."""

    data = await _read_json(get_data_paths()["chat_history"], [])
    return TypeAdapter(list[ChatMessage]).validate_python(data)
