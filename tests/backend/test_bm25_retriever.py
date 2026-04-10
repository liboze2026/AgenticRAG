import pytest
from unittest.mock import patch
from backend.strategies.retrievers.bm25 import BM25Retriever, _tokenize, _BM25_AVAILABLE


def test_tokenize():
    assert _tokenize("Hello, World! 123") == ["hello", "world", "123"]


@pytest.mark.skipif(not _BM25_AVAILABLE, reason="rank-bm25 not installed")
@pytest.mark.asyncio
async def test_index_and_retrieve_text():
    retriever = BM25Retriever()
    # Patch text extraction so we don't need a real PDF
    with patch("backend.strategies.retrievers.bm25._extract_page_text") as mock_ex:
        mock_ex.side_effect = lambda path, page: {
            ("/a.pdf", 1): "transformer attention mechanism",
            ("/a.pdf", 2): "convolutional neural network",
            ("/b.pdf", 1): "attention is all you need",
        }[(path, page)]
        await retriever.index("a", 1, [], "/a/p1.png", pdf_path="/a.pdf")
        await retriever.index("a", 2, [], "/a/p2.png", pdf_path="/a.pdf")
        await retriever.index("b", 1, [], "/b/p1.png", pdf_path="/b.pdf")

    results = await retriever.retrieve_text("attention", top_k=3)
    assert len(results) >= 2
    docs = {r.document_id for r in results}
    assert "a" in docs
    assert "b" in docs


@pytest.mark.asyncio
async def test_delete_removes_doc():
    retriever = BM25Retriever()
    with patch("backend.strategies.retrievers.bm25._extract_page_text", return_value="text"):
        await retriever.index("a", 1, [], "/a.png", pdf_path="/a.pdf")
        await retriever.index("b", 1, [], "/b.png", pdf_path="/b.pdf")
    assert len(retriever._docs) == 2
    await retriever.delete("a")
    assert len(retriever._docs) == 1
    assert retriever._docs[0]["doc_id"] == "b"
