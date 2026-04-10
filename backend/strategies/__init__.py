"""Global strategy registries. Import this module to trigger all strategy registrations."""
from backend.core.registry import Registry

processor_registry = Registry("processor")
document_encoder_registry = Registry("document_encoder")
query_encoder_registry = Registry("query_encoder")
retriever_registry = Registry("retriever")
reranker_registry = Registry("reranker")
generator_registry = Registry("generator")

ALL_REGISTRIES = {
    "processor": processor_registry,
    "document_encoder": document_encoder_registry,
    "query_encoder": query_encoder_registry,
    "retriever": retriever_registry,
    "reranker": reranker_registry,
    "generator": generator_registry,
}


def import_all_strategies():
    """Import all strategy modules to trigger registration decorators."""
    import backend.strategies.processors  # noqa: F401
    import backend.strategies.encoders    # noqa: F401
    import backend.strategies.retrievers  # noqa: F401
    import backend.strategies.rerankers   # noqa: F401
    import backend.strategies.generators  # noqa: F401
