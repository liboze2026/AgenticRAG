import base64
import json
import logging
from typing import List, Optional

from backend.interfaces.generator import BaseGenerator
from backend.models.schemas import Answer, RetrievalResult
from backend.strategies import generator_registry

logger = logging.getLogger(__name__)

_CITATION_SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions based on the provided document pages. "
    "When referencing specific information from the pages, use citation markers like [1], [2], etc., "
    "where the number corresponds to the order in which the pages were provided. "
    "Be concise and accurate."
)

# GLM-4V models (e.g. glm-4v-flash, glm-4v-plus, glm-4.6v) support vision.
# Reasoning-capable models (4.5, 4.5-air, 4.6v) consume max_tokens for hidden
# reasoning tokens, so the limit is bumped accordingly.
_VISION_MODEL_PREFIXES = ("glm-4v", "glm-4.6v")
_DEFAULT_MAX_TOKENS = 2048


def _is_vision(model: str) -> bool:
    return any(model.startswith(p) for p in _VISION_MODEL_PREFIXES)


@generator_registry.register("zhipu")
class ZhipuGenerator(BaseGenerator):
    """Zhipu (BigModel) generator with model-level fallback.

    The first call always uses `model`. If it raises (rate-limited, 5xx,
    timeout, network error, …) the call is retried against each entry in
    `fallback_models` in order. The final exception is re-raised when every
    model fails. This gives the demo a soft landing when the primary
    paid/reasoning model hiccups: it falls back to the free flash model
    instead of erroring at the user.
    """

    def __init__(
        self,
        client=None,
        model: str = "glm-4.6v",
        fallback_models: Optional[List[str]] = None,
        zhipu_api_key: str = "",
        generation_cache=None,
        max_tokens: int = _DEFAULT_MAX_TOKENS,
    ):
        if client is None:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(
                api_key=zhipu_api_key,
                base_url="https://open.bigmodel.cn/api/paas/v4/",
            )
        self.client = client
        self.model = model
        self.fallback_models = list(fallback_models or [])
        self.generation_cache = generation_cache
        self.max_tokens = max_tokens
        # Vision capability is per-call (depends on which model handled the
        # request), so this attribute reflects the *primary* model only and is
        # used to decide whether to attach images to the payload.
        self._vision = _is_vision(model)

    async def _create_with_fallback(self, messages: list) -> str:
        """Try primary model, then each fallback in order. Returns text or raises."""
        chain = [self.model, *self.fallback_models]
        last_exc: Optional[BaseException] = None
        for idx, model in enumerate(chain):
            tag = "primary" if idx == 0 else f"fallback#{idx}"
            try:
                response = await self.client.chat.completions.create(
                    model=model, messages=messages, max_tokens=self.max_tokens,
                )
                text = (response.choices[0].message.content or "").strip()
                # Some reasoning models (glm-4.6v, glm-4.5*) emit empty content
                # when max_tokens is fully consumed by hidden reasoning. Treat
                # an empty reply as a soft failure and fall through to the
                # next model rather than returning a blank answer to the user.
                if not text:
                    usage = getattr(response, "usage", None)
                    raise RuntimeError(
                        f"empty reply from {model} (usage={usage!r}; "
                        f"likely max_tokens={self.max_tokens} exhausted by hidden reasoning)"
                    )
                if idx > 0:
                    logger.warning("zhipu generator served by %s [%s] after primary failed",
                                   model, tag)
                else:
                    logger.info("zhipu generator served by %s [%s] OK", model, tag)
                return text
            except Exception as e:
                last_exc = e
                logger.warning("zhipu [%s=%s] failed: %s: %s",
                               tag, model, type(e).__name__, str(e)[:200])
        raise last_exc if last_exc else RuntimeError("zhipu generate failed")

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
        text = await self._create_with_fallback(messages)

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
        text = await self._create_with_fallback(chat_messages)
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
