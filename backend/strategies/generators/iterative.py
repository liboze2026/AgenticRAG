import re
from typing import List, Optional

from backend.interfaces.generator import BaseGenerator
from backend.models.schemas import Answer, RetrievalResult
from backend.strategies import generator_registry


@generator_registry.register("iterative")
class IterativeGenerator(BaseGenerator):
    """Wraps a base generator to support self-reflective multi-round generation.

    Round 1: ask for an answer + a confidence rating.
    If confidence < threshold, ask for a refined sub-query, retrieve more, regenerate.

    Note: this generator needs access to a retriever to do follow-up retrieval.
    Wired via DI as `iterative_retriever` and `iterative_query_encoder`.
    """

    def __init__(
        self,
        base_generator: Optional[BaseGenerator] = None,
        iterative_retriever=None,
        iterative_query_encoder=None,
        max_iterations: int = 2,
        confidence_threshold: float = 0.7,
        top_k: int = 5,
    ):
        self.base_generator = base_generator
        self.iterative_retriever = iterative_retriever
        self.iterative_query_encoder = iterative_query_encoder
        self.max_iterations = max_iterations
        self.confidence_threshold = confidence_threshold
        self.top_k = top_k

    async def generate(self, query: str, context: List[RetrievalResult]) -> Answer:
        if self.base_generator is None:
            return Answer(text="", sources=context)

        current_context = list(context)
        text = ""

        for iteration in range(self.max_iterations):
            prompt = (
                f"{query}\n\n"
                "Answer the question using the provided pages. After your answer, on a new line, "
                "write 'CONFIDENCE: X' where X is between 0.0 and 1.0 reflecting your certainty. "
                "If you cannot answer confidently, on another new line write "
                "'NEED_INFO: <a focused follow-up question>'."
            )
            answer = await self.base_generator.generate(prompt, current_context)
            text = answer.text

            confidence = _parse_confidence(text)
            need_info = _parse_need_info(text)

            if confidence >= self.confidence_threshold or not need_info or iteration == self.max_iterations - 1:
                # Final
                return Answer(
                    text=_strip_metadata(text),
                    sources=current_context,
                    timing={"iterations": float(iteration + 1)},
                )

            # Retrieve more for the follow-up question
            if self.iterative_retriever and self.iterative_query_encoder:
                vectors = await self.iterative_query_encoder.encode_query(need_info)
                if hasattr(self.iterative_retriever, "set_query"):
                    self.iterative_retriever.set_query(need_info)
                more_results = await self.iterative_retriever.retrieve(vectors, top_k=self.top_k)
                # Append non-duplicate results to context
                seen = {(r.document_id, r.page_number) for r in current_context}
                for r in more_results:
                    key = (r.document_id, r.page_number)
                    if key not in seen:
                        current_context.append(r)
                        seen.add(key)

        return Answer(text=text, sources=current_context, timing={"iterations": float(self.max_iterations)})


def _parse_confidence(text: str) -> float:
    match = re.search(r"CONFIDENCE\s*:\s*([0-9]*\.?[0-9]+)", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return 0.0


def _parse_need_info(text: str) -> Optional[str]:
    match = re.search(r"NEED_INFO\s*:\s*(.+)", text)
    if match:
        return match.group(1).strip()
    return None


def _strip_metadata(text: str) -> str:
    """Remove CONFIDENCE and NEED_INFO lines from final answer."""
    lines = []
    for line in text.split("\n"):
        if "CONFIDENCE:" in line or "NEED_INFO:" in line:
            continue
        lines.append(line)
    return "\n".join(lines).strip()
