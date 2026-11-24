"""Sidecar-identified flipbook clips for SpriteAnimator2D."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from termin.base import log
from termin.default_assets.render.sprite_plugin import SpriteDescriptorImportPlugin

if TYPE_CHECKING:
    from termin_assets import AssetContext, PreLoadResult


class SpriteAnimationClipImportPlugin(SpriteDescriptorImportPlugin):
    type_id = "sprite_animation_clip"
    extensions = {".spriteclip"}


class SpriteAnimationClipRuntimePlugin:
    type_id = "sprite_animation_clip"

    def register(self, context: AssetContext, result: PreLoadResult) -> None:
        from termin.render_components import TcSpriteAnimationClip
        from termin_assets import AssetRecord

        try:
            text = Path(result.path).read_text(encoding="utf-8")
            clip = TcSpriteAnimationClip.declare(context.uuid, context.name, result.path)
            clip.load_json(text)
        except (OSError, ValueError, RuntimeError):
            log.error(f"Failed to load sprite animation clip '{context.uuid}' from {result.path}", exc_info=True)
            raise

        context.resource_manager.external_assets.upsert(
            AssetRecord(type_id=self.type_id, uuid=context.uuid, name=context.name, path=result.path,
                        spec_data=result.spec_data)
        )

    def reload(self, context: AssetContext, result: PreLoadResult) -> bool:
        self.register(context, result)
        return True

    def unregister(self, context: AssetContext, result: PreLoadResult) -> None:
        from termin.render_components import TcSpriteAnimationClip

        TcSpriteAnimationClip.from_uuid(context.uuid).unload()
        context.resource_manager.external_assets.remove(self.type_id, context.uuid)
