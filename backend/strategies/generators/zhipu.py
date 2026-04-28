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

# GLM-4V models (e.g. glm-4v-flash, glm-4v-plus) support vision.
# Text-only models (e.g. glm-4.5-air) will fall back to page-reference text only.
_VISION_MODEL_PREFIXES = ("glm-4v",)


@generator_registry.register("zhipu")
class ZhipuGenerator(BaseGenerator):
    def __init__(self, client=None, model: str = "glm-4.5-air", zhipu_api_key: str = "", generation_cache=None):
        if client is None:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=zhipu_api_key,
                base_url="https://open.bigmodel.cn/api/paas/v4/",
            )
        self.client = client
        self.model = model
        self.generation_cache = generation_cache
        self._vision = any(model.startswith(p) for p in _VISION_MODEL_PREFIXES)

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
            model=self.model, messages=messages, max_tokens=1024
        )
        text = response.choices[0].message.content

        if self.generation_cache is not None:
            self.generation_cache.set(cache_key, text)
        return Answer(text=text, sources=context)

    async def generate_chat(self, messages: List[dict], context: List[RetrievalResult]) -> Answer:
        if not messages:
            return Answer(text="", sources=context)

        # Zhipu GLM-4V rejects some mixed multi-turn + multimodal payloads with
        # code 1210. Preserve conversation context by folding prior turns into
        # the current user prompt, then attach retrieved pages only once.
        content = self._build_content(self._build_chat_query(messages), context)
        chat_messages = [
            {"role": "system", "content": _CITATION_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ]

        response = await self.client.chat.completions.create(
            model=self.model, messages=chat_messages, max_tokens=1024
        )
        text = response.choices[0].message.content
        return Answer(text=text, sources=context)

    def _cache_key(self, query: str, context: List[RetrievalResult]) -> str:
        sources = [f"{r.document_id}:{r.page_number}" for r in context]
        return f"zhipu:{self.model}:{query}:{json.dumps(sources)}"

    def _build_chat_query(self, messages: List[dict]) -> str:
        turns = [
            (msg.get("role"), str(msg.get("content", "")).strip())
            for msg in messages
            if msg.get("role") in {"user", "assistant"} and str(msg.get("content", "")).strip()
        ]
        last_user_idx = next((idx for idx in range(len(turns) - 1, -1, -1) if turns[idx][0] == "user"), None)
        if last_user_idx is None:
            return ""
        last_user = turns[last_user_idx][1]
        if not last_user:
            return ""

        history = turns[:last_user_idx]
        if not history:
            return last_user

        lines = ["Conversation history:"]
        for role, content in history[-8:]:
            label = "User" if role == "user" else "Assistant"
            lines.append(f"{label}: {content}")
        lines.append("")
        lines.append(f"Current question: {last_user}")
        return "\n".join(lines)

    def _build_content(self, query: str, context: List[RetrievalResult]) -> list:
        content = [{"type": "text", "text": (
            f"Based on the following document pages, answer the question.\n"
            f"Use [1], [2], ... to cite specific pages.\n\nQuestion: {query}"
        )}]
        for i, result in enumerate(context, 1):
            content.append({"type": "text", "text": f"[Page {i}]"})
            if self._vision:
                try:
                    with open(result.image_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    content.append({"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}})
                except FileNotFoundError:
                    pass
            else:
                content.append({"type": "text", "text": f"(doc: {result.document_id}, page: {result.page_number})"})
        return content
