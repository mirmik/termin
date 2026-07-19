"""Navmesh asset plugins."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from termin_assets import AssetContext, AssetTypeRegistry, PreLoadResult


class NavMeshImportPlugin:
    """Import-side plugin for navmesh files."""

    type_id = "navmesh"
    extensions = {".navmesh"}
    priority = 10

    def preload(self, path: str) -> "PreLoadResult | None":
        from termin_assets import PreLoadResult, read_spec_file

        spec_data = read_spec_file(path)
        uuid = spec_data.get("uuid") if spec_data else None
        return PreLoadResult(
            resource_type=self.type_id,
            path=path,
            content=None,
            uuid=uuid,
            spec_data=spec_data,
        )


class NavMeshRuntimePlugin:
    """Runtime-side plugin for navmesh registration and reload."""

    type_id = "navmesh"

    def register(self, context: "AssetContext", result: "PreLoadResult") -> None:
        from termin.default_assets.navmesh.asset import NavMeshAsset

        rm = context.resource_manager
        name = context.name
        asset = None
        candidate = rm.get_runtime_asset_by_uuid(self.type_id, context.uuid)
        if isinstance(candidate, NavMeshAsset):
            asset = candidate

        if asset is None:
            asset = NavMeshAsset(
                navmesh=None,
                name=name,
                source_path=result.path,
                uuid=context.uuid,
            )

        asset.parse_spec(result.spec_data)
        rm.register_runtime_asset(
            self.type_id,
            name,
            asset,
            source_path=result.path,
            uuid=context.uuid,
        )

    def reload(self, context: "AssetContext", result: "PreLoadResult") -> None:
        rm = context.resource_manager
        asset = rm.get_runtime_asset_by_uuid(self.type_id, context.uuid)
        if asset is None:
            return

        if not asset.is_loaded:
            return

        if not asset.should_reload_from_file():
            return

        asset.parse_spec(result.spec_data)
        asset.reload()

    def unregister(self, context: "AssetContext", result: "PreLoadResult") -> None:
        context.resource_manager.unregister_runtime_asset_by_uuid(self.type_id, context.uuid)


class NavMeshAssetPlugin(NavMeshImportPlugin, NavMeshRuntimePlugin):
    """Compatibility combined navmesh plugin."""


def create_import_plugin() -> NavMeshImportPlugin:
    return NavMeshImportPlugin()


def create_runtime_plugin() -> NavMeshRuntimePlugin:
    return NavMeshRuntimePlugin()


def register_navmesh_import_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_import(NavMeshImportPlugin())


def register_navmesh_runtime_plugin(registry: "AssetTypeRegistry") -> None:
    registry.register_runtime(NavMeshRuntimePlugin())


def register_navmesh_asset_plugin(registry: "AssetTypeRegistry") -> None:
    register_navmesh_import_plugin(registry)
    register_navmesh_runtime_plugin(registry)
