import pytest
from backend.services.experiment_service import ExperimentService


@pytest.fixture
def svc(tmp_path):
    return ExperimentService(db_path=str(tmp_path / "exp.db"))


def test_record_and_list(svc):
    exp_id = svc.record(
        pipeline_config={"retriever": "multi_vector"},
        metrics={"mrr": 0.85, "recall_at_k": {1: 0.6, 5: 0.9}},
        total_queries=10,
        note="baseline run",
    )
    assert exp_id == 1
    rows = svc.list_experiments()
    assert len(rows) == 1
    assert rows[0]["pipeline_config"]["retriever"] == "multi_vector"
    assert rows[0]["metrics"]["mrr"] == 0.85
    assert rows[0]["note"] == "baseline run"


def test_get_experiment(svc):
    exp_id = svc.record(pipeline_config={}, metrics={}, total_queries=0)
    exp = svc.get_experiment(exp_id)
    assert exp is not None
    assert exp["id"] == exp_id
    assert svc.get_experiment(999) is None


def test_delete_experiment(svc):
    exp_id = svc.record(pipeline_config={}, metrics={}, total_queries=0)
    assert svc.delete_experiment(exp_id) is True
    assert svc.get_experiment(exp_id) is None
    assert svc.delete_experiment(exp_id) is False


def test_list_ordering_newest_first(svc):
    a = svc.record(pipeline_config={"v": 1}, metrics={}, total_queries=0)
    b = svc.record(pipeline_config={"v": 2}, metrics={}, total_queries=0)
    rows = svc.list_experiments()
    assert rows[0]["id"] == b
    assert rows[1]["id"] == a
