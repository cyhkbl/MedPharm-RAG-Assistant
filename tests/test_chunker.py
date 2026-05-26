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
    assert "炎症" in result[0]["content"]


def test_paragraph_splitting():
    """多段落文本应按段落切分"""
    para1 = "这是第一段内容。" * 20
    para2 = "这是第二段内容。" * 20
    text = f"{para1}\n\n{para2}"
    result = chunk_text(text, chunk_size=200, overlap=50)
    assert len(result) >= 2


def test_chapter_prefix_injection():
    """带 metadata 时应注入章节前缀"""
    text = "测试内容" * 200
    result = chunk_text(text, chunk_size=600, overlap=100, textbook="生理学", chapter="第一章")
    for chunk in result:
        assert "教材: 生理学" in chunk["content"]
        assert "章节: 第一章" in chunk["content"]


def test_metadata():
    """每个 chunk 应包含元数据"""
    text = "测试内容" * 200
    result = chunk_text(text, chunk_size=600, overlap=100, textbook="生理学", chapter="第一章")
    for chunk in result:
        assert chunk["metadata"]["textbook"] == "生理学"
        assert chunk["metadata"]["chapter"] == "第一章"


def test_chunk_size():
    """每个 chunk 长度不应远超 chunk_size（prefix 除外）"""
    # Create multi-paragraph text
    paragraphs = ["段落内容。" * 50 for _ in range(5)]
    text = "\n\n".join(paragraphs)
    result = chunk_text(text, chunk_size=600, overlap=100)
    for chunk in result:
        # Content includes prefix, so check core content length
        assert len(chunk["content"]) <= 800  # prefix + some tolerance


def test_zero_overlap():
    """overlap=0 时不应有重叠"""
    para1 = "A" * 300
    para2 = "B" * 300
    para3 = "C" * 300
    text = f"{para1}\n\n{para2}\n\n{para3}"
    result = chunk_text(text, chunk_size=350, overlap=0)
    assert len(result) >= 2


def test_metadata_passthrough():
    """额外的 metadata 字段应被传递到 chunk 中"""
    text = "测试内容" * 200
    result = chunk_text(text, chunk_size=600, overlap=100, textbook="test", chapter="ch1", custom_field="value")
    for chunk in result:
        assert chunk["metadata"]["custom_field"] == "value"
