import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel

StrategySpec = Union[str, Dict[str, Any]]


class ServerConfig(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: List[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]


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
    processor: StrategySpec = "page_screenshot"
    document_encoder: StrategySpec = "colpali"
    query_encoder: StrategySpec = "colpali"
    retriever: StrategySpec = "multi_vector"
    reranker: Optional[StrategySpec] = None
    generator: StrategySpec = "openai_gpt4o"


class ApiKeysConfig(BaseModel):
    openai: str = ""
    anthropic: str = ""


class CacheConfig(BaseModel):
    enabled: bool = False
    query_cache_dir: str = "data/cache/query"
    generation_cache_dir: str = "data/cache/generation"


class AppConfig(BaseModel):
    server: ServerConfig = ServerConfig()
    worker: WorkerConfig = WorkerConfig()
    qdrant: QdrantConfig = QdrantConfig()
    storage: StorageConfig = StorageConfig()
    pipeline: PipelineConfig = PipelineConfig()
    api_keys: ApiKeysConfig = ApiKeysConfig()
    cache: CacheConfig = CacheConfig()


def _substitute_env_vars(text: str) -> str:
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
