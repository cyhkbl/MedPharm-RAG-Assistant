from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Chapter(BaseModel):
    chapter_id: str
    title: str
    page_start: int
    page_end: int
    content: str
    char_count: int


class Textbook(BaseModel):
    id: str
    filename: str
    title: str
    format: str
    total_pages: int
    total_chars: int
    chapters: list[Chapter] = Field(default_factory=list)
    upload_time: datetime
    parse_status: str


class KnowledgeNode(BaseModel):
    id: str
    name: str
    definition: str
    category: str
    chapter: str
    page: int
    textbook_id: str
    frequency: int = 1


class KnowledgeEdge(BaseModel):
    source: str
    target: str
    relation_type: Literal["prerequisite", "parallel", "contains", "applies_to"]
    description: str


class IntegrationDecision(BaseModel):
    decision_id: str
    action: Literal["merge", "keep", "remove"]
    affected_nodes: list[str]
    result_node: str
    reason: str
    confidence: float


class Citation(BaseModel):
    textbook: str
    chapter: str
    page: int
    relevance_score: float
    source_chunks: list[str]


class RAGResponse(BaseModel):
    answer: str
    citations: list[Citation]


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    timestamp: datetime


class IntegrationStats(BaseModel):
    original_chars: int
    compressed_chars: int
    compression_ratio: float
    merge_count: int
    keep_count: int
    remove_count: int
