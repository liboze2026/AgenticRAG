import base64
import json
from typing import List, Optional
from backend.interfaces.generator import BaseGenerator
from backend.models.schemas import Answer, RetrievalResult
from backend.strategies import generator_registry


@generator_registry.register("openai_gpt4o")
class OpenAIGPT4oGenerator(BaseGenerator):
    def __init__(self, client=None, model: str = "gpt-4o", openai_api_key: str = "", generation_cache=None):
        if client is None:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=openai_api_key)
        self.client = client
        self.model = model
        self.generation_cache = generation_cache

    async def generate(self, query: str, context: List[RetrievalResult]) -> Answer:
        cache_key = self._cache_key(query, context)
        if self.generation_cache is not None:
            cached = self.generation_cache.get(cache_key)
            if cached is not None:
                return Answer(text=cached, sources=context)

        messages = self._build_messages(query, context)
        response = await self.client.chat.completions.create(model=self.model, messages=messages, max_tokens=2048)
        text = response.choices[0].message.content

        if self.generation_cache is not None:
            self.generation_cache.set(cache_key, text)
        return Answer(text=text, sources=context)

    def _cache_key(self, query: str, context: List[RetrievalResult]) -> str:
        sources = [f"{r.document_id}:{r.page_number}" for r in context]
        return f"openai:{self.model}:{query}:{json.dumps(sources)}"

    def _build_messages(self, query: str, context: List[RetrievalResult]) -> list:
        content = [{"type": "text", "text": f"Based on the following document pages, answer the question:\n\n{query}"}]
        for result in context:
            try:
                with open(result.image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
            except FileNotFoundError:
                continue
        return [{"role": "user", "content": content}]
