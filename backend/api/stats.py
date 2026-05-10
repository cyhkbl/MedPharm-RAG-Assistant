from __future__ import annotations

from fastapi import APIRouter

from backend.core.llm.client import get_token_stats

router = APIRouter()


@router.get("/api/stats/tokens")
async def token_stats() -> dict:
    """返回 LLM Token 消耗统计"""
    return get_token_stats().to_dict()
