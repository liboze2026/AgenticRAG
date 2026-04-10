import pytest
from backend.core.registry import Registry


def test_register_and_get():
    registry = Registry("encoder")

    @registry.register("test_encoder")
    class TestEncoder:
        pass

    cls = registry.get("test_encoder")
    assert cls is TestEncoder


def test_get_unregistered_raises():
    registry = Registry("encoder")
    with pytest.raises(KeyError, match="encoder.*not_registered"):
        registry.get("not_registered")


def test_list_registered():
    registry = Registry("processor")

    @registry.register("a")
    class A:
        pass

    @registry.register("b")
    class B:
        pass

    names = registry.list()
    assert set(names) == {"a", "b"}


def test_duplicate_register_raises():
    registry = Registry("retriever")

    @registry.register("dup")
    class First:
        pass

    with pytest.raises(ValueError, match="already registered"):
        @registry.register("dup")
        class Second:
            pass
