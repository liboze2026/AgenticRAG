"""Shared fixtures for e2e tests.

Run e2e tests: pytest -m e2e
Skip e2e tests: pytest -m "not e2e"

Requires all services running:
  python run.py   (or start.bat)
"""
import time
import pytest
import httpx

BASE_URL = "http://localhost:8000"


def _make_pdf_bytes() -> bytes:
    """Generate a minimal valid single-page PDF with readable text."""
    content = b"BT /F1 12 Tf 72 720 Td (Agentic RAG e2e test document. Retrieval and indexing test.) Tj ET"
    objs = [
        b"1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n",
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n",
        (
            b"3 0 obj\n<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
            b" /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>\nendobj\n"
        ),
        (
            b"4 0 obj\n<< /Length "
            + str(len(content)).encode()
            + b" >>\nstream\n"
            + content
            + b"\nendstream\nendobj\n"
        ),
        b"5 0 obj\n<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>\nendobj\n",
    ]
    pdf = b"%PDF-1.4\n"
    offsets = []
    for obj in objs:
        offsets.append(len(pdf))
        pdf += obj
    xref_pos = len(pdf)
    pdf += b"xref\n"
    pdf += f"0 {len(objs) + 1}\n".encode()
    pdf += b"0000000000 65535 f \n"
    for off in offsets:
        pdf += f"{off:010d} 00000 n \n".encode()
    pdf += b"trailer\n"
    pdf += f"<< /Size {len(objs) + 1} /Root 1 0 R >>\n".encode()
    pdf += b"startxref\n"
    pdf += f"{xref_pos}\n".encode()
    pdf += b"%%EOF\n"
    return pdf


@pytest.fixture(scope="session")
def base_url() -> str:
    return BASE_URL


@pytest.fixture(scope="session")
def minimal_pdf() -> bytes:
    return _make_pdf_bytes()


@pytest.fixture(scope="session", autouse=True)
def require_services(base_url):
    """Skip entire e2e suite if services are not running."""
    try:
        r = httpx.get(f"{base_url}/api/health", timeout=10)
        r.raise_for_status()
        health = r.json()
    except Exception as exc:
        pytest.skip(f"Backend not reachable at {base_url}: {exc}")
    if health.get("worker", {}).get("status") != "ok":
        pytest.skip(f"Worker not available: {health.get('worker')}")
    if health.get("qdrant", {}).get("status") != "ok":
        pytest.skip(f"Qdrant not available: {health.get('qdrant')}")


@pytest.fixture(scope="session")
def client(base_url, require_services):
    with httpx.Client(base_url=base_url, timeout=60) as c:
        yield c


def wait_indexed(client: httpx.Client, doc_id: str, timeout: int = 180) -> dict:
    """Poll document status until completed or failed. Returns final doc dict."""
    for _ in range(timeout):
        r = client.get(f"/api/documents/{doc_id}/status")
        if r.status_code != 200:
            pytest.fail(f"Status check failed ({r.status_code}): {r.text}")
        doc = r.json()
        if doc["status"] == "completed":
            return doc
        if doc["status"] == "failed":
            pytest.fail(f"Document indexing failed for {doc_id}: {doc}")
        time.sleep(1)
    pytest.fail(f"Document indexing timed out after {timeout}s for {doc_id}")


@pytest.fixture(scope="module")
def indexed_doc(client, minimal_pdf):
    """Upload and index a document. Shared per test module. Cleaned up after module."""
    r = client.post(
        "/api/documents/upload",
        files={"file": ("e2e_test.pdf", minimal_pdf, "application/pdf")},
    )
    assert r.status_code == 200, f"Upload failed: {r.text}"
    doc_id = r.json()["id"]
    wait_indexed(client, doc_id)
    yield doc_id
    # Cleanup
    try:
        client.delete(f"/api/documents/{doc_id}")
    except Exception as exc:
        import warnings
        warnings.warn(f"indexed_doc cleanup failed for {doc_id}: {exc}")
