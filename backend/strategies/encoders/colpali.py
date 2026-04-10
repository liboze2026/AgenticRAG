from typing import List, Optional
from backend.interfaces.encoder import BaseEncoder
from backend.models.schemas import Embedding, PageImage
from backend.services.worker_client import WorkerClient
from backend.strategies import document_encoder_registry, query_encoder_registry


def _kmeans_pool(vectors, k, max_iters=10, seed=42):
    """Simple k-means pooling with no external deps. Returns k centroid vectors."""
    import random
    random.seed(seed)
    n = len(vectors)
    if n <= k:
        return vectors
    # Initialize centroids by selecting k evenly-spaced vectors
    indices = [int(i * n / k) for i in range(k)]
    centroids = [list(vectors[i]) for i in indices]
    dim = len(vectors[0])

    def dist_sq(a, b):
        return sum((x - y) ** 2 for x, y in zip(a, b))

    for _ in range(max_iters):
        # Assign each vector to nearest centroid
        assignments = []
        for v in vectors:
            best = 0
            best_d = dist_sq(v, centroids[0])
            for ci in range(1, k):
                d = dist_sq(v, centroids[ci])
                if d < best_d:
                    best_d = d
                    best = ci
            assignments.append(best)
        # Recompute centroids
        new_centroids = [[0.0] * dim for _ in range(k)]
        counts = [0] * k
        for v, a in zip(vectors, assignments):
            for d_i in range(dim):
                new_centroids[a][d_i] += v[d_i]
            counts[a] += 1
        for ci in range(k):
            if counts[ci] > 0:
                new_centroids[ci] = [x / counts[ci] for x in new_centroids[ci]]
            else:
                new_centroids[ci] = centroids[ci]
        centroids = new_centroids
    return centroids


def _mean_pool(vectors):
    if not vectors:
        return vectors
    dim = len(vectors[0])
    n = len(vectors)
    summed = [0.0] * dim
    for v in vectors:
        for i in range(dim):
            summed[i] += v[i]
    return [[s / n for s in summed]]


@document_encoder_registry.register("colpali")
@query_encoder_registry.register("colpali")
class ColPaliEncoder(BaseEncoder):
    def __init__(
        self,
        worker_client: Optional[WorkerClient] = None,
        batch_size: int = 8,
        model_name: str = "vidore/colpali-v1.2",
        pool_strategy: Optional[str] = None,
        num_clusters: int = 32,
        query_cache=None,  # optional DiskCache
    ):
        self.worker_client = worker_client
        self.batch_size = batch_size
        self.model_name = model_name
        self.pool_strategy = pool_strategy
        self.num_clusters = num_clusters
        self.query_cache = query_cache

    def _pool(self, vectors):
        if self.pool_strategy == "mean":
            return _mean_pool(vectors)
        if self.pool_strategy == "kmeans":
            return _kmeans_pool(vectors, self.num_clusters)
        return vectors

    async def encode_documents(self, pages: List[PageImage]) -> List[Embedding]:
        if not pages:
            return []
        embeddings = []
        for batch_start in range(0, len(pages), self.batch_size):
            batch = pages[batch_start:batch_start + self.batch_size]
            image_paths = [p.image_path for p in batch]
            raw = await self.worker_client.encode_documents(image_paths)
            for page, r in zip(batch, raw):
                pooled = self._pool(r["vectors"])
                embeddings.append(Embedding(
                    document_id=page.document_id,
                    page_number=page.page_number,
                    vectors=pooled,
                ))
        return embeddings

    async def encode_query(self, query: str) -> List[List[float]]:
        if self.query_cache is not None:
            cached = self.query_cache.get(f"colpali:{self.model_name}:{query}")
            if cached is not None:
                return cached
        vectors = await self.worker_client.encode_query(query)
        if self.query_cache is not None:
            self.query_cache.set(f"colpali:{self.model_name}:{query}", vectors)
        return vectors
