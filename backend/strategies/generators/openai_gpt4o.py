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

        messages = [
            {"role": "system", "content": _CITATION_SYSTEM_PROMPT},
            {"role": "user", "content": self._build_content(query, context)},
        ]
        response = await self.client.chat.completions.create(
            model=self.model, messages=messages, max_tokens=2048
        )
        if not response.choices:
            raise RuntimeError("OpenAI 返回空 choices")
        text = response.choices[0].message.content or ""

        if self.generation_cache is not None:
            self.generation_cache.set(cache_key, text)
        return Answer(text=text, sources=context)

    async def generate_chat(self, messages: List[dict], context: List[RetrievalResult]) -> Answer:
        """Multi-turn chat: inject retrieved pages into the last user message."""
        if not messages:
            return Answer(text="", sources=context)

        openai_messages = [{"role": "system", "content": _CITATION_SYSTEM_PROMPT}]

        # All messages except the last user turn pass through as text
        for msg in messages[:-1]:
            openai_messages.append({"role": msg["role"], "content": msg["content"]})

        # Last user message gets the retrieved page images injected
        last = messages[-1]
        content = self._build_content(last.get("content", ""), context)
        openai_messages.append({"role": "user", "content": content})

        response = await self.client.chat.completions.create(
            model=self.model, messages=openai_messages, max_tokens=2048
        )
        if not response.choices:
            raise RuntimeError("OpenAI 返回空 choices")
        text = response.choices[0].message.content or ""
        return Answer(text=text, sources=context)

    def _cache_key(self, query: str, context: List[RetrievalResult]) -> str:
        sources = [f"{r.document_id}:{r.page_number}" for r in context]
        return f"openai:{self.model}:{query}:{json.dumps(sources)}"

    def _build_content(self, query: str, context: List[RetrievalResult]) -> list:
        content = [{"type": "text", "text": (
            f"Based on the following document pages, answer the question.\n"
            f"Use [1], [2], ... to cite specific pages.\n\nQuestion: {query}"
        )}]
        for i, result in enumerate(context, 1):
            content.append({"type": "text", "text": f"[Page {i}]"})
            try:
                with open(result.image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
            except (FileNotFoundError, PermissionError, OSError):
                pass
        return content
