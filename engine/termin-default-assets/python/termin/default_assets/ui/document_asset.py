"""Project-file record backed by the native UI document asset registry."""

from __future__ import annotations

from pathlib import Path

from termin.base import log
from termin_assets import Asset


class UiDocumentSourceAsset(Asset):
    """Metadata and reload lifecycle for one native ``UiDocumentAsset``.

    The Python object participates in the generic project asset index only. The
    parsed recipe and every instantiated widget tree remain owned by
    ``termin-gui-native``.
    """

    def __init__(
        self,
        name: str = "ui",
        source_path: Path | str | None = None,
        uuid: str | None = None,
    ) -> None:
        super().__init__(name=name, source_path=source_path, uuid=uuid)

    @property
    def canonical_resource(self):
        """Return the current generation-safe native asset handle."""
        from termin.gui_native import UiDocumentAsset

        asset = UiDocumentAsset.from_uuid(self.uuid)
        return asset if asset.valid else None

    @property
    def resource(self):
        if not self._loaded and not self.ensure_loaded():
            return None
        return self.canonical_resource

    def _read_source(self) -> str:
        if self._source_path is None:
            raise ValueError(f"native UI asset '{self.name}' has no source path")
        return self._source_path.read_text(encoding="utf-8")

    def _load(self) -> bool:
        from termin.gui_native import UiDocumentAsset

        source_path = self._source_path
        if source_path is None:
            log.error(
                f"[UiDocumentSourceAsset] Cannot load '{self.name}' "
                f"({self.uuid}): source path is missing"
            )
            return False
        try:
            source = self._read_source()
        except Exception:
            log.error(
                f"[UiDocumentSourceAsset] Failed to read native UI source "
                f"'{source_path}' ({self.uuid})",
                exc_info=True,
            )
            return False

        current = UiDocumentAsset.from_uuid(self.uuid)
        if current.valid:
            if current.source_identity != str(source_path):
                log.error(
                    f"[UiDocumentSourceAsset] Native UI UUID collision for "
                    f"'{self.uuid}': '{current.source_identity}' vs '{source_path}'"
                )
                return False
            if not current.reload_source(source):
                log.error(
                    f"[UiDocumentSourceAsset] Native UI reload rejected "
                    f"'{source_path}' ({self.uuid}); previous revision remains active"
                )
                return False
            native_asset = UiDocumentAsset.from_uuid(self.uuid)
        else:
            native_asset = UiDocumentAsset.declare_source(
                self.uuid,
                self.name,
                str(source_path),
                source,
            )
            if not native_asset.valid:
                log.error(
                    f"[UiDocumentSourceAsset] Failed to declare native UI source "
                    f"'{source_path}' ({self.uuid})"
                )
                return False

        self._loaded = True
        return True

    def remove_native(self) -> bool:
        """Remove the corresponding native registry entry."""
        native_asset = self.canonical_resource
        self._loaded = False
        return native_asset is None or bool(native_asset.remove())


__all__ = ["UiDocumentSourceAsset"]
