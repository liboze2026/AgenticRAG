import base64
import json
from typing import List
from backend.interfaces.generator import BaseGenerator
from backend.models.schemas import Answer, RetrievalResult
from backend.strategies import generator_registry

_CITATION_SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions based on the provided document pages. "
    "When referencing specific information from the pages, use citation markers like [1], [2], etc., "
    "where the number corresponds to the order in which the pages were provided. "
    "Be concise and accurate."
)


@generator_registry.register("claude")
class ClaudeGenerator(BaseGenerator):
    def __init__(self, client=None, model: str = "claude-sonnet-4-6", anthropic_api_key: str = "", generation_cache=None):
        if client is None:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=anthropic_api_key)
        self.client = client
        self.model = model
        self.generation_cache = generation_cache

    async def generate(self, query: str, context: List[RetrievalResult]) -> Answer:
        cache_key = self._cache_key(query, context)
        if self.generation_cache is not None:
            cached = self.generation_cache.get(cache_key)
            if cached is not None:
                return Answer(text=cached, sources=context)

        content = self._build_context_content(query, context)
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=_CITATION_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": content}],
        )
        text = response.content[0].text

        if self.generation_cache is not None:
            self.generation_cache.set(cache_key, text)
        return Answer(text=text, sources=context)

    async def generate_chat(self, messages: List[dict], context: List[RetrievalResult]) -> Answer:
        """Multi-turn chat: pass full history, inject pages into last user message."""
        if not messages:
            return Answer(text="", sources=context)

        anthropic_messages = []

        # All messages except the last pass through as plain text
        for msg in messages[:-1]:
            anthropic_messages.append({"role": msg["role"], "content": msg["content"]})

        # Last user message gets retrieved pages prepended
        last = messages[-1]
        content = self._build_context_content(last.get("content", ""), context)
        anthropic_messages.append({"role": "user", "content": content})

        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            system=_CITATION_SYSTEM_PROMPT,
            messages=anthropic_messages,
        )
        text = response.content[0].text
        return Answer(text=text, sources=context)

    def _cache_key(self, query: str, context: List[RetrievalResult]) -> str:
        sources = [f"{r.document_id}:{r.page_number}" for r in context]
        return f"claude:{self.model}:{query}:{json.dumps(sources)}"

    def _build_context_content(self, query: str, context: List[RetrievalResult]) -> list:
        content = []
        for i, result in enumerate(context, 1):
            content.append({"type": "text", "text": f"[Page {i}]"})
            try:
                with open(result.image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                content.append({
                    "type": "image",
                    "source": {"type": "base64", "media_type": "image/png", "data": b64},
                })
            except FileNotFoundError:
                pass
        content.append({
            "type": "text",
            "text": (
                f"Based on the document pages shown above, answer the question.\n"
                f"Use [1], [2], ... to cite specific pages.\n\nQuestion: {query}"
            ),
        })
        return content
