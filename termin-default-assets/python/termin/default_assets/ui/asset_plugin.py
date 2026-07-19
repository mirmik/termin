"""UI asset plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin_assets import AssetContext, AssetTypeRegistry, PreLoadResult


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


class UIRuntimePlugin:
    """Runtime-side plugin for UI asset registration and reload."""

    type_id = "ui"

    def register(self, context: "AssetContext", result: "PreLoadResult") -> None:
        from termin.default_assets.ui.asset import UIAsset

        rm = context.resource_manager
        name = context.name
        asset = None
        candidate = rm.get_runtime_asset_by_uuid(self.type_id, context.uuid)
        if isinstance(candidate, UIAsset):
            asset = candidate

        if asset is None:
            asset = UIAsset(
                widget=None,
                name=name,
                source_path=result.path,
                uuid=context.uuid,
            )

        asset.parse_spec(result.spec_data)
        rm.register_runtime_asset(self.type_id, name, asset, source_path=result.path, uuid=context.uuid)

    def reload(self, context: "AssetContext", result: "PreLoadResult") -> None:
        rm = context.resource_manager
        asset = rm.get_runtime_asset_by_uuid(self.type_id, context.uuid)
        if asset is None:
            return

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        asset.reload()

    def unregister(self, context: "AssetContext", result: "PreLoadResult") -> None:
        context.resource_manager.unregister_runtime_asset_by_uuid(self.type_id, context.uuid)


class UIAssetPlugin(UIImportPlugin, UIRuntimePlugin):
    """Compatibility combined UI plugin."""


def create_import_plugin() -> UIImportPlugin:
    return UIImportPlugin()


def create_runtime_plugin() -> UIRuntimePlugin:
    return UIRuntimePlugin()


def register_ui_import_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_import(UIImportPlugin())


def register_ui_runtime_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_runtime(UIRuntimePlugin())


def register_ui_asset_plugin(registry: "AssetTypeRegistry") -> None:
    register_ui_import_plugin(registry)
    register_ui_runtime_plugin(registry)
