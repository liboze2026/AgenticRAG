"""E2E tests: document upload, indexing lifecycle, status transitions, delete."""
import pytest
import httpx
import time
from tests.e2e.conftest import wait_indexed


pytestmark = pytest.mark.e2e


def test_upload_returns_doc_id(client, minimal_pdf):
    r = client.post(
        "/api/documents/upload",
        files={"file": ("flow_test.pdf", minimal_pdf, "application/pdf")},
    )
    assert r.status_code == 200
    data = r.json()
    assert "id" in data
    assert data["filename"] == "flow_test.pdf"
    assert data["status"] in ("pending", "indexing", "completed")
    # cleanup
    client.delete(f"/api/documents/{data['id']}")


def test_upload_then_index_completes(client, minimal_pdf):
    r = client.post(
        "/api/documents/upload",
        files={"file": ("index_test.pdf", minimal_pdf, "application/pdf")},
    )
    assert r.status_code == 200
    doc_id = r.json()["id"]

    doc = wait_indexed(client, doc_id)
    assert doc["status"] == "completed"
    # indexed_pages must equal total_pages (white-box: no pages dropped)
    assert doc["indexed_pages"] == doc["total_pages"]
    assert doc["total_pages"] >= 1

    client.delete(f"/api/documents/{doc_id}")


def test_status_endpoint_matches_list(client, indexed_doc):
    # GET /{id}/status and GET /{id} must return same data
    r_status = client.get(f"/api/documents/{indexed_doc}/status")
    r_detail = client.get(f"/api/documents/{indexed_doc}")
    assert r_status.status_code == 200
    assert r_detail.status_code == 200
    assert r_status.json()["status"] == r_detail.json()["status"]


def test_document_appears_in_list(client, indexed_doc):
    r = client.get("/api/documents")
    assert r.status_code == 200
    doc_ids = [d["id"] for d in r.json()]
    assert indexed_doc in doc_ids


def test_delete_document_removes_it(client, minimal_pdf):
    r = client.post(
        "/api/documents/upload",
        files={"file": ("delete_test.pdf", minimal_pdf, "application/pdf")},
    )
    assert r.status_code == 200
    doc_id = r.json()["id"]

    del_r = client.delete(f"/api/documents/{doc_id}")
    assert del_r.status_code == 200

    # GET should now 404
    get_r = client.get(f"/api/documents/{doc_id}")
    assert get_r.status_code == 404

    # List should not contain it
    list_r = client.get("/api/documents")
    assert all(d["id"] != doc_id for d in list_r.json())


def test_delete_nonexistent_returns_404(client):
    r = client.delete("/api/documents/nonexistent-id-xyz")
    assert r.status_code == 404


def test_get_nonexistent_returns_404(client):
    r = client.get("/api/documents/nonexistent-id-xyz")
    assert r.status_code == 404


def test_retry_rejected_for_completed_doc(client, indexed_doc):
    r = client.post(f"/api/documents/{indexed_doc}/retry")
    # completed doc cannot be retried
    assert r.status_code == 400
    assert "Cannot retry" in r.json()["detail"]
