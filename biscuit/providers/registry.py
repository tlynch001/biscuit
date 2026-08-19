"""Tiny, dependency-free provider registry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Generic, TypeVar

from biscuit.exceptions import ProviderNotFoundError

T = TypeVar("T")


class ProviderRegistry(Generic[T]):
    def __init__(self, category: str) -> None:
        self._category = category
        self._providers: dict[str, type[T]] = {}

    def register(self, name: str) -> Callable[[type[T]], type[T]]:
        def decorator(cls: type[T]) -> type[T]:
            if name in self._providers and self._providers[name] is not cls:
                raise ValueError(
                    f"A {self._category} provider named {name!r} is already registered "
                    f"({self._providers[name].__qualname__})."
                )
            cls.name = name  # type: ignore[attr-defined]
            self._providers[name] = cls
            return cls

        return decorator

    def get(self, name: str) -> type[T]:
        try:
            return self._providers[name]
        except KeyError as exc:
            available = ", ".join(sorted(self._providers)) or "<none registered>"
            raise ProviderNotFoundError(
                f"No {self._category} provider named {name!r}. Available: {available}"
            ) from exc

    def create(self, name: str, /, **kwargs: object) -> T:
        return self.get(name)(**kwargs)

    def available(self) -> list[str]:
        return sorted(self._providers)


story_registry: ProviderRegistry = ProviderRegistry("story")
image_registry: ProviderRegistry = ProviderRegistry("image")
narration_registry: ProviderRegistry = ProviderRegistry("narration")


def load_builtin_providers() -> None:
    """Import built-in provider modules so their registration decorators run."""

    from biscuit.providers import (  # noqa: F401
        image_development,
        image_openai,
        narration_development,
        narration_elevenlabs,
        story_template,
    )
