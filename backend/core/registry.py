from typing import Dict, List, Type


class Registry:
    """A named registry that maps string keys to classes."""

    def __init__(self, category: str):
        self.category = category
        self._entries: Dict[str, Type] = {}

    def register(self, name: str):
        """Decorator to register a class under the given name."""
        def decorator(cls: Type) -> Type:
            if name in self._entries:
                raise ValueError(
                    f"{self.category} '{name}' already registered"
                )
            self._entries[name] = cls
            return cls
        return decorator

    def get(self, name: str) -> Type:
        if name not in self._entries:
            raise KeyError(
                f"{self.category} '{name}' not registered. "
                f"Available: {list(self._entries.keys())}"
            )
        return self._entries[name]

    def list(self) -> List[str]:
        return list(self._entries.keys())
