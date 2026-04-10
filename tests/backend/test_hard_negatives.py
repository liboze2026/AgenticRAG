from backend.services.hard_negatives import mine_hard_negatives, augment_eval_set


def test_mine_hard_negatives_basic():
    relevant = ["doc1:5"]
    all_pages = {"doc1": 10}
    negs = mine_hard_negatives(relevant, all_pages, window=2)
    assert set(negs) == {"doc1:3", "doc1:4", "doc1:6", "doc1:7"}


def test_mine_excludes_relevant():
    relevant = ["doc1:3", "doc1:5"]
    all_pages = {"doc1": 10}
    negs = mine_hard_negatives(relevant, all_pages, window=2)
    # 3 and 5 are relevant; window from 3: {1,2,4,5}; window from 5: {3,4,6,7}
    # exclude relevant {3,5}: {1, 2, 4, 6, 7}
    assert set(negs) == {"doc1:1", "doc1:2", "doc1:4", "doc1:6", "doc1:7"}


def test_mine_respects_page_bounds():
    relevant = ["doc1:1"]
    all_pages = {"doc1": 3}
    negs = mine_hard_negatives(relevant, all_pages, window=5)
    assert set(negs) == {"doc1:2", "doc1:3"}


def test_augment_eval_set_adds_field():
    eval_data = [{"query": "q1", "relevant": ["doc1:5"]}]
    all_pages = {"doc1": 10}
    augmented = augment_eval_set(eval_data, all_pages, window=1)
    assert augmented[0]["query"] == "q1"
    assert augmented[0]["relevant"] == ["doc1:5"]
    assert "hard_negatives" in augmented[0]
    assert set(augmented[0]["hard_negatives"]) == {"doc1:4", "doc1:6"}
