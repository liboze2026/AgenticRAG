import base64
import json
from typing import List, Optional
from backend.interfaces.generator import BaseGenerator
from backend.models.schemas import Answer, RetrievalResult
from backend.strategies import generator_registry


@generator_registry.register("claude")
class ClaudeGenerator(BaseGenerator):
    def __init__(self, client=None, model: str = "claude-sonnet-4-6-20250514", anthropic_api_key: str = "", generation_cache=None):
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

        content = self._build_content(query, context)
        response = await self.client.messages.create(model=self.model, max_tokens=2048, messages=[{"role": "user", "content": content}])
        text = response.content[0].text

        if self.generation_cache is not None:
            self.generation_cache.set(cache_key, text)
        return Answer(text=text, sources=context)

    def _cache_key(self, query: str, context: List[RetrievalResult]) -> str:
        sources = [f"{r.document_id}:{r.page_number}" for r in context]
        return f"claude:{self.model}:{query}:{json.dumps(sources)}"

    def _build_content(self, query: str, context: List[RetrievalResult]) -> list:
        content = []
        for result in context:
            try:
                with open(result.image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                content.append({"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": b64}})
            except FileNotFoundError:
                continue
        content.append({"type": "text", "text": f"Based on the document pages shown above, answer the question:\n\n{query}"})
        return content
