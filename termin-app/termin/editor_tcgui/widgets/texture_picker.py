"""Unified texture picker widget for tcgui inspectors.

Combines file-based textures (TextureAsset registry) and render-target
textures (color/depth) in a single combo with optional GPU preview.
"""

from __future__ import annotations

from typing import Any, Callable, Optional

import numpy as np

from tcbase import log
from tcgui.widgets.combo_box import ComboBox
from tcgui.widgets.hstack import HStack
from tcgui.widgets.units import px
from tcgui.widgets.widget import Widget


class TexturePreviewWidget(Widget):
    """Small texture preview widget (48x48) with placeholder text."""

    def __init__(self) -> None:
        super().__init__()
        self.preferred_width = px(48)
        self.preferred_height = px(48)
        self._image_data: np.ndarray | None = None
        self._gpu_texture: Any = None
        self._dirty: bool = False
        self._placeholder: str = "No\nTex"

    def set_image(self, data: Any, placeholder: str = "No\nTex") -> None:
        self._placeholder = placeholder
        self._image_data = None
        self._dirty = True

        if data is None:
            return

        try:
            arr = np.asarray(data)
            if arr.ndim != 3:
                return
            if arr.shape[2] == 4:
                self._image_data = np.ascontiguousarray(arr.astype(np.uint8))
            elif arr.shape[2] == 3:
                alpha = np.full((arr.shape[0], arr.shape[1], 1), 255, dtype=np.uint8)
                rgb = arr.astype(np.uint8)
                self._image_data = np.ascontiguousarray(np.concatenate([rgb, alpha], axis=2))
        except Exception as e:
            log.warn(f"[TexturePreviewWidget] failed to prepare texture preview image: {e}")
            self._image_data = None

    def _sync_texture(self, renderer: Any) -> None:
        if not self._dirty:
            return
        self._dirty = False

        if self._gpu_texture is not None:
            try:
                renderer.destroy_texture(self._gpu_texture)
            except Exception as e:
                log.warn(f"[TexturePreviewWidget] failed to delete old texture preview: {e}")
            self._gpu_texture = None

        if self._image_data is not None:
            try:
                self._gpu_texture = renderer.upload_texture(self._image_data)
            except Exception as e:
                log.error(f"[TexturePreviewWidget] failed to upload texture preview: {e}")
                self._gpu_texture = None

    def render(self, renderer: Any) -> None:
        self._sync_texture(renderer)

        renderer.draw_rect(self.x, self.y, self.width, self.height, (0.17, 0.18, 0.22, 1.0))
        renderer.draw_rect_outline(self.x, self.y, self.width, self.height, (0.36, 0.38, 0.44, 1.0), 1.0)

        if self._gpu_texture is not None:
            renderer.draw_image(self.x + 1, self.y + 1, self.width - 2, self.height - 2, self._gpu_texture)
        else:
            renderer.draw_text_centered(
                self.x + self.width * 0.5,
                self.y + self.height * 0.5,
                self._placeholder,
                (0.56, 0.58, 0.64, 1.0),
                10.0,
            )


class TexturePickerWidget(HStack):
    """Texture selector with preview and combo box.

    Shows file-based textures from the asset registry and render-target
    textures (color/depth) from the RT pool.  Calls ``on_changed(tag, value)``
    on selection change:

    ============== =============================================
    tag            value
    ============== =============================================
    ``"default"``  ``""`` (no texture selected)
    ``"file"``     asset name (e.g. ``"my_texture"``)
    ``"rt_color"`` render-target name
    ``"rt_depth"`` render-target name
    ============== =============================================
    """

    # Display names shown in the combo for RT textures.
    _RT_COLOR_SUFFIX: str = " (Color)"
    _RT_DEPTH_SUFFIX: str = " (Depth)"

    def __init__(
        self,
        resource_manager: Any,
        on_changed: Callable[[str, str], None],
        scene_getter: Optional[Callable[[], list[Any]]] = None,
        default_texture_kind: str = "white",
        show_preview: bool = True,
    ) -> None:
        super().__init__()
        self.spacing = 8

        self._rm: Any = resource_manager
        self._on_changed: Callable[[str, str], None] = on_changed
        self._scene_getter: Optional[Callable[[], list[Any]]] = scene_getter
        self._default_texture_kind: str = default_texture_kind
        self._show_preview: bool = show_preview
        self._updating: bool = False

        # Parallel lists indexed by combo item index.
        self._item_tags: list[str] = []
        self._item_values: list[str] = []

        self._preview: Optional[TexturePreviewWidget] = None
        if show_preview:
            self._preview = TexturePreviewWidget()
            self.add_child(self._preview)

        self._combo: ComboBox = ComboBox()
        self._combo.stretch = True
        self._combo.on_changed = self._on_combo_changed
        self.add_child(self._combo)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_value(self, name: str, tag: str) -> None:
        """Populate combo and select the item matching *tag* / *name*."""
        self._updating = True
        try:
            self._populate()

            found = False
            for i in range(self._combo.item_count):
                if i < len(self._item_tags) and i < len(self._item_values):
                    if self._item_tags[i] == tag and self._item_values[i] == name:
                        self._combo.selected_index = i
                        found = True
                        break

            if not found:
                self._combo.selected_index = 0

            self._update_preview(self._combo.selected_index)
        finally:
            self._updating = False

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------

    def _populate(self) -> None:
        """Rebuild combo items and parallel tag / value lists."""
        old_cb = self._combo.on_changed
        self._combo.on_changed = None
        try:
            self._combo.clear()
            self._item_tags.clear()
            self._item_values.clear()

            # "(default)" is always first.
            self._combo.add_item("(default)")
            self._item_tags.append("default")
            self._item_values.append("")

            # Render-target textures are dynamic scene resources. Put them
            # before file textures so they stay visible in the combo popup
            # even when the project has many texture assets.
            self._add_rt_textures()

            # File-based textures.
            for tname in self._rm.list_texture_names():
                if tname == "__white_1x1__":
                    continue
                self._combo.add_item(tname)
                self._item_tags.append("file")
                self._item_values.append(tname)

            log.warn(
                f"[TexturePickerWidget] combo populated: "
                f"item_count={self._combo.item_count}, "
                f"items={list(zip(self._item_tags, self._item_values, self._combo.items, strict=True))}"
            )
        finally:
            self._combo.on_changed = old_cb

    def _add_rt_textures(self) -> None:
        """Append render-target color/depth textures to the combo."""
        try:
            entries = self._get_rt_entries()
        except Exception as e:
            log.warn(f"[TexturePickerWidget] Failed to enumerate RT textures: {e}")
            return

        for display_name, tag, rt_name in entries:
            self._combo.add_item(display_name)
            self._item_tags.append(tag)
            self._item_values.append(rt_name)

    def _get_rt_entries(self) -> list[tuple[str, str, str]]:
        """Return ``[(display_name, tag, rt_name), ...]`` for alive RTs.

        Uses *scene_getter* when available (RT-inspector path), otherwise
        falls back to the global ``render_target_pool_list()`` (material-inspector
        path).
        """
        entries: list[tuple[str, str, str]] = []
        scene_entries: list[tuple[str, str, str]] = []

        if self._scene_getter is not None:
            scene_entries = self._get_rt_entries_from_scenes()
            entries.extend(scene_entries)
        pool_entries = self._get_rt_entries_from_pool()
        entries.extend(pool_entries)

        entries = self._dedupe_rt_entries(entries)
        entries.sort(key=lambda e: e[0])
        log.warn(
            f"[TexturePickerWidget] RT enumeration summary: "
            f"scene_getter={self._scene_getter is not None}, "
            f"scene_entries={len(scene_entries)}, pool_entries={len(pool_entries)}, "
            f"deduped_entries={len(entries)}, "
            f"names={[display_name for display_name, _tag, _rt_name in entries]}"
        )
        return entries

    def _dedupe_rt_entries(self, entries: list[tuple[str, str, str]]) -> list[tuple[str, str, str]]:
        """Deduplicate entries by texture identity while preserving first label."""
        result: list[tuple[str, str, str]] = []
        seen: set[tuple[str, str]] = set()
        for display_name, tag, rt_name in entries:
            key = (tag, rt_name)
            if key in seen:
                continue
            seen.add(key)
            result.append((display_name, tag, rt_name))
        return result

    def _get_rt_entries_from_scenes(self) -> list[tuple[str, str, str]]:
        """Collect RT textures from scene render mounts."""
        entries: list[tuple[str, str, str]] = []
        try:
            from termin.scene_rendering import scene_render_mount

            scenes_value = self._scene_getter()
            if scenes_value is None:
                scenes = []
            elif isinstance(scenes_value, (list, tuple)):
                scenes = list(scenes_value)
            else:
                scenes = [scenes_value]
            log.warn(f"[TexturePickerWidget] scene_getter returned {len(scenes)} scene(s)")
            for scene in scenes:
                mount = scene_render_mount(scene)
                scene_name = scene.name or scene.uuid or repr(scene)
                configs = mount.render_target_configs
                log.warn(
                    f"[TexturePickerWidget] scene '{scene_name}' has "
                    f"{len(configs)} render_target_config(s)"
                )
                for rt in configs:
                    if rt.kind != "texture_2d":
                        continue
                    name = rt.name
                    if not name:
                        log.warn(f"[TexturePickerWidget] skipped unnamed render_target_config in scene '{scene_name}'")
                        continue
                    entries.append((f"{name}{self._RT_COLOR_SUFFIX}", "rt_color", name))
                    entries.append((f"{name}{self._RT_DEPTH_SUFFIX}", "rt_depth", name))
        except Exception as e:
            log.warn(f"[TexturePickerWidget] Scene RT enumeration failed: {e}")
        return entries

    def _get_rt_entries_from_pool(self) -> list[tuple[str, str, str]]:
        """Collect RT textures from the global render-target pool."""
        entries: list[tuple[str, str, str]] = []
        try:
            from termin.render_framework import render_target_pool_list
        except ImportError as e:
            log.warn(f"[TexturePickerWidget] render_framework import failed while enumerating RT textures: {e}")
            return entries

        try:
            pool = list(render_target_pool_list())
            log.warn(f"[TexturePickerWidget] render_target_pool_list returned {len(pool)} handle(s)")
            for h in pool:
                if not h.alive:
                    log.warn(f"[TexturePickerWidget] skipped dead RT handle {h.index}:{h.generation}")
                    continue
                if h.kind != "texture_2d":
                    continue
                name = h.name
                if not name:
                    log.warn(f"[TexturePickerWidget] skipped unnamed live RT handle {h.index}:{h.generation}")
                    continue
                entries.append((f"{name}{self._RT_COLOR_SUFFIX}", "rt_color", name))
                entries.append((f"{name}{self._RT_DEPTH_SUFFIX}", "rt_depth", name))
        except Exception as e:
            log.warn(f"[TexturePickerWidget] Pool RT enumeration failed: {e}")
        return entries

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------

    def _on_combo_changed(self, index: int, text: str) -> None:
        if index < 0 or index >= len(self._item_tags):
            return

        self._update_preview(index)

        if self._updating:
            return

        tag = self._item_tags[index]
        value = self._item_values[index]
        self._on_changed(tag, value)

    # ------------------------------------------------------------------
    # Preview
    # ------------------------------------------------------------------

    def _update_preview(self, index: int) -> None:
        if self._preview is None:
            return
        img, placeholder = self._resolve_preview_image(index)
        self._preview.set_image(img, placeholder=placeholder)

    def _resolve_preview_image(self, index: int) -> tuple[Any, str]:
        """Return ``(image_data, placeholder)`` for combo item at *index*."""
        if index < 0 or index >= len(self._item_tags):
            return None, "No\nTex"

        tag = self._item_tags[index]
        value = self._item_values[index]

        if tag == "default":
            return self._resolve_default_preview()

        if tag == "file":
            return self._resolve_file_preview(value)

        if tag in ("rt_color", "rt_depth"):
            return self._resolve_rt_preview(value, tag)

        return None, "No\nTex"

    def _resolve_default_preview(self) -> tuple[Any, str]:
        from termin.render.texture import (
            get_normal_texture,
            get_white_texture,
        )

        tex = get_normal_texture() if self._default_texture_kind == "normal" else get_white_texture()
        return tex._image_data, "default"

    def _resolve_file_preview(self, name: str) -> tuple[Any, str]:
        tex = self._rm.get_texture(name)
        if tex is None:
            return None, "No\nTex"
        return tex._image_data, "No\nTex"

    def _resolve_rt_preview(self, rt_name: str, tag: str) -> tuple[Any, str]:
        channel = "depth" if tag == "rt_depth" else "color"
        tc_tex = find_rt_texture(rt_name, channel)
        if tc_tex is None:
            log.warn(f"[TexturePickerWidget] RT preview texture not found: {rt_name}/{channel}")
            return None, "No\nTex"

        try:
            data = tc_tex.data
            if data is None:
                return None, "No\nTex"

            arr = np.asarray(data)
            if arr.ndim == 3 and arr.shape[2] in (3, 4):
                # Float HDR textures: map [0, +inf) to [0, 255].
                if arr.dtype == np.float32 or arr.dtype == np.float64:
                    arr = np.clip(arr * 255.0, 0.0, 255.0).astype(np.uint8)
                return arr, "No\nTex"

            log.warn(
                f"[TexturePickerWidget] RT preview data has unsupported shape: "
                f"{rt_name}/{channel} shape={arr.shape}"
            )
            return None, "No\nTex"
        except Exception as e:
            log.warn(f"[TexturePickerWidget] RT preview failed for '{rt_name}': {e}")
            return None, "No\nTex"


# ------------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------------

def find_rt_texture(rt_name: str, channel: str) -> Any:
    """Find a live render target by name and return its color or depth TcTexture."""
    try:
        from termin.render_framework import render_target_pool_list
    except ImportError as e:
        log.warn(f"[TexturePickerWidget] render_framework import failed while resolving RT texture: {e}")
        return None

    for h in render_target_pool_list():
        if not h.alive or h.name != rt_name:
            continue
        h.ensure_textures()
        if channel == "color":
            return h.color_texture
        if channel == "depth":
            return h.depth_texture
    log.warn(f"[TexturePickerWidget] live render target texture not found: {rt_name}/{channel}")
    return None
