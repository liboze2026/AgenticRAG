# Multimodal Retrieval System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a modular, pluggable multimodal document retrieval and reasoning prototype system with a FastAPI backend, Vue 3 frontend, and remote GPU worker, based on a dual-tower architecture.

**Architecture:** Dual-tower pipeline with abstract interfaces at each layer (Processor, Encoder, Retriever, Reranker, Generator). Strategies are registered via decorators and assembled from YAML config. The backend orchestrates requests, delegating GPU-intensive encoding to a remote Worker via SSH-tunneled HTTP. Qdrant stores multi-vectors on the remote server.

**Tech Stack:** Python 3.11+, FastAPI, Qdrant, Vue 3 (Vite + TypeScript), PyYAML, httpx, Pydantic, pdf2image/PyMuPDF

---

## File Structure

```
agent/
├── config/
│   └── default.yaml                          # Default pipeline + connection config
├── backend/
│   ├── __init__.py
│   ├── main.py                               # FastAPI app entry, lifespan, CORS
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py                         # Load & validate YAML config
│   │   ├── registry.py                       # Strategy registry + decorators
│   │   └── pipeline.py                       # Pipeline assembler & runner
│   ├── interfaces/
│   │   ├── __init__.py
│   │   ├── processor.py                      # BaseProcessor ABC
│   │   ├── encoder.py                        # BaseEncoder ABC (dual-tower)
│   │   ├── retriever.py                      # BaseRetriever ABC
│   │   ├── reranker.py                       # BaseReranker ABC
│   │   └── generator.py                      # BaseGenerator ABC
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py                        # Pydantic models for API & internal
│   ├── strategies/
│   │   ├── __init__.py                       # Auto-import all strategies
│   │   ├── processors/
│   │   │   ├── __init__.py
│   │   │   └── page_screenshot.py            # PDF -> page images
│   │   ├── encoders/
│   │   │   ├── __init__.py
│   │   │   └── colpali.py                    # ColPali encoder (calls Worker)
│   │   ├── retrievers/
│   │   │   ├── __init__.py
│   │   │   └── multi_vector.py               # Qdrant multi-vector retrieval
│   │   ├── rerankers/
│   │   │   └── __init__.py
│   │   └── generators/
│   │       ├── __init__.py
│   │       ├── openai_gpt4o.py               # GPT-4o generator
│   │       └── claude.py                     # Claude generator
│   ├── services/
│   │   ├── __init__.py
│   │   ├── document_service.py               # Document CRUD + indexing orchestration
│   │   ├── worker_client.py                  # HTTP client to remote Worker
│   │   └── evaluation.py                     # Recall@K, MRR computation
│   └── api/
│       ├── __init__.py
│       ├── documents.py                      # Document management routes
│       ├── query.py                          # Query & retrieve routes
│       ├── experiments.py                    # Pipeline switch & evaluation routes
│       └── system.py                         # Health check route
├── worker/
│   ├── __init__.py
│   ├── main.py                               # Worker FastAPI entry
│   ├── model_manager.py                      # Load/cache models
│   └── endpoints/
│       ├── __init__.py
│       └── encode.py                         # /encode/documents, /encode/query
├── frontend/                                 # Vue 3 + Vite + TypeScript
│   ├── package.json
│   ├── vite.config.ts
│   ├── tsconfig.json
│   ├── index.html
│   └── src/
│       ├── main.ts
│       ├── App.vue
│       ├── router/
│       │   └── index.ts
│       ├── api/
│       │   └── client.ts                     # Axios API client
│       ├── views/
│       │   ├── DocumentsView.vue
│       │   ├── QueryView.vue
│       │   ├── ExperimentView.vue
│       │   └── SystemView.vue
│       └── components/
│           ├── DocumentUpload.vue
│           ├── DocumentList.vue
│           ├── QueryInput.vue
│           ├── AnswerDisplay.vue
│           ├── EvidencePanel.vue
│           ├── PipelineSelector.vue
│           └── EvalResults.vue
├── scripts/
│   ├── start_tunnel.sh
│   └── deploy_worker.sh
├── tests/
│   ├── __init__.py
│   ├── backend/
│   │   ├── __init__.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── test_config.py
│   │   │   ├── test_registry.py
│   │   │   └── test_pipeline.py
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── test_document_service.py
│   │   │   └── test_evaluation.py
│   │   └── api/
│   │       ├── __init__.py
│   │       ├── test_documents.py
│   │       ├── test_query.py
│   │       ├── test_experiments.py
│   │       └── test_system.py
│   └── worker/
│       ├── __init__.py
│       └── test_encode.py
├── requirements.txt
└── README.md
```

---

## Task 1: Project Scaffolding & Config

**Files:**
- Create: `backend/__init__.py`, `backend/core/__init__.py`, `backend/interfaces/__init__.py`, `backend/models/__init__.py`, `backend/strategies/__init__.py`, `backend/strategies/processors/__init__.py`, `backend/strategies/encoders/__init__.py`, `backend/strategies/retrievers/__init__.py`, `backend/strategies/rerankers/__init__.py`, `backend/strategies/generators/__init__.py`, `backend/services/__init__.py`, `backend/api/__init__.py`, `worker/__init__.py`, `worker/endpoints/__init__.py`, `tests/__init__.py`, `tests/backend/__init__.py`, `tests/backend/core/__init__.py`, `tests/backend/services/__init__.py`, `tests/backend/api/__init__.py`, `tests/worker/__init__.py`
- Create: `config/default.yaml`
- Create: `backend/core/config.py`
- Create: `requirements.txt`
- Test: `tests/backend/core/test_config.py`

- [ ] **Step 1: Create all `__init__.py` files and `requirements.txt`**

```bash
mkdir -p backend/core backend/interfaces backend/models backend/strategies/processors backend/strategies/encoders backend/strategies/retrievers backend/strategies/rerankers backend/strategies/generators backend/services backend/api
mkdir -p worker/endpoints
mkdir -p tests/backend/core tests/backend/services tests/backend/api tests/worker
```

Create empty `__init__.py` in every package directory listed above.

Create `requirements.txt`:

```
fastapi==0.115.6
uvicorn[standard]==0.34.0
pydantic==2.10.4
pyyaml==6.0.2
httpx==0.28.1
python-multipart==0.0.20
qdrant-client==1.13.3
pdf2image==1.17.0
Pillow==11.1.0
openai==1.59.7
anthropic==0.43.0
pytest==8.3.4
pytest-asyncio==0.25.0
```

- [ ] **Step 2: Create default config YAML**

Create `config/default.yaml`:

```yaml
server:
  host: "0.0.0.0"
  port: 8000

worker:
  host: "localhost"
  port: 8001
  timeout: 120

qdrant:
  host: "localhost"
  port: 6333
  collection_name: "documents"

storage:
  upload_dir: "data/uploads"
  images_dir: "data/images"

pipeline:
  processor: "page_screenshot"
  document_encoder: "colpali"
  query_encoder: "colpali"
  retriever: "multi_vector"
  reranker: null
  generator: "openai_gpt4o"

ssh_tunnel:
  enabled: true
  pem_path: "~/.ssh/key.pem"
  bastion: "user@bastion-host"
  target: "user@gpu-server"
  forwards:
    - local: 8001
      remote: 8001
    - local: 6333
      remote: 6333

api_keys:
  openai: "${OPENAI_API_KEY}"
  anthropic: "${ANTHROPIC_API_KEY}"
```

- [ ] **Step 3: Write failing test for config loading**

Create `tests/backend/core/test_config.py`:

```python
import os
import pytest
from backend.core.config import load_config, AppConfig


def test_load_config_from_file(tmp_path):
    config_file = tmp_path / "test.yaml"
    config_file.write_text("""
server:
  host: "0.0.0.0"
  port: 8000
worker:
  host: "localhost"
  port: 8001
  timeout: 120
qdrant:
  host: "localhost"
  port: 6333
  collection_name: "documents"
storage:
  upload_dir: "data/uploads"
  images_dir: "data/images"
pipeline:
  processor: "page_screenshot"
  document_encoder: "colpali"
  query_encoder: "colpali"
  retriever: "multi_vector"
  reranker: null
  generator: "openai_gpt4o"
api_keys:
  openai: "test-key"
  anthropic: "test-key"
""")
    config = load_config(str(config_file))
    assert isinstance(config, AppConfig)
    assert config.server.port == 8000
    assert config.pipeline.document_encoder == "colpali"
    assert config.pipeline.reranker is None
    assert config.qdrant.collection_name == "documents"


def test_load_config_env_substitution(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-123")
    config_file = tmp_path / "test.yaml"
    config_file.write_text("""
server:
  host: "0.0.0.0"
  port: 8000
worker:
  host: "localhost"
  port: 8001
  timeout: 120
qdrant:
  host: "localhost"
  port: 6333
  collection_name: "documents"
storage:
  upload_dir: "data/uploads"
  images_dir: "data/images"
pipeline:
  processor: "page_screenshot"
  document_encoder: "colpali"
  query_encoder: "colpali"
  retriever: "multi_vector"
  reranker: null
  generator: "openai_gpt4o"
api_keys:
  openai: "${OPENAI_API_KEY}"
  anthropic: ""
""")
    config = load_config(str(config_file))
    assert config.api_keys.openai == "sk-test-123"


def test_load_config_missing_file():
    with pytest.raises(FileNotFoundError):
        load_config("/nonexistent/path.yaml")
```

- [ ] **Step 4: Run test to verify it fails**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/core/test_config.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'backend.core.config'`

- [ ] **Step 5: Implement config module**

Create `backend/core/config.py`:

```python
import os
import re
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000


class WorkerConfig(BaseModel):
    host: str = "localhost"
    port: int = 8001
    timeout: int = 120


class QdrantConfig(BaseModel):
    host: str = "localhost"
    port: int = 6333
    collection_name: str = "documents"


class StorageConfig(BaseModel):
    upload_dir: str = "data/uploads"
    images_dir: str = "data/images"


class PipelineConfig(BaseModel):
    processor: str = "page_screenshot"
    document_encoder: str = "colpali"
    query_encoder: str = "colpali"
    retriever: str = "multi_vector"
    reranker: Optional[str] = None
    generator: str = "openai_gpt4o"


class ApiKeysConfig(BaseModel):
    openai: str = ""
    anthropic: str = ""


class AppConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    worker: WorkerConfig = WorkerConfig()
    qdrant: QdrantConfig = QdrantConfig()
    storage: StorageConfig = StorageConfig()
    pipeline: PipelineConfig = PipelineConfig()
    api_keys: ApiKeysConfig = ApiKeysConfig()


def _substitute_env_vars(text: str) -> str:
    """Replace ${VAR_NAME} with environment variable values."""
    def replacer(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))
    return re.sub(r"\$\{([^}]+)\}", replacer, text)


def load_config(path: str) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    raw = config_path.read_text(encoding="utf-8")
    raw = _substitute_env_vars(raw)
    data = yaml.safe_load(raw)
    return AppConfig(**data)
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/core/test_config.py -v
```

Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git init
git add config/ backend/ worker/ tests/ requirements.txt
git commit -m "feat: project scaffolding with config loading"
```

---

## Task 2: Strategy Registry

**Files:**
- Create: `backend/core/registry.py`
- Test: `tests/backend/core/test_registry.py`

- [ ] **Step 1: Write failing test**

Create `tests/backend/core/test_registry.py`:

```python
import pytest
from backend.core.registry import Registry


def test_register_and_get():
    registry = Registry("encoder")
    
    @registry.register("test_encoder")
    class TestEncoder:
        pass
    
    cls = registry.get("test_encoder")
    assert cls is TestEncoder


def test_get_unregistered_raises():
    registry = Registry("encoder")
    with pytest.raises(KeyError, match="encoder.*not_registered"):
        registry.get("not_registered")


def test_list_registered():
    registry = Registry("processor")
    
    @registry.register("a")
    class A:
        pass
    
    @registry.register("b")
    class B:
        pass
    
    names = registry.list()
    assert set(names) == {"a", "b"}


def test_duplicate_register_raises():
    registry = Registry("retriever")
    
    @registry.register("dup")
    class First:
        pass
    
    with pytest.raises(ValueError, match="already registered"):
        @registry.register("dup")
        class Second:
            pass
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/core/test_registry.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement registry**

Create `backend/core/registry.py`:

```python
from typing import Dict, List, Type


class Registry:
    """A named registry that maps string keys to classes."""

    def __init__(self, category: str):
        self.category = category
        self._entries: Dict[str, Type] = {}

    def register(self, name: str):
        """Decorator to register a class under the given name."""
        def decorator(cls: Type) -> Type:
            if name in self._entries:
                raise ValueError(
                    f"{self.category} '{name}' already registered"
                )
            self._entries[name] = cls
            return cls
        return decorator

    def get(self, name: str) -> Type:
        if name not in self._entries:
            raise KeyError(
                f"{self.category} '{name}' not registered. "
                f"Available: {list(self._entries.keys())}"
            )
        return self._entries[name]

    def list(self) -> List[str]:
        return list(self._entries.keys())
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/core/test_registry.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/core/registry.py tests/backend/core/test_registry.py
git commit -m "feat: strategy registry with decorator registration"
```

---

## Task 3: Abstract Interfaces

**Files:**
- Create: `backend/interfaces/processor.py`, `backend/interfaces/encoder.py`, `backend/interfaces/retriever.py`, `backend/interfaces/reranker.py`, `backend/interfaces/generator.py`
- Create: `backend/models/schemas.py`

- [ ] **Step 1: Create Pydantic data models**

Create `backend/models/schemas.py`:

```python
from typing import List, Optional
from pydantic import BaseModel


class PageImage(BaseModel):
    """A single page extracted from a PDF."""
    document_id: str
    page_number: int
    image_path: str


class Embedding(BaseModel):
    """Vector embedding — single or multi-vector."""
    document_id: str
    page_number: int
    vectors: List[List[float]]  # multi-vector: list of patch vectors


class RetrievalResult(BaseModel):
    """A single retrieval hit."""
    document_id: str
    page_number: int
    score: float
    image_path: str


class Answer(BaseModel):
    """Generated answer with evidence."""
    text: str
    sources: List[RetrievalResult]


class DocumentInfo(BaseModel):
    """Document metadata."""
    id: str
    filename: str
    total_pages: int
    status: str  # "pending", "indexing", "completed", "failed"
    indexed_pages: int = 0


class EvalMetrics(BaseModel):
    """Evaluation metrics for a batch run."""
    recall_at_k: dict[int, float] = {}  # {1: 0.5, 5: 0.8, 10: 0.95}
    mrr: float = 0.0
    total_queries: int = 0
```

- [ ] **Step 2: Create abstract interfaces**

Create `backend/interfaces/processor.py`:

```python
from abc import ABC, abstractmethod
from typing import List

from backend.models.schemas import PageImage


class BaseProcessor(ABC):
    """Process a PDF file into page-level representations."""

    @abstractmethod
    async def process(self, pdf_path: str, document_id: str) -> List[PageImage]:
        """Extract pages from a PDF. Returns list of PageImage with saved image paths."""
        ...
```

Create `backend/interfaces/encoder.py`:

```python
from abc import ABC, abstractmethod
from typing import List

from backend.models.schemas import Embedding, PageImage


class BaseEncoder(ABC):
    """Dual-tower encoder interface. Encode documents and queries into embeddings."""

    @abstractmethod
    async def encode_documents(self, pages: List[PageImage]) -> List[Embedding]:
        """Encode document pages into embeddings (document tower)."""
        ...

    @abstractmethod
    async def encode_query(self, query: str) -> List[List[float]]:
        """Encode a query string into vectors (query tower). Returns list of vectors."""
        ...
```

Create `backend/interfaces/retriever.py`:

```python
from abc import ABC, abstractmethod
from typing import List

from backend.models.schemas import RetrievalResult


class BaseRetriever(ABC):
    """Retrieve relevant documents given query vectors."""

    @abstractmethod
    async def retrieve(
        self, query_vectors: List[List[float]], top_k: int = 5
    ) -> List[RetrievalResult]:
        ...

    @abstractmethod
    async def index(self, document_id: str, page_number: int,
                    vectors: List[List[float]], image_path: str) -> None:
        """Index a single page's vectors."""
        ...

    @abstractmethod
    async def delete(self, document_id: str) -> None:
        """Delete all indexed data for a document."""
        ...
```

Create `backend/interfaces/reranker.py`:

```python
from abc import ABC, abstractmethod
from typing import List

from backend.models.schemas import RetrievalResult


class BaseReranker(ABC):
    """Rerank retrieval results (optional pipeline stage)."""

    @abstractmethod
    async def rerank(
        self, query: str, results: List[RetrievalResult], top_k: int = 5
    ) -> List[RetrievalResult]:
        ...
```

Create `backend/interfaces/generator.py`:

```python
from abc import ABC, abstractmethod
from typing import List

from backend.models.schemas import Answer, RetrievalResult


class BaseGenerator(ABC):
    """Generate answers from query + retrieved context."""

    @abstractmethod
    async def generate(
        self, query: str, context: List[RetrievalResult]
    ) -> Answer:
        ...
```

- [ ] **Step 3: Update `backend/interfaces/__init__.py`**

```python
from backend.interfaces.processor import BaseProcessor
from backend.interfaces.encoder import BaseEncoder
from backend.interfaces.retriever import BaseRetriever
from backend.interfaces.reranker import BaseReranker
from backend.interfaces.generator import BaseGenerator

__all__ = [
    "BaseProcessor", "BaseEncoder", "BaseRetriever",
    "BaseReranker", "BaseGenerator",
]
```

- [ ] **Step 4: Verify imports work**

```bash
cd /c/bzli/paper/agent && python -c "from backend.interfaces import BaseProcessor, BaseEncoder, BaseRetriever, BaseReranker, BaseGenerator; print('OK')"
```

Expected: `OK`

- [ ] **Step 5: Commit**

```bash
git add backend/interfaces/ backend/models/
git commit -m "feat: abstract interfaces and data models for pipeline"
```

---

## Task 4: Pipeline Assembler

**Files:**
- Create: `backend/core/pipeline.py`
- Test: `tests/backend/core/test_pipeline.py`

- [ ] **Step 1: Write failing test**

Create `tests/backend/core/test_pipeline.py`:

```python
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock
from backend.core.pipeline import Pipeline, PipelineManager
from backend.core.registry import Registry
from backend.interfaces import (
    BaseProcessor, BaseEncoder, BaseRetriever, BaseReranker, BaseGenerator,
)
from backend.models.schemas import (
    PageImage, Embedding, RetrievalResult, Answer,
)


# --- Fake strategies for testing ---

class FakeProcessor(BaseProcessor):
    async def process(self, pdf_path, document_id):
        return [PageImage(document_id=document_id, page_number=1, image_path="/fake/img.png")]


class FakeEncoder(BaseEncoder):
    async def encode_documents(self, pages):
        return [Embedding(document_id=p.document_id, page_number=p.page_number, vectors=[[0.1, 0.2]]) for p in pages]

    async def encode_query(self, query):
        return [[0.1, 0.2]]


class FakeRetriever(BaseRetriever):
    async def retrieve(self, query_vectors, top_k=5):
        return [RetrievalResult(document_id="doc1", page_number=1, score=0.95, image_path="/fake/img.png")]

    async def index(self, document_id, page_number, vectors, image_path):
        pass

    async def delete(self, document_id):
        pass


class FakeGenerator(BaseGenerator):
    async def generate(self, query, context):
        return Answer(text="fake answer", sources=context)


def _make_registries():
    processors = Registry("processor")
    doc_encoders = Registry("document_encoder")
    query_encoders = Registry("query_encoder")
    retrievers = Registry("retriever")
    rerankers = Registry("reranker")
    generators = Registry("generator")

    processors.register("fake")(FakeProcessor)
    doc_encoders.register("fake")(FakeEncoder)
    query_encoders.register("fake")(FakeEncoder)
    retrievers.register("fake")(FakeRetriever)
    generators.register("fake")(FakeGenerator)

    return {
        "processor": processors,
        "document_encoder": doc_encoders,
        "query_encoder": query_encoders,
        "retriever": retrievers,
        "reranker": rerankers,
        "generator": generators,
    }


def test_pipeline_assemble():
    registries = _make_registries()
    pipeline_config = {
        "processor": "fake",
        "document_encoder": "fake",
        "query_encoder": "fake",
        "retriever": "fake",
        "reranker": None,
        "generator": "fake",
    }
    pipeline = Pipeline.from_config(pipeline_config, registries)
    assert isinstance(pipeline.processor, FakeProcessor)
    assert isinstance(pipeline.document_encoder, FakeEncoder)
    assert isinstance(pipeline.generator, FakeGenerator)
    assert pipeline.reranker is None


@pytest.mark.asyncio
async def test_pipeline_query():
    registries = _make_registries()
    pipeline_config = {
        "processor": "fake",
        "document_encoder": "fake",
        "query_encoder": "fake",
        "retriever": "fake",
        "reranker": None,
        "generator": "fake",
    }
    pipeline = Pipeline.from_config(pipeline_config, registries)
    answer = await pipeline.query("test question", top_k=3)
    assert answer.text == "fake answer"
    assert len(answer.sources) == 1


@pytest.mark.asyncio
async def test_pipeline_retrieve_only():
    registries = _make_registries()
    pipeline_config = {
        "processor": "fake",
        "document_encoder": "fake",
        "query_encoder": "fake",
        "retriever": "fake",
        "reranker": None,
        "generator": "fake",
    }
    pipeline = Pipeline.from_config(pipeline_config, registries)
    results = await pipeline.retrieve("test question", top_k=3)
    assert len(results) == 1
    assert results[0].score == 0.95


def test_pipeline_manager_switch():
    registries = _make_registries()
    config_a = {
        "processor": "fake",
        "document_encoder": "fake",
        "query_encoder": "fake",
        "retriever": "fake",
        "reranker": None,
        "generator": "fake",
    }
    manager = PipelineManager(registries)
    manager.set_pipeline(config_a)
    assert manager.pipeline is not None

    available = manager.list_available()
    assert "processor" in available
    assert "fake" in available["processor"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/core/test_pipeline.py -v
```

Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement Pipeline**

Create `backend/core/pipeline.py`:

```python
from typing import Dict, List, Optional

from backend.core.registry import Registry
from backend.interfaces import (
    BaseProcessor, BaseEncoder, BaseRetriever, BaseReranker, BaseGenerator,
)
from backend.models.schemas import Answer, PageImage, Embedding, RetrievalResult


class Pipeline:
    """Assembled pipeline with concrete strategy instances."""

    def __init__(
        self,
        processor: BaseProcessor,
        document_encoder: BaseEncoder,
        query_encoder: BaseEncoder,
        retriever: BaseRetriever,
        reranker: Optional[BaseReranker],
        generator: BaseGenerator,
    ):
        self.processor = processor
        self.document_encoder = document_encoder
        self.query_encoder = query_encoder
        self.retriever = retriever
        self.reranker = reranker
        self.generator = generator

    @classmethod
    def from_config(
        cls, config: dict, registries: Dict[str, Registry]
    ) -> "Pipeline":
        processor = registries["processor"].get(config["processor"])()
        doc_encoder = registries["document_encoder"].get(config["document_encoder"])()
        query_encoder = registries["query_encoder"].get(config["query_encoder"])()
        retriever = registries["retriever"].get(config["retriever"])()

        reranker = None
        if config.get("reranker"):
            reranker = registries["reranker"].get(config["reranker"])()

        generator = registries["generator"].get(config["generator"])()

        return cls(
            processor=processor,
            document_encoder=doc_encoder,
            query_encoder=query_encoder,
            retriever=retriever,
            reranker=reranker,
            generator=generator,
        )

    async def index_document(self, pdf_path: str, document_id: str) -> List[PageImage]:
        """Process and index a PDF document."""
        pages = await self.processor.process(pdf_path, document_id)
        embeddings = await self.document_encoder.encode_documents(pages)
        for page, emb in zip(pages, embeddings):
            await self.retriever.index(
                document_id=emb.document_id,
                page_number=emb.page_number,
                vectors=emb.vectors,
                image_path=page.image_path,
            )
        return pages

    async def retrieve(self, query: str, top_k: int = 5) -> List[RetrievalResult]:
        """Retrieve relevant pages without generation."""
        query_vectors = await self.query_encoder.encode_query(query)
        results = await self.retriever.retrieve(query_vectors, top_k=top_k)
        if self.reranker:
            results = await self.reranker.rerank(query, results, top_k=top_k)
        return results

    async def query(self, query: str, top_k: int = 5) -> Answer:
        """Full pipeline: retrieve + generate."""
        results = await self.retrieve(query, top_k=top_k)
        answer = await self.generator.generate(query, results)
        return answer


class PipelineManager:
    """Manages pipeline lifecycle and switching."""

    def __init__(self, registries: Dict[str, Registry]):
        self.registries = registries
        self.pipeline: Optional[Pipeline] = None
        self._current_config: Optional[dict] = None

    def set_pipeline(self, config: dict) -> Pipeline:
        self.pipeline = Pipeline.from_config(config, self.registries)
        self._current_config = config
        return self.pipeline

    def get_current_config(self) -> Optional[dict]:
        return self._current_config

    def list_available(self) -> Dict[str, List[str]]:
        return {name: reg.list() for name, reg in self.registries.items()}
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/core/test_pipeline.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/core/pipeline.py tests/backend/core/test_pipeline.py
git commit -m "feat: pipeline assembler with config-driven strategy composition"
```

---

## Task 5: Global Registry Setup & Strategy Auto-Import

**Files:**
- Create: `backend/strategies/__init__.py` (update with auto-import)
- Create: `backend/strategies/processors/__init__.py`, `backend/strategies/encoders/__init__.py`, etc.

- [ ] **Step 1: Create global registries module**

Update `backend/strategies/__init__.py`:

```python
"""
Global strategy registries. Import this module to trigger all strategy registrations.
"""
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
```

- [ ] **Step 2: Verify import works**

```bash
cd /c/bzli/paper/agent && python -c "from backend.strategies import ALL_REGISTRIES; print(list(ALL_REGISTRIES.keys()))"
```

Expected: `['processor', 'document_encoder', 'query_encoder', 'retriever', 'reranker', 'generator']`

- [ ] **Step 3: Commit**

```bash
git add backend/strategies/
git commit -m "feat: global registries with auto-import mechanism"
```

---

## Task 6: Worker Client

**Files:**
- Create: `backend/services/worker_client.py`
- Test: `tests/backend/services/test_worker_client.py` (skipped in this task — tested via integration)

- [ ] **Step 1: Write failing test**

Create `tests/backend/services/test_worker_client.py`:

```python
import pytest
import httpx
from unittest.mock import AsyncMock, patch
from backend.services.worker_client import WorkerClient


@pytest.mark.asyncio
async def test_encode_documents():
    mock_response = httpx.Response(
        200,
        json={"embeddings": [{"document_id": "doc1", "page_number": 1, "vectors": [[0.1, 0.2]]}]},
    )
    client = WorkerClient(host="localhost", port=8001, timeout=30)
    with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await client.encode_documents(["/path/to/img.png"])
    assert len(result) == 1
    assert result[0]["document_id"] == "doc1"


@pytest.mark.asyncio
async def test_encode_query():
    mock_response = httpx.Response(
        200,
        json={"vectors": [[0.1, 0.2, 0.3]]},
    )
    client = WorkerClient(host="localhost", port=8001, timeout=30)
    with patch.object(client._client, "post", new_callable=AsyncMock, return_value=mock_response):
        result = await client.encode_query("what is attention?")
    assert len(result) == 1
    assert result[0] == [0.1, 0.2, 0.3]


@pytest.mark.asyncio
async def test_health_check():
    mock_response = httpx.Response(200, json={"status": "ok", "model": "colpali"})
    client = WorkerClient(host="localhost", port=8001, timeout=30)
    with patch.object(client._client, "get", new_callable=AsyncMock, return_value=mock_response):
        result = await client.health()
    assert result["status"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/services/test_worker_client.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement WorkerClient**

Create `backend/services/worker_client.py`:

```python
from typing import List

import httpx


class WorkerClient:
    """HTTP client for communicating with the remote GPU worker."""

    def __init__(self, host: str, port: int, timeout: int = 120):
        self.base_url = f"http://{host}:{port}"
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout),
        )

    async def encode_documents(self, image_paths: List[str]) -> List[dict]:
        """Send page images to worker for encoding."""
        response = await self._client.post(
            "/encode/documents",
            json={"image_paths": image_paths},
        )
        response.raise_for_status()
        return response.json()["embeddings"]

    async def encode_query(self, query: str) -> List[List[float]]:
        """Encode a query string via the worker."""
        response = await self._client.post(
            "/encode/query",
            json={"query": query},
        )
        response.raise_for_status()
        return response.json()["vectors"]

    async def health(self) -> dict:
        """Check worker health."""
        response = await self._client.get("/health")
        response.raise_for_status()
        return response.json()

    async def close(self):
        await self._client.aclose()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/services/test_worker_client.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/worker_client.py tests/backend/services/test_worker_client.py
git commit -m "feat: worker client for remote GPU communication"
```

---

## Task 7: Page Screenshot Processor Strategy

**Files:**
- Create: `backend/strategies/processors/page_screenshot.py`
- Test: `tests/backend/test_page_screenshot.py`

- [ ] **Step 1: Write failing test**

Create `tests/backend/test_page_screenshot.py`:

```python
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from PIL import Image

from backend.strategies.processors.page_screenshot import PageScreenshotProcessor


@pytest.fixture
def output_dir(tmp_path):
    return str(tmp_path / "images")


@pytest.mark.asyncio
async def test_process_creates_images(tmp_path, output_dir):
    # Create fake PIL images to simulate pdf2image output
    fake_images = [Image.new("RGB", (100, 100), "red"), Image.new("RGB", (100, 100), "blue")]

    with patch("backend.strategies.processors.page_screenshot.convert_from_path", return_value=fake_images):
        processor = PageScreenshotProcessor(images_dir=output_dir)
        pages = await processor.process("/fake/test.pdf", "doc123")

    assert len(pages) == 2
    assert pages[0].document_id == "doc123"
    assert pages[0].page_number == 1
    assert pages[1].page_number == 2
    assert os.path.exists(pages[0].image_path)
    assert os.path.exists(pages[1].image_path)

    # Verify images are actually saved
    img = Image.open(pages[0].image_path)
    assert img.size == (100, 100)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/test_page_screenshot.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement PageScreenshotProcessor**

Create `backend/strategies/processors/page_screenshot.py`:

```python
import os
from typing import List

from pdf2image import convert_from_path

from backend.interfaces.processor import BaseProcessor
from backend.models.schemas import PageImage
from backend.strategies import processor_registry


@processor_registry.register("page_screenshot")
class PageScreenshotProcessor(BaseProcessor):
    """Convert PDF pages to screenshot images."""

    def __init__(self, images_dir: str = "data/images", dpi: int = 200):
        self.images_dir = images_dir
        self.dpi = dpi

    async def process(self, pdf_path: str, document_id: str) -> List[PageImage]:
        doc_dir = os.path.join(self.images_dir, document_id)
        os.makedirs(doc_dir, exist_ok=True)

        images = convert_from_path(pdf_path, dpi=self.dpi)
        pages = []
        for i, img in enumerate(images):
            page_num = i + 1
            img_path = os.path.join(doc_dir, f"page_{page_num}.png")
            img.save(img_path, "PNG")
            pages.append(PageImage(
                document_id=document_id,
                page_number=page_num,
                image_path=img_path,
            ))
        return pages
```

Update `backend/strategies/processors/__init__.py`:

```python
import backend.strategies.processors.page_screenshot  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/test_page_screenshot.py -v
```

Expected: 1 passed

- [ ] **Step 5: Commit**

```bash
git add backend/strategies/processors/ tests/backend/test_page_screenshot.py
git commit -m "feat: page screenshot processor strategy"
```

---

## Task 8: ColPali Encoder Strategy

**Files:**
- Create: `backend/strategies/encoders/colpali.py`
- Update: `backend/strategies/encoders/__init__.py`

- [ ] **Step 1: Write failing test**

Create `tests/backend/test_colpali_encoder.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.strategies.encoders.colpali import ColPaliEncoder
from backend.models.schemas import PageImage


@pytest.mark.asyncio
async def test_encode_documents():
    mock_client = MagicMock()
    mock_client.encode_documents = AsyncMock(return_value=[
        {"document_id": "doc1", "page_number": 1, "vectors": [[0.1, 0.2]]},
    ])
    encoder = ColPaliEncoder(worker_client=mock_client)
    pages = [PageImage(document_id="doc1", page_number=1, image_path="/img/page_1.png")]
    embeddings = await encoder.encode_documents(pages)

    assert len(embeddings) == 1
    assert embeddings[0].document_id == "doc1"
    assert embeddings[0].vectors == [[0.1, 0.2]]
    mock_client.encode_documents.assert_called_once_with(["/img/page_1.png"])


@pytest.mark.asyncio
async def test_encode_query():
    mock_client = MagicMock()
    mock_client.encode_query = AsyncMock(return_value=[[0.3, 0.4]])
    encoder = ColPaliEncoder(worker_client=mock_client)
    vectors = await encoder.encode_query("what is attention?")

    assert vectors == [[0.3, 0.4]]
    mock_client.encode_query.assert_called_once_with("what is attention?")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/test_colpali_encoder.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement ColPali encoder**

Create `backend/strategies/encoders/colpali.py`:

```python
from typing import List

from backend.interfaces.encoder import BaseEncoder
from backend.models.schemas import Embedding, PageImage
from backend.services.worker_client import WorkerClient
from backend.strategies import document_encoder_registry, query_encoder_registry


@document_encoder_registry.register("colpali")
@query_encoder_registry.register("colpali")
class ColPaliEncoder(BaseEncoder):
    """ColPali encoder that delegates to remote GPU worker."""

    def __init__(self, worker_client: WorkerClient = None):
        self.worker_client = worker_client

    async def encode_documents(self, pages: List[PageImage]) -> List[Embedding]:
        image_paths = [p.image_path for p in pages]
        raw = await self.worker_client.encode_documents(image_paths)
        return [
            Embedding(
                document_id=r["document_id"],
                page_number=r["page_number"],
                vectors=r["vectors"],
            )
            for r in raw
        ]

    async def encode_query(self, query: str) -> List[List[float]]:
        return await self.worker_client.encode_query(query)
```

Update `backend/strategies/encoders/__init__.py`:

```python
import backend.strategies.encoders.colpali  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/test_colpali_encoder.py -v
```

Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add backend/strategies/encoders/ tests/backend/test_colpali_encoder.py
git commit -m "feat: ColPali encoder strategy delegating to remote worker"
```

---

## Task 9: Multi-Vector Retriever Strategy

**Files:**
- Create: `backend/strategies/retrievers/multi_vector.py`
- Update: `backend/strategies/retrievers/__init__.py`

- [ ] **Step 1: Write failing test**

Create `tests/backend/test_multi_vector_retriever.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.strategies.retrievers.multi_vector import MultiVectorRetriever


@pytest.mark.asyncio
async def test_index_page():
    mock_qdrant = MagicMock()
    mock_qdrant.upsert = AsyncMock()
    retriever = MultiVectorRetriever(qdrant_client=mock_qdrant, collection_name="test")

    await retriever.index(
        document_id="doc1",
        page_number=1,
        vectors=[[0.1, 0.2], [0.3, 0.4]],
        image_path="/img/page_1.png",
    )
    mock_qdrant.upsert.assert_called_once()


@pytest.mark.asyncio
async def test_retrieve():
    mock_qdrant = MagicMock()
    mock_point = MagicMock()
    mock_point.id = "abc123"
    mock_point.score = 0.95
    mock_point.payload = {
        "document_id": "doc1",
        "page_number": 1,
        "image_path": "/img/page_1.png",
    }
    mock_qdrant.query_points = AsyncMock(return_value=MagicMock(points=[mock_point]))

    retriever = MultiVectorRetriever(qdrant_client=mock_qdrant, collection_name="test")
    results = await retriever.retrieve([[0.1, 0.2]], top_k=3)

    assert len(results) == 1
    assert results[0].document_id == "doc1"
    assert results[0].score == 0.95


@pytest.mark.asyncio
async def test_delete():
    mock_qdrant = MagicMock()
    mock_qdrant.delete = AsyncMock()
    retriever = MultiVectorRetriever(qdrant_client=mock_qdrant, collection_name="test")

    await retriever.delete("doc1")
    mock_qdrant.delete.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/test_multi_vector_retriever.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement MultiVectorRetriever**

Create `backend/strategies/retrievers/multi_vector.py`:

```python
import uuid
from typing import List

from qdrant_client import models

from backend.interfaces.retriever import BaseRetriever
from backend.models.schemas import RetrievalResult
from backend.strategies import retriever_registry


@retriever_registry.register("multi_vector")
class MultiVectorRetriever(BaseRetriever):
    """Multi-vector retrieval using Qdrant with MaxSim-style scoring."""

    def __init__(self, qdrant_client=None, collection_name: str = "documents"):
        self.client = qdrant_client
        self.collection_name = collection_name

    async def index(
        self, document_id: str, page_number: int,
        vectors: List[List[float]], image_path: str
    ) -> None:
        point_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"{document_id}:{page_number}"))
        point = models.PointStruct(
            id=point_id,
            vector=vectors,
            payload={
                "document_id": document_id,
                "page_number": page_number,
                "image_path": image_path,
            },
        )
        await self.client.upsert(
            collection_name=self.collection_name,
            points=[point],
        )

    async def retrieve(
        self, query_vectors: List[List[float]], top_k: int = 5
    ) -> List[RetrievalResult]:
        response = await self.client.query_points(
            collection_name=self.collection_name,
            query=query_vectors,
            limit=top_k,
            with_payload=True,
        )
        results = []
        for point in response.points:
            results.append(RetrievalResult(
                document_id=point.payload["document_id"],
                page_number=point.payload["page_number"],
                score=point.score,
                image_path=point.payload["image_path"],
            ))
        return results

    async def delete(self, document_id: str) -> None:
        await self.client.delete(
            collection_name=self.collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id",
                            match=models.MatchValue(value=document_id),
                        )
                    ]
                )
            ),
        )
```

Update `backend/strategies/retrievers/__init__.py`:

```python
import backend.strategies.retrievers.multi_vector  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/test_multi_vector_retriever.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add backend/strategies/retrievers/ tests/backend/test_multi_vector_retriever.py
git commit -m "feat: multi-vector retriever strategy with Qdrant"
```

---

## Task 10: Generator Strategies (GPT-4o + Claude)

**Files:**
- Create: `backend/strategies/generators/openai_gpt4o.py`
- Create: `backend/strategies/generators/claude.py`
- Update: `backend/strategies/generators/__init__.py`

- [ ] **Step 1: Write failing test**

Create `tests/backend/test_generators.py`:

```python
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.strategies.generators.openai_gpt4o import OpenAIGPT4oGenerator
from backend.strategies.generators.claude import ClaudeGenerator
from backend.models.schemas import RetrievalResult


def _make_context():
    return [
        RetrievalResult(document_id="doc1", page_number=1, score=0.9, image_path="/img/p1.png"),
    ]


@pytest.mark.asyncio
async def test_openai_generator():
    mock_response = MagicMock()
    mock_response.choices = [MagicMock(message=MagicMock(content="The answer is 42."))]

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    generator = OpenAIGPT4oGenerator(client=mock_client, model="gpt-4o")
    answer = await generator.generate("What is the answer?", _make_context())

    assert answer.text == "The answer is 42."
    assert len(answer.sources) == 1


@pytest.mark.asyncio
async def test_claude_generator():
    mock_response = MagicMock()
    mock_response.content = [MagicMock(text="Claude says 42.")]

    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    generator = ClaudeGenerator(client=mock_client, model="claude-sonnet-4-6-20250514")
    answer = await generator.generate("What is the answer?", _make_context())

    assert answer.text == "Claude says 42."
    assert len(answer.sources) == 1
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/test_generators.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement OpenAI generator**

Create `backend/strategies/generators/openai_gpt4o.py`:

```python
import base64
from typing import List

from backend.interfaces.generator import BaseGenerator
from backend.models.schemas import Answer, RetrievalResult
from backend.strategies import generator_registry


@generator_registry.register("openai_gpt4o")
class OpenAIGPT4oGenerator(BaseGenerator):
    """Generate answers using OpenAI GPT-4o multimodal API."""

    def __init__(self, client=None, model: str = "gpt-4o", api_key: str = ""):
        if client is None:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=api_key)
        self.client = client
        self.model = model

    async def generate(
        self, query: str, context: List[RetrievalResult]
    ) -> Answer:
        messages = self._build_messages(query, context)
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_tokens=2048,
        )
        text = response.choices[0].message.content
        return Answer(text=text, sources=context)

    def _build_messages(self, query: str, context: List[RetrievalResult]) -> list:
        content = []
        content.append({
            "type": "text",
            "text": f"Based on the following document pages, answer the question:\n\n{query}",
        })
        for result in context:
            try:
                with open(result.image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                content.append({
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                })
            except FileNotFoundError:
                continue
        return [{"role": "user", "content": content}]
```

- [ ] **Step 4: Implement Claude generator**

Create `backend/strategies/generators/claude.py`:

```python
import base64
from typing import List

from backend.interfaces.generator import BaseGenerator
from backend.models.schemas import Answer, RetrievalResult
from backend.strategies import generator_registry


@generator_registry.register("claude")
class ClaudeGenerator(BaseGenerator):
    """Generate answers using Anthropic Claude multimodal API."""

    def __init__(self, client=None, model: str = "claude-sonnet-4-6-20250514", api_key: str = ""):
        if client is None:
            from anthropic import AsyncAnthropic
            client = AsyncAnthropic(api_key=api_key)
        self.client = client
        self.model = model

    async def generate(
        self, query: str, context: List[RetrievalResult]
    ) -> Answer:
        content = self._build_content(query, context)
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=2048,
            messages=[{"role": "user", "content": content}],
        )
        text = response.content[0].text
        return Answer(text=text, sources=context)

    def _build_content(self, query: str, context: List[RetrievalResult]) -> list:
        content = []
        for result in context:
            try:
                with open(result.image_path, "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": b64,
                    },
                })
            except FileNotFoundError:
                continue
        content.append({
            "type": "text",
            "text": f"Based on the document pages shown above, answer the question:\n\n{query}",
        })
        return content
```

Update `backend/strategies/generators/__init__.py`:

```python
import backend.strategies.generators.openai_gpt4o  # noqa: F401
import backend.strategies.generators.claude  # noqa: F401
```

- [ ] **Step 5: Run test to verify it passes**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/test_generators.py -v
```

Expected: 2 passed

- [ ] **Step 6: Commit**

```bash
git add backend/strategies/generators/ tests/backend/test_generators.py
git commit -m "feat: OpenAI GPT-4o and Claude generator strategies"
```

---

## Task 11: Document Service

**Files:**
- Create: `backend/services/document_service.py`
- Test: `tests/backend/services/test_document_service.py`

- [ ] **Step 1: Write failing test**

Create `tests/backend/services/test_document_service.py`:

```python
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from backend.services.document_service import DocumentService
from backend.models.schemas import PageImage


@pytest.fixture
def doc_service(tmp_path):
    mock_pipeline = MagicMock()
    mock_pipeline.index_document = AsyncMock(return_value=[
        PageImage(document_id="doc1", page_number=1, image_path="/img/p1.png"),
    ])
    mock_pipeline.retriever = MagicMock()
    mock_pipeline.retriever.delete = AsyncMock()
    return DocumentService(
        upload_dir=str(tmp_path / "uploads"),
        pipeline=mock_pipeline,
    )


@pytest.mark.asyncio
async def test_upload_and_list(doc_service, tmp_path):
    # Simulate file upload
    pdf_content = b"%PDF-1.4 fake content"
    doc_info = await doc_service.upload(filename="test.pdf", content=pdf_content)

    assert doc_info.filename == "test.pdf"
    assert doc_info.status == "pending"

    docs = doc_service.list_documents()
    assert len(docs) == 1
    assert docs[0].id == doc_info.id


@pytest.mark.asyncio
async def test_index_document(doc_service):
    pdf_content = b"%PDF-1.4 fake"
    doc_info = await doc_service.upload(filename="test.pdf", content=pdf_content)

    await doc_service.index_document(doc_info.id)
    updated = doc_service.get_document(doc_info.id)
    assert updated.status == "completed"


@pytest.mark.asyncio
async def test_delete_document(doc_service):
    pdf_content = b"%PDF-1.4 fake"
    doc_info = await doc_service.upload(filename="test.pdf", content=pdf_content)

    await doc_service.delete_document(doc_info.id)
    assert doc_service.get_document(doc_info.id) is None


def test_get_nonexistent(doc_service):
    assert doc_service.get_document("nonexistent") is None
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/services/test_document_service.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement DocumentService**

Create `backend/services/document_service.py`:

```python
import os
import uuid
import shutil
from typing import Dict, List, Optional

from backend.models.schemas import DocumentInfo


class DocumentService:
    """Manages document lifecycle: upload, index, delete."""

    def __init__(self, upload_dir: str, pipeline=None):
        self.upload_dir = upload_dir
        self.pipeline = pipeline
        self._documents: Dict[str, DocumentInfo] = {}
        self._paths: Dict[str, str] = {}
        os.makedirs(upload_dir, exist_ok=True)

    async def upload(self, filename: str, content: bytes) -> DocumentInfo:
        doc_id = str(uuid.uuid4())[:8]
        doc_dir = os.path.join(self.upload_dir, doc_id)
        os.makedirs(doc_dir, exist_ok=True)
        pdf_path = os.path.join(doc_dir, filename)
        with open(pdf_path, "wb") as f:
            f.write(content)

        info = DocumentInfo(
            id=doc_id,
            filename=filename,
            total_pages=0,
            status="pending",
        )
        self._documents[doc_id] = info
        self._paths[doc_id] = pdf_path
        return info

    async def index_document(self, doc_id: str) -> DocumentInfo:
        info = self._documents.get(doc_id)
        if not info:
            raise ValueError(f"Document {doc_id} not found")

        info.status = "indexing"
        pdf_path = self._paths[doc_id]

        try:
            pages = await self.pipeline.index_document(pdf_path, doc_id)
            info.total_pages = len(pages)
            info.indexed_pages = len(pages)
            info.status = "completed"
        except Exception:
            info.status = "failed"
            raise

        return info

    def get_document(self, doc_id: str) -> Optional[DocumentInfo]:
        return self._documents.get(doc_id)

    def list_documents(self) -> List[DocumentInfo]:
        return list(self._documents.values())

    async def delete_document(self, doc_id: str) -> None:
        if doc_id in self._documents:
            # Delete from vector store
            if self.pipeline:
                await self.pipeline.retriever.delete(doc_id)
            # Delete files
            doc_dir = os.path.join(self.upload_dir, doc_id)
            if os.path.exists(doc_dir):
                shutil.rmtree(doc_dir)
            del self._documents[doc_id]
            self._paths.pop(doc_id, None)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/services/test_document_service.py -v
```

Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/document_service.py tests/backend/services/test_document_service.py
git commit -m "feat: document service with upload, index, delete lifecycle"
```

---

## Task 12: Evaluation Service

**Files:**
- Create: `backend/services/evaluation.py`
- Test: `tests/backend/services/test_evaluation.py`

- [ ] **Step 1: Write failing test**

Create `tests/backend/services/test_evaluation.py`:

```python
import pytest
from backend.services.evaluation import compute_recall_at_k, compute_mrr


def test_recall_at_1_hit():
    retrieved = ["doc1:1", "doc2:3", "doc1:2"]
    relevant = {"doc1:1"}
    assert compute_recall_at_k(retrieved, relevant, k=1) == 1.0


def test_recall_at_1_miss():
    retrieved = ["doc2:3", "doc1:1", "doc1:2"]
    relevant = {"doc1:1"}
    assert compute_recall_at_k(retrieved, relevant, k=1) == 0.0


def test_recall_at_5():
    retrieved = ["a", "b", "c", "d", "e"]
    relevant = {"c", "e"}
    assert compute_recall_at_k(retrieved, relevant, k=5) == 1.0


def test_recall_at_3_partial():
    retrieved = ["a", "b", "c", "d", "e"]
    relevant = {"c", "e"}
    assert compute_recall_at_k(retrieved, relevant, k=3) == 0.5


def test_mrr_first():
    retrieved = ["a", "b", "c"]
    relevant = {"a"}
    assert compute_mrr(retrieved, relevant) == 1.0


def test_mrr_second():
    retrieved = ["a", "b", "c"]
    relevant = {"b"}
    assert compute_mrr(retrieved, relevant) == 0.5


def test_mrr_none():
    retrieved = ["a", "b", "c"]
    relevant = {"d"}
    assert compute_mrr(retrieved, relevant) == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/services/test_evaluation.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement evaluation functions**

Create `backend/services/evaluation.py`:

```python
from typing import List, Set


def compute_recall_at_k(
    retrieved: List[str], relevant: Set[str], k: int
) -> float:
    """Compute Recall@K: fraction of relevant items found in top-K retrieved."""
    if not relevant:
        return 0.0
    top_k = set(retrieved[:k])
    hits = len(top_k & relevant)
    return hits / len(relevant)


def compute_mrr(retrieved: List[str], relevant: Set[str]) -> float:
    """Compute Mean Reciprocal Rank for a single query."""
    for i, item in enumerate(retrieved):
        if item in relevant:
            return 1.0 / (i + 1)
    return 0.0
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/services/test_evaluation.py -v
```

Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add backend/services/evaluation.py tests/backend/services/test_evaluation.py
git commit -m "feat: evaluation metrics (Recall@K, MRR)"
```

---

## Task 13: FastAPI App & API Routes

**Files:**
- Create: `backend/main.py`
- Create: `backend/api/documents.py`, `backend/api/query.py`, `backend/api/experiments.py`, `backend/api/system.py`
- Test: `tests/backend/api/test_documents.py`, `tests/backend/api/test_query.py`, `tests/backend/api/test_experiments.py`, `tests/backend/api/test_system.py`

- [ ] **Step 1: Write failing test for system health**

Create `tests/backend/api/test_system.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock, patch
from backend.main import create_app


@pytest.fixture
def mock_deps():
    mock_worker = MagicMock()
    mock_worker.health = AsyncMock(return_value={"status": "ok", "model": "colpali"})
    mock_pipeline_manager = MagicMock()
    mock_pipeline_manager.pipeline = MagicMock()
    mock_doc_service = MagicMock()
    mock_doc_service.list_documents.return_value = []
    return {
        "worker_client": mock_worker,
        "pipeline_manager": mock_pipeline_manager,
        "document_service": mock_doc_service,
    }


@pytest.mark.asyncio
async def test_health(mock_deps):
    app = create_app(**mock_deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["worker"]["status"] == "ok"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/api/test_system.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement FastAPI app and system route**

Create `backend/api/system.py`:

```python
from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    worker_client = request.app.state.worker_client
    try:
        worker_status = await worker_client.health()
    except Exception as e:
        worker_status = {"status": "error", "detail": str(e)}

    return {
        "status": "ok",
        "worker": worker_status,
        "qdrant": {"status": "ok"},
    }
```

Create `backend/api/documents.py`:

```python
from fastapi import APIRouter, Request, UploadFile, File, BackgroundTasks, HTTPException

router = APIRouter()


@router.post("/upload")
async def upload_document(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    doc_service = request.app.state.document_service
    content = await file.read()
    doc_info = await doc_service.upload(filename=file.filename, content=content)
    background_tasks.add_task(doc_service.index_document, doc_info.id)
    return doc_info.model_dump()


@router.get("")
async def list_documents(request: Request):
    doc_service = request.app.state.document_service
    return [d.model_dump() for d in doc_service.list_documents()]


@router.get("/{doc_id}/status")
async def get_document_status(request: Request, doc_id: str):
    doc_service = request.app.state.document_service
    doc = doc_service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return doc.model_dump()


@router.delete("/{doc_id}")
async def delete_document(request: Request, doc_id: str):
    doc_service = request.app.state.document_service
    doc = doc_service.get_document(doc_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    await doc_service.delete_document(doc_id)
    return {"status": "deleted"}
```

Create `backend/api/query.py`:

```python
from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import Optional

router = APIRouter()


class QueryRequest(BaseModel):
    query: str
    top_k: int = 5


@router.post("/query")
async def query(request: Request, body: QueryRequest):
    pipeline = request.app.state.pipeline_manager.pipeline
    answer = await pipeline.query(body.query, top_k=body.top_k)
    return {
        "answer": answer.text,
        "sources": [s.model_dump() for s in answer.sources],
    }


@router.post("/retrieve")
async def retrieve(request: Request, body: QueryRequest):
    pipeline = request.app.state.pipeline_manager.pipeline
    results = await pipeline.retrieve(body.query, top_k=body.top_k)
    return {"results": [r.model_dump() for r in results]}
```

Create `backend/api/experiments.py`:

```python
from fastapi import APIRouter, Request
from pydantic import BaseModel
from typing import List, Optional, Set

from backend.services.evaluation import compute_recall_at_k, compute_mrr

router = APIRouter()


@router.get("/pipelines")
async def list_pipelines(request: Request):
    manager = request.app.state.pipeline_manager
    return {
        "available": manager.list_available(),
        "current": manager.get_current_config(),
    }


class PipelineSwitch(BaseModel):
    processor: str
    document_encoder: str
    query_encoder: str
    retriever: str
    reranker: Optional[str] = None
    generator: str


@router.put("/pipelines/active")
async def switch_pipeline(request: Request, body: PipelineSwitch):
    manager = request.app.state.pipeline_manager
    manager.set_pipeline(body.model_dump())
    return {"status": "switched", "config": body.model_dump()}


class EvalQuery(BaseModel):
    query: str
    relevant: List[str]  # list of "doc_id:page_number" strings


class EvalRequest(BaseModel):
    queries: List[EvalQuery]
    top_k: int = 10


@router.post("/experiments/evaluate")
async def evaluate(request: Request, body: EvalRequest):
    pipeline = request.app.state.pipeline_manager.pipeline

    recall_sums = {1: 0.0, 5: 0.0, 10: 0.0}
    mrr_sum = 0.0
    n = len(body.queries)

    for eq in body.queries:
        results = await pipeline.retrieve(eq.query, top_k=body.top_k)
        retrieved = [f"{r.document_id}:{r.page_number}" for r in results]
        relevant_set = set(eq.relevant)

        for k in recall_sums:
            recall_sums[k] += compute_recall_at_k(retrieved, relevant_set, k)
        mrr_sum += compute_mrr(retrieved, relevant_set)

    return {
        "recall_at_k": {k: v / n for k, v in recall_sums.items()} if n > 0 else {},
        "mrr": mrr_sum / n if n > 0 else 0.0,
        "total_queries": n,
    }
```

Create `backend/main.py`:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.api import documents, query, experiments, system


def create_app(
    worker_client=None,
    pipeline_manager=None,
    document_service=None,
) -> FastAPI:
    app = FastAPI(title="Multimodal Retrieval System")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store dependencies in app state
    app.state.worker_client = worker_client
    app.state.pipeline_manager = pipeline_manager
    app.state.document_service = document_service

    # Register routes
    app.include_router(system.router, prefix="/api")
    app.include_router(documents.router, prefix="/api/documents")
    app.include_router(query.router, prefix="/api")
    app.include_router(experiments.router, prefix="/api")

    return app
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/api/test_system.py -v
```

Expected: 1 passed

- [ ] **Step 5: Write test for documents API**

Create `tests/backend/api/test_documents.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock
from backend.main import create_app
from backend.models.schemas import DocumentInfo


@pytest.fixture
def mock_deps():
    mock_doc_service = MagicMock()
    doc = DocumentInfo(id="abc", filename="test.pdf", total_pages=0, status="pending")
    mock_doc_service.upload = AsyncMock(return_value=doc)
    mock_doc_service.list_documents.return_value = [doc]
    mock_doc_service.get_document.return_value = doc
    mock_doc_service.index_document = AsyncMock()
    mock_doc_service.delete_document = AsyncMock()

    return {
        "worker_client": MagicMock(),
        "pipeline_manager": MagicMock(),
        "document_service": mock_doc_service,
    }


@pytest.mark.asyncio
async def test_upload_document(mock_deps):
    app = create_app(**mock_deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/documents/upload",
            files={"file": ("test.pdf", b"fake pdf content", "application/pdf")},
        )
    assert resp.status_code == 200
    assert resp.json()["filename"] == "test.pdf"


@pytest.mark.asyncio
async def test_list_documents(mock_deps):
    app = create_app(**mock_deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/documents")
    assert resp.status_code == 200
    assert len(resp.json()) == 1


@pytest.mark.asyncio
async def test_delete_document(mock_deps):
    app = create_app(**mock_deps)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.delete("/api/documents/abc")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"
```

- [ ] **Step 6: Run all API tests**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/backend/api/ -v
```

Expected: 4 passed

- [ ] **Step 7: Commit**

```bash
git add backend/main.py backend/api/ tests/backend/api/
git commit -m "feat: FastAPI app with documents, query, experiments, and system routes"
```

---

## Task 14: Remote Worker Service

**Files:**
- Create: `worker/main.py`
- Create: `worker/model_manager.py`
- Create: `worker/endpoints/encode.py`
- Test: `tests/worker/test_encode.py`

- [ ] **Step 1: Write failing test**

Create `tests/worker/test_encode.py`:

```python
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import MagicMock, patch
import numpy as np
from worker.main import create_worker_app


@pytest.fixture
def mock_model_manager():
    manager = MagicMock()
    manager.encode_images.return_value = [
        {"document_id": "", "page_number": 0, "vectors": [[0.1, 0.2, 0.3]]}
    ]
    manager.encode_query.return_value = [[0.4, 0.5, 0.6]]
    manager.model_name.return_value = "colpali-v1.2"
    return manager


@pytest.mark.asyncio
async def test_encode_query(mock_model_manager):
    app = create_worker_app(model_manager=mock_model_manager)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post("/encode/query", json={"query": "what is attention?"})
    assert resp.status_code == 200
    assert resp.json()["vectors"] == [[0.4, 0.5, 0.6]]


@pytest.mark.asyncio
async def test_encode_documents(mock_model_manager):
    app = create_worker_app(model_manager=mock_model_manager)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/encode/documents",
            json={"image_paths": ["/fake/img.png"]},
        )
    assert resp.status_code == 200
    assert len(resp.json()["embeddings"]) == 1


@pytest.mark.asyncio
async def test_worker_health(mock_model_manager):
    app = create_worker_app(model_manager=mock_model_manager)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")
    assert resp.status_code == 200
    assert "model" in resp.json()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/worker/test_encode.py -v
```

Expected: FAIL

- [ ] **Step 3: Implement model manager**

Create `worker/model_manager.py`:

```python
from typing import List


class ModelManager:
    """Load and manage encoding models on the GPU worker."""

    def __init__(self, model_name: str = "colpali"):
        self._model_name = model_name
        self._model = None
        self._processor = None

    def load(self):
        """Load model into GPU memory. Called at startup."""
        if self._model_name == "colpali":
            from colpali_engine.models import ColPali, ColPaliProcessor
            self._model = ColPali.from_pretrained(
                "vidore/colpali-v1.2",
                device_map="auto",
            ).eval()
            self._processor = ColPaliProcessor.from_pretrained("vidore/colpali-v1.2")
        # Add more models here as needed

    def encode_images(self, image_paths: List[str]) -> List[dict]:
        """Encode document page images into multi-vector embeddings."""
        from PIL import Image

        images = [Image.open(p).convert("RGB") for p in image_paths]
        inputs = self._processor.process_images(images)
        inputs = {k: v.to(self._model.device) for k, v in inputs.items()}

        with __import__("torch").no_grad():
            embeddings = self._model(**inputs)

        results = []
        for i, emb in enumerate(embeddings):
            results.append({
                "document_id": "",
                "page_number": 0,
                "vectors": emb.cpu().tolist(),
            })
        return results

    def encode_query(self, query: str) -> List[List[float]]:
        """Encode a query string into multi-vector embedding."""
        inputs = self._processor.process_queries([query])
        inputs = {k: v.to(self._model.device) for k, v in inputs.items()}

        with __import__("torch").no_grad():
            embeddings = self._model(**inputs)

        return embeddings[0].cpu().tolist()

    def model_name(self) -> str:
        return self._model_name
```

- [ ] **Step 4: Implement worker endpoints**

Create `worker/endpoints/encode.py`:

```python
from typing import List

from fastapi import APIRouter, Request
from pydantic import BaseModel

router = APIRouter()


class EncodeDocumentsRequest(BaseModel):
    image_paths: List[str]


class EncodeQueryRequest(BaseModel):
    query: str


@router.post("/documents")
async def encode_documents(request: Request, body: EncodeDocumentsRequest):
    manager = request.app.state.model_manager
    embeddings = manager.encode_images(body.image_paths)
    return {"embeddings": embeddings}


@router.post("/query")
async def encode_query(request: Request, body: EncodeQueryRequest):
    manager = request.app.state.model_manager
    vectors = manager.encode_query(body.query)
    return {"vectors": vectors}
```

- [ ] **Step 5: Implement worker app**

Create `worker/main.py`:

```python
from fastapi import FastAPI
from worker.endpoints import encode


def create_worker_app(model_manager=None) -> FastAPI:
    app = FastAPI(title="Multimodal Retrieval Worker")
    app.state.model_manager = model_manager

    app.include_router(encode.router, prefix="/encode")

    @app.get("/health")
    async def health():
        return {
            "status": "ok",
            "model": app.state.model_manager.model_name(),
        }

    return app
```

- [ ] **Step 6: Run test to verify it passes**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/worker/test_encode.py -v
```

Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add worker/ tests/worker/
git commit -m "feat: remote GPU worker with model manager and encode endpoints"
```

---

## Task 15: SSH Tunnel & Deploy Scripts

**Files:**
- Create: `scripts/start_tunnel.sh`
- Create: `scripts/deploy_worker.sh`

- [ ] **Step 1: Create SSH tunnel script**

Create `scripts/start_tunnel.sh`:

```bash
#!/bin/bash
# Start SSH tunnel to remote GPU server via bastion host
# Usage: ./scripts/start_tunnel.sh [config_path]

CONFIG=${1:-config/default.yaml}

# Default values (override by editing or passing env vars)
PEM_PATH="${PEM_PATH:-~/.ssh/key.pem}"
BASTION="${BASTION:-user@bastion-host}"
TARGET="${TARGET:-user@gpu-server}"
WORKER_PORT="${WORKER_PORT:-8001}"
QDRANT_PORT="${QDRANT_PORT:-6333}"

echo "Starting SSH tunnel..."
echo "  Bastion: $BASTION"
echo "  Target:  $TARGET"
echo "  Ports:   localhost:$WORKER_PORT -> remote:$WORKER_PORT"
echo "           localhost:$QDRANT_PORT -> remote:$QDRANT_PORT"

ssh -i "$PEM_PATH" -J "$BASTION" "$TARGET" \
    -L "$WORKER_PORT:localhost:$WORKER_PORT" \
    -L "$QDRANT_PORT:localhost:$QDRANT_PORT" \
    -N -o ServerAliveInterval=60 -o ServerAliveCountMax=3
```

- [ ] **Step 2: Create worker deploy script**

Create `scripts/deploy_worker.sh`:

```bash
#!/bin/bash
# Deploy and start the worker service on remote GPU server
# Run this script ON the remote server, or use ssh to execute it
# Usage: ./scripts/deploy_worker.sh

set -e

WORKER_DIR="${WORKER_DIR:-~/multimodal-worker}"
WORKER_PORT="${WORKER_PORT:-8001}"

echo "Setting up worker in $WORKER_DIR..."

# Create directory and copy worker files
mkdir -p "$WORKER_DIR"

# Install dependencies (assumes conda/venv is activated)
pip install fastapi uvicorn colpali-engine torch pillow

echo "Starting worker on port $WORKER_PORT..."
cd "$WORKER_DIR"
python -m uvicorn worker.main:app --host 0.0.0.0 --port "$WORKER_PORT"
```

- [ ] **Step 3: Make scripts executable and commit**

```bash
chmod +x scripts/start_tunnel.sh scripts/deploy_worker.sh
git add scripts/
git commit -m "feat: SSH tunnel and worker deployment scripts"
```

---

## Task 16: Vue 3 Frontend — Project Setup & Router

**Files:**
- Create: `frontend/` (Vite + Vue 3 + TypeScript project)

- [ ] **Step 1: Initialize Vue project**

```bash
cd /c/bzli/paper/agent && npm create vite@latest frontend -- --template vue-ts
```

- [ ] **Step 2: Install dependencies**

```bash
cd /c/bzli/paper/agent/frontend && npm install && npm install vue-router@4 axios element-plus @element-plus/icons-vue
```

- [ ] **Step 3: Create router**

Create `frontend/src/router/index.ts`:

```typescript
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/documents',
  },
  {
    path: '/documents',
    name: 'Documents',
    component: () => import('../views/DocumentsView.vue'),
  },
  {
    path: '/query',
    name: 'Query',
    component: () => import('../views/QueryView.vue'),
  },
  {
    path: '/experiments',
    name: 'Experiments',
    component: () => import('../views/ExperimentView.vue'),
  },
  {
    path: '/system',
    name: 'System',
    component: () => import('../views/SystemView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
```

- [ ] **Step 4: Create API client**

Create `frontend/src/api/client.ts`:

```typescript
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 120000,
})

export interface DocumentInfo {
  id: string
  filename: string
  total_pages: number
  status: string
  indexed_pages: number
}

export interface RetrievalResult {
  document_id: string
  page_number: number
  score: number
  image_path: string
}

export interface QueryResponse {
  answer: string
  sources: RetrievalResult[]
}

export interface EvalMetrics {
  recall_at_k: Record<number, number>
  mrr: number
  total_queries: number
}

export interface PipelineInfo {
  available: Record<string, string[]>
  current: Record<string, string | null>
}

export const documentsApi = {
  upload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post<DocumentInfo>('/documents/upload', form)
  },
  list: () => api.get<DocumentInfo[]>('/documents'),
  status: (id: string) => api.get<DocumentInfo>(`/documents/${id}/status`),
  delete: (id: string) => api.delete(`/documents/${id}`),
}

export const queryApi = {
  query: (query: string, topK = 5) =>
    api.post<QueryResponse>('/query', { query, top_k: topK }),
  retrieve: (query: string, topK = 5) =>
    api.post<{ results: RetrievalResult[] }>('/retrieve', { query, top_k: topK }),
}

export const experimentsApi = {
  getPipelines: () => api.get<PipelineInfo>('/pipelines'),
  switchPipeline: (config: Record<string, string | null>) =>
    api.put('/pipelines/active', config),
  evaluate: (queries: Array<{ query: string; relevant: string[] }>, topK = 10) =>
    api.post<EvalMetrics>('/experiments/evaluate', { queries, top_k: topK }),
}

export const systemApi = {
  health: () => api.get('/health'),
}

export default api
```

- [ ] **Step 5: Update main.ts with router and Element Plus**

Replace `frontend/src/main.ts`:

```typescript
import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import App from './App.vue'
import router from './router'

const app = createApp(App)
app.use(router)
app.use(ElementPlus)
app.mount('#app')
```

- [ ] **Step 6: Update App.vue with navigation layout**

Replace `frontend/src/App.vue`:

```vue
<template>
  <el-container style="height: 100vh">
    <el-aside width="200px">
      <el-menu :default-active="route.path" router>
        <el-menu-item index="/documents">
          <span>文档管理</span>
        </el-menu-item>
        <el-menu-item index="/query">
          <span>检索问答</span>
        </el-menu-item>
        <el-menu-item index="/experiments">
          <span>实验工作台</span>
        </el-menu-item>
        <el-menu-item index="/system">
          <span>系统状态</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-main>
      <router-view />
    </el-main>
  </el-container>
</template>

<script setup lang="ts">
import { useRoute } from 'vue-router'
const route = useRoute()
</script>
```

- [ ] **Step 7: Verify build**

```bash
cd /c/bzli/paper/agent/frontend && npm run build
```

Expected: Build succeeds (with empty view stubs we'll create next)

- [ ] **Step 8: Commit**

```bash
cd /c/bzli/paper/agent
git add frontend/
git commit -m "feat: Vue 3 frontend scaffold with router, API client, Element Plus"
```

---

## Task 17: Frontend — Documents View

**Files:**
- Create: `frontend/src/views/DocumentsView.vue`
- Create: `frontend/src/components/DocumentUpload.vue`
- Create: `frontend/src/components/DocumentList.vue`

- [ ] **Step 1: Create DocumentUpload component**

Create `frontend/src/components/DocumentUpload.vue`:

```vue
<template>
  <el-upload
    drag
    multiple
    action=""
    :auto-upload="false"
    :on-change="handleFileChange"
    accept=".pdf"
  >
    <el-icon :size="60"><upload-filled /></el-icon>
    <div>拖拽 PDF 文件到此处，或 <em>点击上传</em></div>
  </el-upload>
  <el-button type="primary" :loading="uploading" :disabled="!files.length" @click="uploadAll" style="margin-top: 12px">
    上传 {{ files.length }} 个文件
  </el-button>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { UploadFilled } from '@element-plus/icons-vue'
import { documentsApi } from '../api/client'

const emit = defineEmits<{ (e: 'uploaded'): void }>()

const files = ref<File[]>([])
const uploading = ref(false)

function handleFileChange(uploadFile: any) {
  if (uploadFile.raw) {
    files.value.push(uploadFile.raw)
  }
}

async function uploadAll() {
  uploading.value = true
  try {
    for (const file of files.value) {
      await documentsApi.upload(file)
    }
    files.value = []
    emit('uploaded')
  } finally {
    uploading.value = false
  }
}
</script>
```

- [ ] **Step 2: Create DocumentList component**

Create `frontend/src/components/DocumentList.vue`:

```vue
<template>
  <el-table :data="documents" stripe style="width: 100%">
    <el-table-column prop="id" label="ID" width="100" />
    <el-table-column prop="filename" label="文件名" />
    <el-table-column prop="total_pages" label="总页数" width="80" />
    <el-table-column prop="indexed_pages" label="已索引" width="80" />
    <el-table-column label="状态" width="120">
      <template #default="{ row }">
        <el-tag :type="statusType(row.status)">{{ row.status }}</el-tag>
      </template>
    </el-table-column>
    <el-table-column label="操作" width="100">
      <template #default="{ row }">
        <el-button type="danger" size="small" @click="$emit('delete', row.id)">删除</el-button>
      </template>
    </el-table-column>
  </el-table>
</template>

<script setup lang="ts">
import type { DocumentInfo } from '../api/client'

defineProps<{ documents: DocumentInfo[] }>()
defineEmits<{ (e: 'delete', id: string): void }>()

function statusType(status: string) {
  switch (status) {
    case 'completed': return 'success'
    case 'indexing': return 'warning'
    case 'failed': return 'danger'
    default: return 'info'
  }
}
</script>
```

- [ ] **Step 3: Create DocumentsView**

Create `frontend/src/views/DocumentsView.vue`:

```vue
<template>
  <div>
    <h2>文档管理</h2>
    <DocumentUpload @uploaded="loadDocuments" />
    <el-divider />
    <DocumentList :documents="documents" @delete="handleDelete" />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import DocumentUpload from '../components/DocumentUpload.vue'
import DocumentList from '../components/DocumentList.vue'
import { documentsApi, type DocumentInfo } from '../api/client'

const documents = ref<DocumentInfo[]>([])

async function loadDocuments() {
  const resp = await documentsApi.list()
  documents.value = resp.data
}

async function handleDelete(id: string) {
  await documentsApi.delete(id)
  await loadDocuments()
}

onMounted(loadDocuments)
</script>
```

- [ ] **Step 4: Verify build**

```bash
cd /c/bzli/paper/agent/frontend && npm run build
```

Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
cd /c/bzli/paper/agent && git add frontend/src/views/DocumentsView.vue frontend/src/components/DocumentUpload.vue frontend/src/components/DocumentList.vue
git commit -m "feat: documents view with upload and list components"
```

---

## Task 18: Frontend — Query View

**Files:**
- Create: `frontend/src/views/QueryView.vue`
- Create: `frontend/src/components/QueryInput.vue`
- Create: `frontend/src/components/AnswerDisplay.vue`
- Create: `frontend/src/components/EvidencePanel.vue`

- [ ] **Step 1: Create QueryInput component**

Create `frontend/src/components/QueryInput.vue`:

```vue
<template>
  <div style="display: flex; gap: 12px">
    <el-input
      v-model="query"
      placeholder="输入问题..."
      @keyup.enter="$emit('submit', query)"
      size="large"
    />
    <el-input-number v-model="topK" :min="1" :max="20" size="large" style="width: 120px" />
    <el-button type="primary" size="large" :loading="loading" @click="$emit('submit', query, topK)">
      检索问答
    </el-button>
    <el-button size="large" :loading="loading" @click="$emit('retrieve', query, topK)">
      仅检索
    </el-button>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'

defineProps<{ loading: boolean }>()
defineEmits<{
  (e: 'submit', query: string, topK?: number): void
  (e: 'retrieve', query: string, topK?: number): void
}>()

const query = ref('')
const topK = ref(5)
</script>
```

- [ ] **Step 2: Create AnswerDisplay component**

Create `frontend/src/components/AnswerDisplay.vue`:

```vue
<template>
  <el-card v-if="answer" style="margin-top: 16px">
    <template #header>
      <span>回答</span>
    </template>
    <div style="white-space: pre-wrap">{{ answer }}</div>
  </el-card>
</template>

<script setup lang="ts">
defineProps<{ answer: string }>()
</script>
```

- [ ] **Step 3: Create EvidencePanel component**

Create `frontend/src/components/EvidencePanel.vue`:

```vue
<template>
  <div v-if="results.length" style="margin-top: 16px">
    <h3>检索证据 (Top-{{ results.length }})</h3>
    <el-row :gutter="12">
      <el-col v-for="(r, i) in results" :key="i" :span="8">
        <el-card shadow="hover" @click="selectedIndex = i">
          <div style="text-align: center">
            <img
              :src="'/api/images/' + r.document_id + '/page_' + r.page_number + '.png'"
              style="max-width: 100%; max-height: 200px; object-fit: contain"
            />
          </div>
          <div style="margin-top: 8px; font-size: 12px; color: #666">
            文档: {{ r.document_id }} | 页: {{ r.page_number }} | 分数: {{ r.score.toFixed(4) }}
          </div>
        </el-card>
      </el-col>
    </el-row>
    <el-dialog v-model="showDialog" width="80%">
      <img
        v-if="selectedResult"
        :src="'/api/images/' + selectedResult.document_id + '/page_' + selectedResult.page_number + '.png'"
        style="width: 100%"
      />
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import type { RetrievalResult } from '../api/client'

const props = defineProps<{ results: RetrievalResult[] }>()
const selectedIndex = ref(-1)
const showDialog = computed({
  get: () => selectedIndex.value >= 0,
  set: (v) => { if (!v) selectedIndex.value = -1 },
})
const selectedResult = computed(() =>
  selectedIndex.value >= 0 ? props.results[selectedIndex.value] : null
)
</script>
```

- [ ] **Step 4: Create QueryView**

Create `frontend/src/views/QueryView.vue`:

```vue
<template>
  <div>
    <h2>检索问答</h2>
    <QueryInput :loading="loading" @submit="handleQuery" @retrieve="handleRetrieve" />
    <AnswerDisplay :answer="answer" />
    <EvidencePanel :results="results" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import QueryInput from '../components/QueryInput.vue'
import AnswerDisplay from '../components/AnswerDisplay.vue'
import EvidencePanel from '../components/EvidencePanel.vue'
import { queryApi, type RetrievalResult } from '../api/client'

const loading = ref(false)
const answer = ref('')
const results = ref<RetrievalResult[]>([])

async function handleQuery(query: string, topK = 5) {
  loading.value = true
  answer.value = ''
  results.value = []
  try {
    const resp = await queryApi.query(query, topK)
    answer.value = resp.data.answer
    results.value = resp.data.sources
  } finally {
    loading.value = false
  }
}

async function handleRetrieve(query: string, topK = 5) {
  loading.value = true
  answer.value = ''
  results.value = []
  try {
    const resp = await queryApi.retrieve(query, topK)
    results.value = resp.data.results
  } finally {
    loading.value = false
  }
}
</script>
```

- [ ] **Step 5: Verify build**

```bash
cd /c/bzli/paper/agent/frontend && npm run build
```

Expected: Build succeeds

- [ ] **Step 6: Commit**

```bash
cd /c/bzli/paper/agent && git add frontend/src/views/QueryView.vue frontend/src/components/QueryInput.vue frontend/src/components/AnswerDisplay.vue frontend/src/components/EvidencePanel.vue
git commit -m "feat: query view with input, answer display, and evidence panel"
```

---

## Task 19: Frontend — Experiment View

**Files:**
- Create: `frontend/src/views/ExperimentView.vue`
- Create: `frontend/src/components/PipelineSelector.vue`
- Create: `frontend/src/components/EvalResults.vue`

- [ ] **Step 1: Create PipelineSelector component**

Create `frontend/src/components/PipelineSelector.vue`:

```vue
<template>
  <el-card>
    <template #header>Pipeline 配置</template>
    <el-form label-width="140px" v-if="available">
      <el-form-item v-for="(options, key) in available" :key="key" :label="key">
        <el-select v-model="selected[key]" :placeholder="'选择 ' + key" clearable>
          <el-option v-for="opt in options" :key="opt" :label="opt" :value="opt" />
        </el-select>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="switching" @click="handleSwitch">切换 Pipeline</el-button>
      </el-form-item>
    </el-form>
  </el-card>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { experimentsApi } from '../api/client'

const available = ref<Record<string, string[]> | null>(null)
const selected = ref<Record<string, string | null>>({})
const switching = ref(false)

async function loadPipelines() {
  const resp = await experimentsApi.getPipelines()
  available.value = resp.data.available
  if (resp.data.current) {
    selected.value = { ...resp.data.current }
  }
}

async function handleSwitch() {
  switching.value = true
  try {
    await experimentsApi.switchPipeline(selected.value)
  } finally {
    switching.value = false
  }
}

onMounted(loadPipelines)
</script>
```

- [ ] **Step 2: Create EvalResults component**

Create `frontend/src/components/EvalResults.vue`:

```vue
<template>
  <el-card style="margin-top: 16px" v-if="metrics">
    <template #header>评测结果</template>
    <el-descriptions :column="2" border>
      <el-descriptions-item label="总查询数">{{ metrics.total_queries }}</el-descriptions-item>
      <el-descriptions-item label="MRR">{{ metrics.mrr.toFixed(4) }}</el-descriptions-item>
      <el-descriptions-item
        v-for="(val, k) in metrics.recall_at_k"
        :key="k"
        :label="'Recall@' + k"
      >
        {{ val.toFixed(4) }}
      </el-descriptions-item>
    </el-descriptions>
  </el-card>
</template>

<script setup lang="ts">
import type { EvalMetrics } from '../api/client'
defineProps<{ metrics: EvalMetrics | null }>()
</script>
```

- [ ] **Step 3: Create ExperimentView**

Create `frontend/src/views/ExperimentView.vue`:

```vue
<template>
  <div>
    <h2>实验工作台</h2>
    <PipelineSelector />
    <el-card style="margin-top: 16px">
      <template #header>批量评测</template>
      <el-upload
        action=""
        :auto-upload="false"
        :on-change="handleFileChange"
        accept=".json"
      >
        <el-button>上传评测数据 (JSON)</el-button>
      </el-upload>
      <div style="margin-top: 8px; font-size: 12px; color: #999">
        格式: [{"query": "...", "relevant": ["doc_id:page"]}]
      </div>
      <el-button type="primary" :loading="evaluating" :disabled="!evalData" @click="runEval" style="margin-top: 12px">
        运行评测
      </el-button>
    </el-card>
    <EvalResults :metrics="metrics" />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import PipelineSelector from '../components/PipelineSelector.vue'
import EvalResults from '../components/EvalResults.vue'
import { experimentsApi, type EvalMetrics } from '../api/client'

const evalData = ref<Array<{ query: string; relevant: string[] }> | null>(null)
const evaluating = ref(false)
const metrics = ref<EvalMetrics | null>(null)

function handleFileChange(uploadFile: any) {
  const reader = new FileReader()
  reader.onload = (e) => {
    evalData.value = JSON.parse(e.target?.result as string)
  }
  reader.readAsText(uploadFile.raw)
}

async function runEval() {
  if (!evalData.value) return
  evaluating.value = true
  metrics.value = null
  try {
    const resp = await experimentsApi.evaluate(evalData.value)
    metrics.value = resp.data
  } finally {
    evaluating.value = false
  }
}
</script>
```

- [ ] **Step 4: Verify build**

```bash
cd /c/bzli/paper/agent/frontend && npm run build
```

Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
cd /c/bzli/paper/agent && git add frontend/src/views/ExperimentView.vue frontend/src/components/PipelineSelector.vue frontend/src/components/EvalResults.vue
git commit -m "feat: experiment view with pipeline selector and batch evaluation"
```

---

## Task 20: Frontend — System View

**Files:**
- Create: `frontend/src/views/SystemView.vue`

- [ ] **Step 1: Create SystemView**

Create `frontend/src/views/SystemView.vue`:

```vue
<template>
  <div>
    <h2>系统状态</h2>
    <el-button @click="refresh" :loading="loading" style="margin-bottom: 16px">刷新</el-button>
    <el-descriptions v-if="health" :column="1" border>
      <el-descriptions-item label="系统状态">
        <el-tag :type="health.status === 'ok' ? 'success' : 'danger'">{{ health.status }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="Worker 状态">
        <el-tag :type="health.worker?.status === 'ok' ? 'success' : 'danger'">
          {{ health.worker?.status || 'unknown' }}
        </el-tag>
        <span v-if="health.worker?.model" style="margin-left: 8px">模型: {{ health.worker.model }}</span>
      </el-descriptions-item>
      <el-descriptions-item label="Qdrant 状态">
        <el-tag :type="health.qdrant?.status === 'ok' ? 'success' : 'danger'">
          {{ health.qdrant?.status || 'unknown' }}
        </el-tag>
      </el-descriptions-item>
    </el-descriptions>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { systemApi } from '../api/client'

const health = ref<any>(null)
const loading = ref(false)

async function refresh() {
  loading.value = true
  try {
    const resp = await systemApi.health()
    health.value = resp.data
  } finally {
    loading.value = false
  }
}

onMounted(refresh)
</script>
```

- [ ] **Step 2: Configure Vite proxy for development**

Update `frontend/vite.config.ts`:

```typescript
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
})
```

- [ ] **Step 3: Verify full build**

```bash
cd /c/bzli/paper/agent/frontend && npm run build
```

Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
cd /c/bzli/paper/agent && git add frontend/src/views/SystemView.vue frontend/vite.config.ts
git commit -m "feat: system status view and Vite dev proxy"
```

---

## Task 21: Backend Entry Point & Static File Serving

**Files:**
- Modify: `backend/main.py`
- Create: `run.py`

- [ ] **Step 1: Create run.py entry point**

Create `run.py`:

```python
"""Main entry point: load config, wire dependencies, start server."""
import os
import uvicorn

from backend.core.config import load_config
from backend.core.pipeline import PipelineManager
from backend.services.document_service import DocumentService
from backend.services.worker_client import WorkerClient
from backend.strategies import ALL_REGISTRIES, import_all_strategies
from backend.main import create_app


def main():
    config_path = os.environ.get("CONFIG_PATH", "config/default.yaml")
    config = load_config(config_path)

    # Import all strategies to trigger registration
    import_all_strategies()

    # Wire dependencies
    worker_client = WorkerClient(
        host=config.worker.host,
        port=config.worker.port,
        timeout=config.worker.timeout,
    )

    pipeline_manager = PipelineManager(ALL_REGISTRIES)
    pipeline_manager.set_pipeline(config.pipeline.model_dump())

    # Ensure storage dirs exist
    os.makedirs(config.storage.upload_dir, exist_ok=True)
    os.makedirs(config.storage.images_dir, exist_ok=True)

    document_service = DocumentService(
        upload_dir=config.storage.upload_dir,
        pipeline=pipeline_manager.pipeline,
    )

    app = create_app(
        worker_client=worker_client,
        pipeline_manager=pipeline_manager,
        document_service=document_service,
    )

    uvicorn.run(app, host=config.server.host, port=config.server.port)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Add static image serving to main.py**

Add to `backend/main.py` inside `create_app`, after route registration:

```python
    import os
    # Serve page images for frontend evidence panel
    images_dir = "data/images"
    if os.path.isdir(images_dir):
        app.mount("/api/images", StaticFiles(directory=images_dir), name="images")
```

- [ ] **Step 3: Commit**

```bash
git add run.py backend/main.py
git commit -m "feat: application entry point with dependency wiring and static image serving"
```

---

## Task 22: Full Integration Test

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write integration test**

Create `tests/test_integration.py`:

```python
"""Integration test: assemble a full pipeline with fakes, test end-to-end via API."""
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, MagicMock

from backend.core.registry import Registry
from backend.core.pipeline import Pipeline, PipelineManager
from backend.services.document_service import DocumentService
from backend.services.worker_client import WorkerClient
from backend.main import create_app
from backend.interfaces import BaseProcessor, BaseEncoder, BaseRetriever, BaseGenerator
from backend.models.schemas import PageImage, Embedding, RetrievalResult, Answer


class StubProcessor(BaseProcessor):
    async def process(self, pdf_path, document_id):
        return [PageImage(document_id=document_id, page_number=1, image_path="/stub/p1.png")]


class StubEncoder(BaseEncoder):
    async def encode_documents(self, pages):
        return [Embedding(document_id=p.document_id, page_number=p.page_number, vectors=[[0.1]]) for p in pages]

    async def encode_query(self, query):
        return [[0.1]]


class StubRetriever(BaseRetriever):
    def __init__(self):
        self._store = []

    async def index(self, document_id, page_number, vectors, image_path):
        self._store.append({"document_id": document_id, "page_number": page_number, "image_path": image_path})

    async def retrieve(self, query_vectors, top_k=5):
        return [
            RetrievalResult(document_id=s["document_id"], page_number=s["page_number"], score=0.9, image_path=s["image_path"])
            for s in self._store[:top_k]
        ]

    async def delete(self, document_id):
        self._store = [s for s in self._store if s["document_id"] != document_id]


class StubGenerator(BaseGenerator):
    async def generate(self, query, context):
        return Answer(text=f"Answer to: {query}", sources=context)


@pytest.fixture
def app_with_stubs(tmp_path):
    retriever = StubRetriever()
    pipeline = Pipeline(
        processor=StubProcessor(),
        document_encoder=StubEncoder(),
        query_encoder=StubEncoder(),
        retriever=retriever,
        reranker=None,
        generator=StubGenerator(),
    )

    registries = {
        "processor": Registry("processor"),
        "document_encoder": Registry("document_encoder"),
        "query_encoder": Registry("query_encoder"),
        "retriever": Registry("retriever"),
        "reranker": Registry("reranker"),
        "generator": Registry("generator"),
    }
    manager = PipelineManager(registries)
    manager.pipeline = pipeline
    manager._current_config = {"processor": "stub", "document_encoder": "stub",
                               "query_encoder": "stub", "retriever": "stub",
                               "reranker": None, "generator": "stub"}

    doc_service = DocumentService(upload_dir=str(tmp_path / "uploads"), pipeline=pipeline)

    mock_worker = MagicMock()
    mock_worker.health = AsyncMock(return_value={"status": "ok", "model": "stub"})

    return create_app(
        worker_client=mock_worker,
        pipeline_manager=manager,
        document_service=doc_service,
    )


@pytest.mark.asyncio
async def test_upload_and_query_flow(app_with_stubs):
    transport = ASGITransport(app=app_with_stubs)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Upload
        resp = await client.post(
            "/api/documents/upload",
            files={"file": ("test.pdf", b"%PDF fake", "application/pdf")},
        )
        assert resp.status_code == 200
        doc_id = resp.json()["id"]

        # Wait briefly for background indexing (in test it's near-instant with stubs)
        import asyncio
        await asyncio.sleep(0.1)

        # Query
        resp = await client.post("/api/query", json={"query": "what is this?", "top_k": 3})
        assert resp.status_code == 200
        data = resp.json()
        assert "Answer to:" in data["answer"]
        assert len(data["sources"]) >= 1

        # Retrieve only
        resp = await client.post("/api/retrieve", json={"query": "test", "top_k": 3})
        assert resp.status_code == 200
        assert len(resp.json()["results"]) >= 1

        # Health
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        assert resp.json()["worker"]["status"] == "ok"

        # Pipelines
        resp = await client.get("/api/pipelines")
        assert resp.status_code == 200
        assert resp.json()["current"]["processor"] == "stub"
```

- [ ] **Step 2: Run integration test**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/test_integration.py -v
```

Expected: 1 passed

- [ ] **Step 3: Run all tests**

```bash
cd /c/bzli/paper/agent && python -m pytest tests/ -v
```

Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "feat: full integration test with stub pipeline"
```

---

## Summary

| Task | Component | Description |
|------|-----------|-------------|
| 1 | Scaffolding | Project structure, config loading |
| 2 | Registry | Strategy registration system |
| 3 | Interfaces | Abstract base classes + data models |
| 4 | Pipeline | Pipeline assembler & runner |
| 5 | Strategies Init | Global registries, auto-import |
| 6 | Worker Client | HTTP client for remote GPU worker |
| 7 | Processor | Page screenshot processor |
| 8 | Encoder | ColPali encoder strategy |
| 9 | Retriever | Multi-vector Qdrant retriever |
| 10 | Generators | GPT-4o + Claude generators |
| 11 | Document Service | Upload, index, delete lifecycle |
| 12 | Evaluation | Recall@K, MRR metrics |
| 13 | API Routes | FastAPI app + all route handlers |
| 14 | Worker | Remote GPU worker service |
| 15 | Scripts | SSH tunnel + deploy scripts |
| 16 | Frontend Setup | Vue 3 + Router + API client |
| 17 | Documents View | Upload + list UI |
| 18 | Query View | Search + answer + evidence UI |
| 19 | Experiment View | Pipeline switch + batch eval UI |
| 20 | System View | Health status UI |
| 21 | Entry Point | run.py + static serving |
| 22 | Integration Test | End-to-end test with stubs |
