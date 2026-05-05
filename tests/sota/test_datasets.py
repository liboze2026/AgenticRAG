import json

import pytest

from backend.sota.datasets import (
    DatasetIntegrity, SUBSETS, count_local_queries, load_local_queries,
)


@pytest.fixture
def fake_root(tmp_path):
    for subset in ("feta_tab", "slidevqa"):
        d = tmp_path / subset
        d.mkdir()
        with open(d / "queries.jsonl", "w") as f:
            for i in range(3):
                f.write(json.dumps({
                    "query_id": f"{subset}_{i}",
                    "query": f"q {i}",
                    "gold_doc_ids": [f"doc_{i}"],
                    "gold_page_numbers": [i + 1],
                }) + "\n")
    return str(tmp_path)


def test_subsets_constant_matches_server_layout():
    # The active server stores 5 VisDoM subsets; MMLongBench is absent.
    assert SUBSETS == ("feta_tab", "paper_tab", "scigraphvqa", "slidevqa", "spiqa")


def test_count_local_queries(fake_root):
    assert count_local_queries(fake_root, "feta_tab") == 3
    assert count_local_queries(fake_root, "scigraphvqa") == 0


def test_load_local_queries(fake_root):
    qs = list(load_local_queries(fake_root, "feta_tab", limit=2))
    assert len(qs) == 2
    assert qs[0].query_id == "feta_tab_0"
    assert qs[0].gold_pages == [("doc_0", 1)]


def test_integrity_check_partial(fake_root):
    integ = DatasetIntegrity.scan(fake_root)
    assert integ.subsets["feta_tab"]["status"] == "ok"
    assert integ.subsets["feta_tab"]["query_count"] == 3
    assert integ.subsets["scigraphvqa"]["status"] == "missing"
    assert integ.subsets["slidevqa"]["status"] == "ok"
    assert integ.subsets["paper_tab"]["status"] == "missing"
    assert integ.subsets["spiqa"]["status"] == "missing"
