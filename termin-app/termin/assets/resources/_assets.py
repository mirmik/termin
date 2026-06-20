"""Application-specific asset management mixin."""

from __future__ import annotations

from typing import TYPE_CHECKING

from termin.default_assets.resource_api import DefaultAssetResourceMixin

if TYPE_CHECKING:
    from termin.default_assets.render.material_asset import MaterialAsset
    from termin.materials import TcMaterial as Material


class AssetsMixin(DefaultAssetResourceMixin):
    """App-layer asset methods that still depend on termin-app."""

    # --------- Materials with app fallback ---------
    def get_material(self, name: str) -> "Material":
        """
        Get material by name (lazy loading).

        Returns UnknownMaterial if material is not found or failed to load.
        """
        from termin.materials import UnknownMaterial

        mat = self.materials.get(name)
        if mat is not None:
            return mat
        asset = self._material_registry.get_asset(name)
        if asset is None:
            return UnknownMaterial.for_missing_material(name)
        if asset.material is None:
            if not asset.ensure_loaded():
                return UnknownMaterial.for_missing_material(name)
        if asset.material is not None:
            self.materials[name] = asset.material
            return asset.material
        return UnknownMaterial.for_missing_material(name)

    def get_material_by_uuid(self, uuid: str) -> "Material":
        """
        Get Material by UUID (lazy loading).

        Returns UnknownMaterial if material is not found or failed to load.
        """
        from termin.materials import UnknownMaterial

        asset: "MaterialAsset | None" = self._material_registry.get_asset_by_uuid(uuid)
        if asset is None:
            return UnknownMaterial.for_missing_material(f"uuid:{uuid}")
        if asset.material is None:
            if not asset.ensure_loaded():
                return UnknownMaterial.for_missing_material(asset.name or f"uuid:{uuid}")
        if asset.material is not None:
            if asset.name:
                self.materials[asset.name] = asset.material
            return asset.material
        return UnknownMaterial.for_missing_material(asset.name or f"uuid:{uuid}")

    def register_builtin_materials(self) -> None:
        """Register builtin materials."""
        from termin.default_assets.builtin_resources import register_builtin_materials

        register_builtin_materials(self)

    def register_builtin_textures(self) -> None:
        """Register builtin placeholder textures."""
        from termin.default_assets.builtin_resources import register_builtin_textures

        register_builtin_textures(self)

    def register_builtin_meshes(self) -> list[str]:
        """Register builtin primitive meshes."""
        from termin.default_assets.builtin_resources import register_builtin_meshes

        return register_builtin_meshes(self)
