import json

import pytest

from backend.sota.executor import RunExecutor
from backend.sota.methods import METHOD_REGISTRY, MethodMeta, register
from backend.sota.runs import RunRegistry
from backend.sota.schemas import RunConfig, RunStatus


@pytest.fixture
def fake_dataset_root(tmp_path):
    sub = tmp_path / "fetatab"
    sub.mkdir()  # mismatched name vs SUBSETS is fine; executor doesn't validate here
    with open(sub / "queries.jsonl", "w") as f:
        for i in range(3):
            f.write(json.dumps({
                "query_id": f"q{i}", "query": f"text {i}",
                "gold_doc_ids": ["doc"], "gold_page_numbers": [i + 1],
            }) + "\n")
    return str(tmp_path)


@pytest.fixture
def stub_method():
    async def _run(query, top_k, ctx):
        # `query` is now SotaQuery; we just emit a fixed ranking.
        return [("doc", 1, 1.0), ("doc", 2, 0.9), ("doc", 3, 0.8)]
    register(MethodMeta(
        name="stub_method", version="t",
        description="test", needs=[], uses_test_labels=False, run=_run,
    ))
    yield "stub_method"
    METHOD_REGISTRY.pop("stub_method", None)


@pytest.mark.asyncio
async def test_executor_runs_and_writes_metrics(tmp_path, fake_dataset_root, stub_method):
    registry = RunRegistry(root=str(tmp_path / "runs"))
    cfg = RunConfig(
        subsets=["fetatab"], methods=[stub_method],
        n_queries_per_subset=3, top_k=5, split="all",
    )
    run_id = await registry.create_run(cfg)
    ex = RunExecutor(
        registry, fake_dataset_root,
        pipeline=None, lab_bundle=None,
        qdrant_client=None, worker_client=None,
    )
    await ex.execute(run_id, cfg)

    summary = await registry.get_run(run_id)
    assert summary.status in {RunStatus.COMPLETED, RunStatus.PARTIAL}
    assert any(m.method == stub_method for m in summary.metrics)
    r1 = next(m for m in summary.metrics if m.metric == "recall@1")
    # q0 hit (gold=p1 at rank 0); q1, q2 miss → 1/3
    assert r1.value == pytest.approx(1 / 3, abs=0.01)
