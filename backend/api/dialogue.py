from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from backend.core.llm.client import chat_completion
from backend.core.llm.prompts import DIALOGUE_SYSTEM_PROMPT
from backend.models.database import get_chat_history, get_data_paths, save_chat_history
from backend.models.schemas import ChatMessage

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    conversation_id: str | None = None


@router.post("/api/dialogue/chat")
async def dialogue_chat(payload: ChatRequest) -> dict:
    conversation_id = payload.conversation_id or f"conv_{uuid.uuid4().hex[:12]}"
    history = await get_chat_history()
    scoped = _conversation_messages(conversation_id)
    messages = [{"role": "system", "content": DIALOGUE_SYSTEM_PROMPT}]
    messages.extend({"role": item["role"], "content": item["content"]} for item in scoped[-12:])
    messages.append({"role": "user", "content": payload.message})
    answer = await chat_completion(messages, temperature=0.3, max_tokens=1600)

    now = datetime.utcnow()
    history.extend(
        [
            ChatMessage(role="user", content=f"[{conversation_id}] {payload.message}", timestamp=now),
            ChatMessage(role="assistant", content=f"[{conversation_id}] {answer}", timestamp=datetime.utcnow()),
        ]
    )
    await save_chat_history(history)
    return {"conversation_id": conversation_id, "message": answer, "timestamp": datetime.utcnow().isoformat()}


@router.get("/api/dialogue/history")
async def dialogue_history(conversation_id: str | None = None) -> dict:
    messages = await get_chat_history()
    if conversation_id:
        return {"conversation_id": conversation_id, "messages": _conversation_messages(conversation_id)}
    return {"messages": [message.model_dump(mode="json") for message in messages]}


def _conversation_messages(conversation_id: str) -> list[dict]:
    import json

    path = get_data_paths()["chat_history"]
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8") or "[]")
    prefix = f"[{conversation_id}] "
    messages = []
    for item in raw:
        content = str(item.get("content", ""))
        if content.startswith(prefix):
            messages.append({**item, "content": content[len(prefix) :]})
    return messages
