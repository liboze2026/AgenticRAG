import asyncio
import os

import pytest

from backend.sota.runs import RunRegistry
from backend.sota.schemas import (
    MethodResult, MethodStatus, MetricCell, RunConfig, RunStatus,
)


@pytest.fixture
def tmp_registry(tmp_path):
    return RunRegistry(root=str(tmp_path))


@pytest.mark.asyncio
async def test_create_run_returns_uuid_and_persists(tmp_registry):
    cfg = RunConfig(subsets=["fetatab"], methods=["baseline_colpali"], n_queries_per_subset=10)
    run_id = await tmp_registry.create_run(cfg)
    assert run_id

    summary = await tmp_registry.get_run(run_id)
    assert summary.id == run_id
    assert summary.status == RunStatus.QUEUED
    assert summary.config.subsets == ["fetatab"]


@pytest.mark.asyncio
async def test_append_metric_and_method_status(tmp_registry):
    cfg = RunConfig(subsets=["fetatab"], methods=["baseline_colpali"], n_queries_per_subset=10)
    run_id = await tmp_registry.create_run(cfg)

    await tmp_registry.set_run_status(run_id, RunStatus.RUNNING)
    await tmp_registry.append_metric(run_id, MetricCell(
        method="baseline_colpali", subset="fetatab",
        metric="recall@1", value=0.82, n_queries=10,
    ))
    await tmp_registry.upsert_method_result(run_id, MethodResult(
        method="baseline_colpali", status=MethodStatus.OK, duration_ms=1500,
    ))

    summary = await tmp_registry.get_run(run_id)
    assert summary.status == RunStatus.RUNNING
    assert len(summary.metrics) == 1
    assert summary.metrics[0].value == pytest.approx(0.82)
    assert summary.methods[0].status == MethodStatus.OK


@pytest.mark.asyncio
async def test_list_runs_orders_by_created_at_desc(tmp_registry):
    cfg = RunConfig(n_queries_per_subset=10)
    a = await tmp_registry.create_run(cfg)
    await asyncio.sleep(0.01)
    b = await tmp_registry.create_run(cfg)
    rows = await tmp_registry.list_runs(limit=10)
    assert rows[0].id == b
    assert rows[1].id == a


@pytest.mark.asyncio
async def test_jsonl_mirror_appends_each_event(tmp_registry, tmp_path):
    cfg = RunConfig(n_queries_per_subset=10)
    run_id = await tmp_registry.create_run(cfg)
    await tmp_registry.append_query_trace(run_id, {"query_id": "q1", "method": "baseline_colpali", "rr": 1.0})
    await tmp_registry.append_query_trace(run_id, {"query_id": "q2", "method": "baseline_colpali", "rr": 0.5})

    queries_path = os.path.join(str(tmp_path), run_id, "queries.jsonl")
    assert os.path.exists(queries_path)
    with open(queries_path) as f:
        lines = f.readlines()
    assert len(lines) == 2
    assert "q1" in lines[0]


@pytest.mark.asyncio
async def test_run_not_found_raises(tmp_registry):
    from backend.sota.error_envelope import SotaError
    with pytest.raises(SotaError):
        await tmp_registry.get_run("does-not-exist")
