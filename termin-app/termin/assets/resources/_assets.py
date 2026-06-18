"""Application-specific asset management mixin."""

from __future__ import annotations

from typing import Optional, TYPE_CHECKING

from termin.default_assets.resource_api import DefaultAssetResourceMixin

if TYPE_CHECKING:
    from termin_assets import Asset
    from termin.animation import TcAnimationClip
    from termin.animation.asset import AnimationClipAsset
    from termin.default_assets.render.material_asset import MaterialAsset
    from termin.glb.asset import GLBAsset
    from termin.materials import TcMaterial as Material
    from termin.skeleton import TcSkeleton
    from termin.skeleton.asset import SkeletonAsset


class AssetsMixin(DefaultAssetResourceMixin):
    """App-layer asset methods that still depend on termin-app or domain packages."""

    # --------- GLB ---------
    def get_glb_asset(self, name: str) -> Optional["GLBAsset"]:
        """Get GLBAsset by name."""
        return self._glb_registry.get_asset(name)

    def get_glb_asset_by_uuid(self, uuid: str) -> Optional["GLBAsset"]:
        """Get GLBAsset by UUID."""
        return self._glb_registry.get_asset_by_uuid(uuid)

    def register_glb_asset(
        self,
        name: str,
        asset: "GLBAsset",
        source_path: str | None = None,
    ) -> None:
        """Register a GLBAsset."""
        self._glb_registry.register(name, asset, source_path=source_path)

    def unregister_glb_asset(self, name: str) -> None:
        """Remove a GLBAsset by name."""
        self._glb_registry.unregister(name)

    def list_glb_names(self) -> list[str]:
        """List all registered GLB asset names."""
        return self._glb_registry.list_names()

    # --------- Materials with app fallback ---------
    def get_material(self, name: str) -> "Material":
        """
        Get material by name (lazy loading).

        Returns UnknownMaterial if material is not found or failed to load.
        """
        from termin.visualization.render.materials.unknown_material import UnknownMaterial

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
        from termin.visualization.render.materials.unknown_material import UnknownMaterial

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
        from termin.assets.builtin_resources import register_builtin_materials

        register_builtin_materials(self)

    def register_builtin_textures(self) -> None:
        """Register builtin placeholder textures."""
        from termin.assets.builtin_resources import register_builtin_textures

        register_builtin_textures(self)

    def register_builtin_meshes(self) -> list[str]:
        """Register builtin primitive meshes."""
        from termin.assets.builtin_resources import register_builtin_meshes

        return register_builtin_meshes(self)

    # --------- Animation Clips ---------
    def get_animation_clip_asset(self, name: str) -> Optional["AnimationClipAsset"]:
        return self._animation_clip_registry.get_asset(name)

    def register_animation_clip(
        self,
        name: str,
        clip: "TcAnimationClip",
        source_path: str | None = None,
        uuid: str | None = None,
    ) -> None:
        from termin.animation.asset import AnimationClipAsset

        asset = AnimationClipAsset(clip=clip, name=name, source_path=source_path, uuid=uuid)
        self._animation_clip_registry.register(name, asset, source_path, uuid)
        self.animation_clips[name] = clip

    def get_animation_clip(self, name: str) -> Optional["TcAnimationClip"]:
        clip = self.animation_clips.get(name)
        if clip is not None:
            return clip
        return self._animation_clip_registry.get(name)

    def get_animation_clip_asset_by_uuid(self, uuid: str) -> Optional["AnimationClipAsset"]:
        return self._animation_clip_registry.get_asset_by_uuid(uuid)

    def get_or_create_animation_clip_asset(
        self,
        name: str,
        source_path: str | None = None,
        uuid: str | None = None,
        parent: "Asset | None" = None,
        parent_key: str | None = None,
    ) -> "AnimationClipAsset":
        return self._animation_clip_registry.get_or_create_asset(
            name=name, source_path=source_path, uuid=uuid, parent=parent, parent_key=parent_key,
        )

    def list_animation_clip_names(self) -> list[str]:
        return self._animation_clip_registry.list_names()

    def find_animation_clip_name(self, clip: "TcAnimationClip") -> Optional[str]:
        return self._animation_clip_registry.find_name(clip)

    def unregister_animation_clip(self, name: str) -> None:
        self._animation_clip_registry.unregister(name)
        if name in self.animation_clips:
            del self.animation_clips[name]

    # --------- Skeletons ---------
    def get_skeleton_asset(self, name: str) -> Optional["SkeletonAsset"]:
        return self._skeleton_registry.get_asset(name)

    def register_skeleton(
        self,
        name: str,
        skeleton: "TcSkeleton",
        source_path: str | None = None,
        uuid: str | None = None,
    ) -> None:
        from termin.skeleton.asset import SkeletonAsset

        asset = SkeletonAsset.from_tc_skeleton(skeleton, name=name, source_path=source_path, uuid=uuid)
        self._skeleton_registry.register(name, asset, source_path, uuid)
        self.skeletons[name] = skeleton

    def get_skeleton(self, name: str) -> Optional["TcSkeleton"]:
        skeleton = self.skeletons.get(name)
        if skeleton is not None:
            return skeleton
        skeleton = self._skeleton_registry.get(name)
        if skeleton is not None:
            self.skeletons[name] = skeleton
        return skeleton

    def list_skeleton_names(self) -> list[str]:
        return self._skeleton_registry.list_names()

    def find_skeleton_name(self, skeleton: "TcSkeleton") -> Optional[str]:
        return self._skeleton_registry.find_name(skeleton)

    def find_skeleton_uuid(self, skeleton: "TcSkeleton") -> Optional[str]:
        return self._skeleton_registry.find_uuid(skeleton)

    def get_skeleton_by_uuid(self, uuid: str) -> Optional["TcSkeleton"]:
        skeleton = self._skeleton_registry.get_by_uuid(uuid)
        if skeleton is not None:
            asset = self._skeleton_registry.get_asset_by_uuid(uuid)
            if asset is not None and asset.name:
                self.skeletons[asset.name] = skeleton
        return skeleton

    def get_skeleton_asset_by_uuid(self, uuid: str) -> Optional["SkeletonAsset"]:
        return self._skeleton_registry.get_asset_by_uuid(uuid)

    def get_or_create_skeleton_asset(
        self,
        name: str,
        source_path: str | None = None,
        uuid: str | None = None,
        parent: "Asset | None" = None,
        parent_key: str | None = None,
    ) -> "SkeletonAsset":
        return self._skeleton_registry.get_or_create_asset(
            name=name, source_path=source_path, uuid=uuid, parent=parent, parent_key=parent_key,
        )

    def unregister_skeleton(self, name: str) -> None:
        self._skeleton_registry.unregister(name)
        if name in self.skeletons:
            del self.skeletons[name]
