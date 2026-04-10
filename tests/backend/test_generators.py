import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.strategies.generators.openai_gpt4o import OpenAIGPT4oGenerator
from backend.strategies.generators.claude import ClaudeGenerator
from backend.models.schemas import RetrievalResult


def _make_context():
    return [RetrievalResult(document_id="doc1", page_number=1, score=0.9, image_path="/img/p1.png")]


@pytest.mark.asyncio
async def test_openai_generator():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="The answer is 42."))]
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
    generator = OpenAIGPT4oGenerator(client=mock_client, model="gpt-4o")
    answer = await generator.generate("What is the answer?", _make_context())
    assert answer.text == "The answer is 42."
    assert len(answer.sources) == 1


@pytest.mark.asyncio
async def test_claude_generator():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Claude says 42.")]
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)
    generator = ClaudeGenerator(client=mock_client, model="claude-sonnet-4-6-20250514")
    answer = await generator.generate("What is the answer?", _make_context())
    assert answer.text == "Claude says 42."
    assert len(answer.sources) == 1
