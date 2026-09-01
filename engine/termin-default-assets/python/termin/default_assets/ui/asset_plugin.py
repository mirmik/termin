"""UI asset plugins."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import uuid4

from termin.base import log

if TYPE_CHECKING:
    from termin_assets import AssetContext, AssetTypeRegistry, PreLoadResult


_NEW_UI_SOURCE = """uiscript: 2
root:
  type: termin.gui.VStack
  name: root
  children:
    - type: termin.gui.IconButton
      name: action
      icon: "+"
      tooltip: "New UI action"
"""


class UIImportPlugin:
    """Import-side plugin for UI script files."""

    type_id = "ui"
    extensions = {".uiscript"}
    priority = 10

    def preload(self, path: str) -> "PreLoadResult | None":
        from termin_assets import AssetIdentityPolicy, PreLoadResult, read_spec_file

        spec_data = read_spec_file(path)
        uuid = spec_data.get("uuid") if spec_data else None
        return PreLoadResult(
            resource_type=self.type_id,
            path=path,
            content=None,
            uuid=uuid,
            spec_data=spec_data,
            identity_policy=AssetIdentityPolicy.GENERATE_SIDECAR,
        )

    def create_asset(self, project_root: str, name: str) -> "PreLoadResult":
        from termin_assets import PreLoadResult, write_spec_file

        safe_name = "".join(
            character if character.isalnum() or character in "-_" else "_"
            for character in name.strip()
        ).strip("_")
        if not safe_name:
            raise ValueError("UI asset name must contain a letter or digit")

        uuid = str(uuid4())
        path = Path(project_root) / "Assets" / "UI" / f"{safe_name}.uiscript"
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            raise FileExistsError(f"UI asset already exists: {path}")
        path.write_text(_NEW_UI_SOURCE, encoding="utf-8")
        spec_data = {"uuid": uuid}
        if not write_spec_file(str(path), spec_data):
            path.unlink(missing_ok=True)
            raise RuntimeError(f"Failed to write UI asset metadata: {path}")
        return PreLoadResult(
            resource_type=self.type_id,
            path=str(path),
            content=None,
            uuid=uuid,
            spec_data=spec_data,
        )


class UIRuntimePlugin:
    """Runtime-side plugin for native UI document registration and reload."""

    type_id = "ui"

    def register(self, context: "AssetContext", result: "PreLoadResult") -> None:
        from termin.default_assets.ui.document_asset import UiDocumentSourceAsset

        rm = context.resource_manager
        name = context.name
        asset = None
        candidate = rm.get_runtime_asset_by_uuid(self.type_id, context.uuid)
        if isinstance(candidate, UiDocumentSourceAsset):
            asset = candidate

        if asset is None:
            asset = UiDocumentSourceAsset(
                name=name,
                source_path=result.path,
                uuid=context.uuid,
            )
        else:
            asset.source_path = result.path
        if not asset.is_loaded and not asset.ensure_loaded():
            log.error(
                f"[UIRuntimePlugin] Failed to register native UI document "
                f"'{result.path}' ({context.uuid})"
            )
            return
        rm.register_runtime_asset(self.type_id, name, asset, source_path=result.path, uuid=context.uuid)

    def reload(self, context: "AssetContext", result: "PreLoadResult") -> bool:
        rm = context.resource_manager
        asset = rm.get_runtime_asset_by_uuid(self.type_id, context.uuid)
        if asset is None:
            log.error(
                f"[UIRuntimePlugin] Native UI reload target is missing: "
                f"'{result.path}' ({context.uuid})"
            )
            return False
        asset.source_path = result.path
        return bool(asset.reload())

    def unregister(self, context: "AssetContext", result: "PreLoadResult") -> None:
        asset = context.resource_manager.unregister_runtime_asset_by_uuid(
            self.type_id, context.uuid
        )
        if asset is not None and not asset.remove_native():
            log.error(
                f"[UIRuntimePlugin] Failed to remove native UI document "
                f"'{result.path}' ({context.uuid})"
            )


def create_import_plugin() -> UIImportPlugin:
    return UIImportPlugin()


def create_runtime_plugin() -> UIRuntimePlugin:
    return UIRuntimePlugin()


def register_ui_import_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_import(UIImportPlugin())


def register_ui_runtime_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_runtime(UIRuntimePlugin())
