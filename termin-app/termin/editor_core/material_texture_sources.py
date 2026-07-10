"""UI-neutral material texture source discovery and render-target resolution."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable


_logger = logging.getLogger(__name__)
SceneGetter = Callable[[], Any]
RenderTargetPoolGetter = Callable[[], tuple[Any, ...]]


def _live_render_targets() -> tuple[Any, ...]:
    from termin.render_framework import render_target_pool_list

    return tuple(render_target_pool_list())


def resolve_live_render_target_texture(
    name: str,
    channel: str,
    *,
    render_target_pool: RenderTargetPoolGetter = _live_render_targets,
):
    for handle in render_target_pool():
        if not handle.alive or handle.name != name:
            continue
        handle.ensure_textures()
        return handle.depth_texture if channel == "depth" else handle.color_texture
    _logger.error("Live render target texture not found: %s/%s", name, channel)
    return None


@dataclass(frozen=True)
class MaterialTextureSource:
    label: str
    tag: str
    name: str


class MaterialTextureSourceCatalog:
    def __init__(
        self,
        resource_manager,
        *,
        scene_getter: SceneGetter | None = None,
        render_target_pool: RenderTargetPoolGetter = _live_render_targets,
    ) -> None:
        self._resource_manager = resource_manager
        self._scene_getter = scene_getter
        self._render_target_pool = render_target_pool

    def set_scene_getter(self, getter: SceneGetter | None) -> None:
        self._scene_getter = getter

    def choices(self, default_kind: str = "white") -> tuple[MaterialTextureSource, ...]:
        entries = [MaterialTextureSource(f"Default ({default_kind})", "default", "")]
        entries.extend(self._render_target_sources())
        entries.extend(
            MaterialTextureSource(name, "file", name)
            for name in self._resource_manager.list_texture_names()
            if name != "__white_1x1__"
        )
        result = []
        seen = set()
        for entry in entries:
            identity = (entry.tag, entry.name)
            if identity in seen:
                continue
            seen.add(identity)
            result.append(entry)
        return tuple(result)

    def resolve_render_target(self, name: str, channel: str):
        return resolve_live_render_target_texture(
            name,
            channel,
            render_target_pool=self._render_target_pool,
        )

    def _render_target_sources(self) -> list[MaterialTextureSource]:
        names = set()
        if self._scene_getter is not None:
            try:
                value = self._scene_getter()
                scenes = value if isinstance(value, (tuple, list)) else [value]
                from termin.render import scene_render_mount

                for scene in scenes:
                    if scene is None:
                        continue
                    for config in scene_render_mount(scene).render_target_configs:
                        if config.kind == "texture_2d" and config.name:
                            names.add(config.name)
            except Exception:
                _logger.exception("Failed to enumerate scene render target textures")
        try:
            names.update(
                handle.name
                for handle in self._render_target_pool()
                if handle.alive and handle.kind == "texture_2d" and handle.name
            )
        except Exception:
            _logger.exception("Failed to enumerate live render target textures")
        entries = []
        for name in sorted(names):
            entries.append(MaterialTextureSource(f"{name} (Color)", "rt_color", name))
            entries.append(MaterialTextureSource(f"{name} (Depth)", "rt_depth", name))
        return entries


__all__ = [
    "MaterialTextureSource",
    "MaterialTextureSourceCatalog",
    "resolve_live_render_target_texture",
]
