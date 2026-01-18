"""
Scene cache system for storing component data.

Provides abstract API for caching arbitrary data per entity/component.
The actual storage backend can be filesystem, archive, memory, etc.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional
from weakref import WeakValueDictionary

from termin._native import log

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene


class SceneCache(ABC):
    """
    Abstract cache storage for a scene.

    Stores data keyed by (entity_uuid, component_type, key).
    The actual storage mechanism is implementation-dependent.
    """

    _instances: Dict[str, "SceneCache"] = {}

    @classmethod
    def for_scene(cls, scene: "Scene") -> "SceneCache":
        """
        Get cache instance for a scene.

        Creates FilesystemSceneCache by default.
        """
        scene_uuid = scene.uuid
        if scene_uuid not in cls._instances:
            cls._instances[scene_uuid] = FilesystemSceneCache(scene)
        return cls._instances[scene_uuid]

    @classmethod
    def clear_instance(cls, scene_uuid: str) -> None:
        """Remove cached instance for scene."""
        cls._instances.pop(scene_uuid, None)

    # === Abstract API ===

    @abstractmethod
    def get(self, entity_uuid: str, component_type: str, key: str) -> bytes | None:
        """
        Read data from cache.

        Args:
            entity_uuid: UUID of the entity owner.
            component_type: Component type name (e.g. "NavMeshBuilderComponent").
            key: Data key (e.g. "navmesh_default").

        Returns:
            Data bytes or None if not in cache.
        """

    @abstractmethod
    def put(self, entity_uuid: str, component_type: str, key: str, data: bytes) -> None:
        """
        Write data to cache.

        Args:
            entity_uuid: UUID of the entity owner.
            component_type: Component type name.
            key: Data key.
            data: Data bytes to store.
        """

    @abstractmethod
    def delete(self, entity_uuid: str, component_type: str, key: str) -> None:
        """Delete data from cache."""

    @abstractmethod
    def exists(self, entity_uuid: str, component_type: str, key: str) -> bool:
        """Check if data exists in cache."""

    @abstractmethod
    def list_keys(self, entity_uuid: str, component_type: str) -> List[str]:
        """List all keys for a component."""

    # === Bulk operations ===

    @abstractmethod
    def clear_component(self, entity_uuid: str, component_type: str) -> None:
        """Delete all cache data for a component."""

    @abstractmethod
    def clear_entity(self, entity_uuid: str) -> None:
        """Delete all cache data for an entity."""

    @abstractmethod
    def clear_all(self) -> None:
        """Clear entire scene cache."""


class FilesystemSceneCache(SceneCache):
    """
    Filesystem-based cache implementation.

    Structure:
        {project_root}/Cache/{scene_name}/{entity_uuid}/{component_type}/{key}
    """

    _root: Path
    _scene_name: str

    def __init__(self, scene: "Scene") -> None:
        self._scene_name = scene.name or scene.uuid
        if not self._scene_name:
            raise ValueError("SceneCache: scene must have name or uuid")
        self._root = self._get_cache_root(self._scene_name)
        print(f"SceneCache: root={self._root}")

    def _get_cache_root(self, scene_name: str) -> Path:
        """Get cache root directory for scene."""
        from termin.editor.project_browser import ProjectBrowser

        project_root = ProjectBrowser.current_project_path
        if project_root is None:
            # Fallback to current directory
            project_root = Path.cwd()

        return project_root / "Cache" / scene_name

    def _get_path(self, entity_uuid: str, component_type: str, key: str) -> Path:
        """Get full path for a cache entry."""
        return self._root / entity_uuid / component_type / key

    def get(self, entity_uuid: str, component_type: str, key: str) -> bytes | None:
        path = self._get_path(entity_uuid, component_type, key)
        if not path.exists():
            return None
        try:
            return path.read_bytes()
        except Exception as e:
            log.error(f"SceneCache: failed to read {path}: {e}")
            return None

    def put(self, entity_uuid: str, component_type: str, key: str, data: bytes) -> None:
        path = self._get_path(entity_uuid, component_type, key)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        except Exception as e:
            log.error(f"SceneCache: failed to write {path}: {e}")

    def delete(self, entity_uuid: str, component_type: str, key: str) -> None:
        path = self._get_path(entity_uuid, component_type, key)
        try:
            if path.exists():
                path.unlink()
        except Exception as e:
            log.error(f"SceneCache: failed to delete {path}: {e}")

    def exists(self, entity_uuid: str, component_type: str, key: str) -> bool:
        return self._get_path(entity_uuid, component_type, key).exists()

    def list_keys(self, entity_uuid: str, component_type: str) -> List[str]:
        component_dir = self._root / entity_uuid / component_type
        if not component_dir.exists():
            return []
        try:
            return [f.name for f in component_dir.iterdir() if f.is_file()]
        except Exception as e:
            log.error(f"SceneCache: failed to list {component_dir}: {e}")
            return []

    def clear_component(self, entity_uuid: str, component_type: str) -> None:
        component_dir = self._root / entity_uuid / component_type
        if not component_dir.exists():
            return
        try:
            import shutil
            shutil.rmtree(component_dir)
        except Exception as e:
            log.error(f"SceneCache: failed to clear {component_dir}: {e}")

    def clear_entity(self, entity_uuid: str) -> None:
        entity_dir = self._root / entity_uuid
        if not entity_dir.exists():
            return
        try:
            import shutil
            shutil.rmtree(entity_dir)
        except Exception as e:
            log.error(f"SceneCache: failed to clear {entity_dir}: {e}")

    def clear_all(self) -> None:
        if not self._root.exists():
            return
        try:
            import shutil
            shutil.rmtree(self._root)
        except Exception as e:
            log.error(f"SceneCache: failed to clear {self._root}: {e}")
