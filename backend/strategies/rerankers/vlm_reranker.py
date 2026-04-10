import asyncio
import re
from typing import List, Optional

from backend.interfaces.reranker import BaseReranker
from backend.interfaces.generator import BaseGenerator
from backend.models.schemas import RetrievalResult
from backend.strategies import reranker_registry


@reranker_registry.register("vlm_reranker")
class VLMReranker(BaseReranker):
    """Rerank retrieval results by asking a multimodal LLM to score each (query, page).

    The base_generator is the same kind of object used in the generator stage,
    but here we use it to *score* (query, page) pairs.

    We send each page individually to the LLM with a prompt like:
        "On a scale of 0-10, how relevant is this page to: {query}? Respond with just the number."
    """

    def __init__(
        self,
        base_generator: Optional[BaseGenerator] = None,
        max_concurrent: int = 4,
    ):
        self.base_generator = base_generator
        self.max_concurrent = max_concurrent

    async def rerank(self, query: str, results: List[RetrievalResult], top_k: int = 5) -> List[RetrievalResult]:
        if not results:
            return results
        if self.base_generator is None:
            return results[:top_k]

        sem = asyncio.Semaphore(self.max_concurrent)

        async def score_one(r: RetrievalResult) -> float:
            async with sem:
                prompt = (
                    f"Question: {query}\n\n"
                    "On a scale from 0 to 10, how relevant is the page shown to answering the question? "
                    "Respond with ONLY a single integer between 0 and 10."
                )
                try:
                    answer = await self.base_generator.generate(prompt, [r])
                    return _parse_score(answer.text)
                except Exception:
                    return 0.0

        scores = await asyncio.gather(*[score_one(r) for r in results])
        scored = list(zip(results, scores))
        scored.sort(key=lambda x: x[1], reverse=True)
        # Reconstruct results with new scores
        reranked = []
        for r, s in scored[:top_k]:
            reranked.append(RetrievalResult(
                document_id=r.document_id,
                page_number=r.page_number,
                score=s,
                image_path=r.image_path,
            ))
        return reranked


def _parse_score(text: str) -> float:
    """Extract a 0-10 score from LLM response."""
    if not text:
        return 0.0
    match = re.search(r"\d+(\.\d+)?", text)
    if not match:
        return 0.0
    try:
        return float(match.group())
    except ValueError:
        return 0.0
