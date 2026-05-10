"""tests/test_chunker.py — 文档分块单元测试"""

from backend.core.rag.chunker import chunk_text


def test_empty_text():
    """空文本应返回空列表"""
    result = chunk_text("", chunk_size=600, overlap=100)
    assert result == []


def test_short_text():
    """短于 chunk_size 的文本应返回单个 chunk"""
    text = "炎症是具有血管系统的活体组织对损伤因子所发生的防御反应。"
    result = chunk_text(text, chunk_size=600, overlap=100)
    assert len(result) == 1
    assert result[0]["content"] == text


def test_overlap():
    """相邻 chunk 应有重叠"""
    text = "A" * 1000
    result = chunk_text(text, chunk_size=600, overlap=100)
    assert len(result) >= 2
    # 第二个 chunk 的开头应包含第一个 chunk 末尾的内容
    assert result[1]["content"][:100] == text[500:600]


def test_chunk_size():
    """每个 chunk 长度应约等于 chunk_size"""
    text = "知识" * 500  # 1000 字符
    result = chunk_text(text, chunk_size=600, overlap=100)
    for chunk in result:
        assert len(chunk["content"]) <= 700  # 允许一定偏差


def test_metadata():
    """每个 chunk 应包含元数据"""
    text = "测试内容" * 200
    result = chunk_text(text, chunk_size=600, overlap=100, metadata={"textbook": "生理学", "chapter": "第一章"})
    for chunk in result:
        assert "textbook" in chunk["metadata"]
        assert "chapter" in chunk["metadata"]


def test_zero_overlap():
    """overlap=0 时不应有重叠"""
    text = "A" * 1200
    result = chunk_text(text, chunk_size=600, overlap=0)
    assert len(result) == 2
    assert result[0]["content"] == "A" * 600
    assert result[1]["content"] == "A" * 600
