import pytest
from backend.services.dataset_service import DatasetService


@pytest.fixture
def svc(tmp_path):
    return DatasetService(db_path=str(tmp_path / "ds.db"))


def test_create_and_get(svc):
    ds = svc.create("baseline", "first dataset")
    assert ds.id == 1
    assert ds.name == "baseline"
    fetched = svc.get(ds.id)
    assert fetched.name == "baseline"


def test_unique_name(svc):
    svc.create("dup")
    with pytest.raises(ValueError):
        svc.create("dup")


def test_list_with_counts(svc):
    a = svc.create("a")
    b = svc.create("b")
    rows = svc.list_all(document_counts={a.id: 5, b.id: 2})
    assert len(rows) == 2
    assert rows[0].document_count == 5
    assert rows[1].document_count == 2


def test_delete(svc):
    ds = svc.create("temp")
    assert svc.delete(ds.id) is True
    assert svc.get(ds.id) is None
    assert svc.delete(ds.id) is False
