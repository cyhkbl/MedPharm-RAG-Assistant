from __future__ import annotations

import json
import re
import uuid
from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from backend.core.llm.client import chat_completion
from backend.core.llm.prompts import DIALOGUE_SYSTEM_PROMPT
from backend.models.database import get_chat_history, get_data_paths, save_chat_history, get_decisions, save_decisions
from backend.models.schemas import ChatMessage

router = APIRouter()

# 意图识别 prompt：判断用户是否要修改整合决策
INTENT_PROMPT = """你是意图识别助手。分析用户消息，判断用户是否想要修改知识整合决策。

如果用户想要"保留/合并/删除"某个知识点，或者对整合结果提出修改意见，输出 JSON：
{{"intent": "override", "keyword": "用户提到的知识点关键词", "action": "keep/merge/remove"}}

如果用户只是普通提问或聊天，输出：
{{"intent": "chat"}}

只输出 JSON，不要其他内容。

用户消息：{message}
"""


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

    # 并行：获取正常回复 + 意图识别
    answer = await chat_completion(messages, temperature=0.3, max_tokens=1600)

    # 意图识别：判断是否要修改决策
    override_result = await _try_override_decision(payload.message)

    if override_result:
        answer += f"\n\n📋 {override_result}"

    now = datetime.utcnow()
    history.extend(
        [
            ChatMessage(role="user", content=f"[{conversation_id}] {payload.message}", timestamp=now),
            ChatMessage(role="assistant", content=f"[{conversation_id}] {answer}", timestamp=datetime.utcnow()),
        ]
    )
    await save_chat_history(history)
    return {"conversation_id": conversation_id, "message": answer, "timestamp": datetime.utcnow().isoformat()}


async def _try_override_decision(message: str) -> str | None:
    """尝试识别用户意图并修改整合决策。返回确认信息或 None。"""
    try:
        # 用 LLM 识别意图
        intent_prompt = INTENT_PROMPT.format(message=message)
        raw = await chat_completion([{"role": "user", "content": intent_prompt}], temperature=0.1, max_tokens=200)

        # 解析 JSON
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.DOTALL)

        intent_data = json.loads(raw)
        if intent_data.get("intent") != "override":
            return None

        keyword = intent_data.get("keyword", "")
        action = intent_data.get("action", "")
        if not keyword or action not in ("keep", "merge", "remove"):
            return None

        # 查找匹配的决策
        decisions = await get_decisions()
        for decision in decisions:
            # 匹配 affected_nodes 或 result_node 中包含关键词的决策
            all_nodes = decision.affected_nodes + [decision.result_node]
            if any(keyword in node for node in all_nodes) or keyword in decision.reason:
                old_action = decision.action
                decision.action = action
                await save_decisions(decisions)
                return f"已将决策 [{decision.decision_id}] 中「{keyword}」的操作从 {old_action} 修改为 {action}"

        return f"未找到包含「{keyword}」的整合决策"
    except Exception:
        return None


@router.get("/api/dialogue/history")
async def dialogue_history(conversation_id: str | None = None) -> dict:
    messages = await get_chat_history()
    if conversation_id:
        return {"conversation_id": conversation_id, "messages": _conversation_messages(conversation_id)}
    return {"messages": [message.model_dump(mode="json") for message in messages]}


def _conversation_messages(conversation_id: str) -> list[dict]:
    import json as _json

    path = get_data_paths()["chat_history"]
    if not path.exists():
        return []
    raw = _json.loads(path.read_text(encoding="utf-8") or "[]")
    prefix = f"[{conversation_id}] "
    messages = []
    for item in raw:
        content = str(item.get("content", ""))
        if content.startswith(prefix):
            messages.append({**item, "content": content[len(prefix) :]})
    return messages
