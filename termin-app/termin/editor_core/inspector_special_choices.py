"""UI-neutral dynamic choices for specialized inspector field kinds."""

from __future__ import annotations

from collections.abc import Callable
import logging
from typing import Any, Protocol


_logger = logging.getLogger(__name__)
InspectorChoices = tuple[tuple[Any, str], ...]


class InspectorSpecialChoiceProvider(Protocol):
    def choices(self, kind: str, targets: tuple[Any, ...]) -> InspectorChoices | None: ...


def _navigation_settings():
    from termin.navmesh.settings import NavigationSettingsManager

    return NavigationSettingsManager.instance()


def _target_clips(targets: tuple[Any, ...]) -> tuple[Any, ...]:
    if not targets:
        return ()
    target = targets[0]
    from termin.scene import TcComponentRef

    if isinstance(target, TcComponentRef):
        clips = target.get_field("clips")
    else:
        from termin.inspect import InspectRegistry

        clips = InspectRegistry.instance().get(target, "clips")
    return tuple(clips or ())


def _clip_name(clip: Any) -> str:
    if isinstance(clip, dict):
        return str(clip.get("name") or "")
    name_member = clip.name
    name = name_member() if callable(name_member) else name_member
    return str(name or "")


class InspectorSpecialChoices:
    def __init__(
        self,
        *,
        navigation_settings: Callable[[], Any] = _navigation_settings,
        target_clips: Callable[[tuple[Any, ...]], tuple[Any, ...]] = _target_clips,
        navmesh_area_count: int = 64,
    ) -> None:
        if navmesh_area_count <= 0:
            raise ValueError("navmesh area count must be positive")
        self._navigation_settings = navigation_settings
        self._target_clips = target_clips
        self._navmesh_area_count = navmesh_area_count

    def choices(self, kind: str, targets: tuple[Any, ...]) -> InspectorChoices | None:
        try:
            if kind == "agent_type":
                names = self._navigation_settings().settings.get_agent_type_names()
                return tuple((name, name) for name in names)
            if kind == "navmesh_area":
                manager = self._navigation_settings()
                return tuple(
                    (index, f"{index}: {manager.navmesh_area_label(index)}")
                    for index in range(self._navmesh_area_count)
                )
            if kind == "clip_selector":
                names = sorted(
                    {
                        name
                        for clip in self._target_clips(targets)
                        if (name := _clip_name(clip))
                    }
                )
                return (("", "(none)"), *((name, name) for name in names))
        except Exception:
            _logger.exception("Failed to collect specialized inspector choices for '%s'", kind)
            raise
        return None


__all__ = [
    "InspectorChoices",
    "InspectorSpecialChoiceProvider",
    "InspectorSpecialChoices",
]
