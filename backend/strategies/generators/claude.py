import base64
from typing import List
from backend.interfaces.generator import BaseGenerator
from backend.models.schemas import Answer, RetrievalResult
from backend.strategies import generator_registry


@generator_registry.register("claude")
class ClaudeGenerator(BaseGenerator):
    def __init__(self, client=None, model: str = "claude-sonnet-4-6-20250514", anthropic_api_key: str = ""):
        if client is None:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=anthropic_api_key)
        self.client = client
        self.model = model

    async def generate(self, query: str, context: List[RetrievalResult]) -> Answer:
        content = self._build_content(query, context)
        response = await self.client.messages.create(model=self.model, max_tokens=2048, messages=[{"role": "user", "content": content}])
        text = response.content[0].text
        return Answer(text=text, sources=context)

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
