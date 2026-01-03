"""
ImmediateRenderer - immediate mode rendering for debug visualization, gizmos, etc.

Implemented in C++ for performance. This module re-exports from native.
"""

from termin._native.render import ImmediateRenderer as _ImmediateRenderer


class ImmediateRenderer(_ImmediateRenderer):
    """
    Singleton wrapper around native ImmediateRenderer.

    Позволяет вызывать из любого компонента:
        from termin.visualization.render.immediate import ImmediateRenderer
        ImmediateRenderer.instance().line(start, end, color)
    """

    _instance: "ImmediateRenderer | None" = None

    def __init__(self):
        super().__init__()
        ImmediateRenderer._instance = self

    @classmethod
    def instance(cls) -> "ImmediateRenderer | None":
        """Получить глобальный экземпляр (None если ещё не создан)."""
        return cls._instance


__all__ = ["ImmediateRenderer"]
