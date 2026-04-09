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
