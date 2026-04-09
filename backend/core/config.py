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
