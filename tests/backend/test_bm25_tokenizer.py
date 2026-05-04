"""Unit tests for the bilingual BM25 tokenizer."""
from backend.strategies.retrievers.bm25 import _tokenize


def test_english_words():
    out = _tokenize("The Attention Mechanism uses softmax")
    assert "attention" in out
    assert "mechanism" in out
    assert "softmax" in out
    # Single-char latin tokens filtered (regex requires 2+ chars)


def test_chinese_unigrams_and_bigrams():
    out = _tokenize("文档结构化解析")
    # Unigrams
    assert "文" in out
    assert "档" in out
    assert "解" in out
    # Bigrams
    assert "文档" in out
    assert "结构" in out
    assert "解析" in out


def test_mixed_chinese_and_english():
    out = _tokenize("ColPali 文档检索")
    assert "colpali" in out
    assert "文档" in out
    assert "档检" in out


def test_empty():
    assert _tokenize("") == []
    assert _tokenize(None) == []


def test_punctuation_stripped():
    out = _tokenize("hello, world! 文档。结构")
    assert "hello" in out
    assert "world" in out
    assert "文档" in out
    assert "结构" in out


def test_overlap_query_doc_chinese():
    """Verify that BM25 over the same Chinese phrase produces overlap."""
    doc_tokens = set(_tokenize("本文研究复杂文档结构化解析方法"))
    query_tokens = set(_tokenize("文档结构化"))
    # Should have non-empty intersection (was empty before fix)
    assert doc_tokens & query_tokens
