"""
ResourceHandle — базовый класс для умных ссылок на ресурсы.

Три режима работы:
1. Direct — хранит raw объект напрямую (Texture, TcShader)
2. Asset — хранит ссылку на Asset
3. Named — хранит имя, ищет в ResourceManager при get()

ResourceKeeper оставлен для обратной совместимости (VoxelGrid, NavMesh, AnimationClip).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Generic, TypeVar

if TYPE_CHECKING:
    from termin.assets.asset import Asset

T = TypeVar("T")  # Raw resource type (Texture, TcShader, etc.)
AssetT = TypeVar("AssetT", bound="Asset")  # Asset type


class ResourceKeeper(Generic[T]):
    """
    Базовый владелец ресурса по имени.

    DEPRECATED: Используется только для VoxelGrid, NavMesh, AnimationClip.
    Новые ресурсы используют Handle → Asset напрямую.
    """

    def __init__(self, name: str):
        self.name = name
        self._resource: T | None = None
        self._source_path: str | None = None

    @property
    def resource(self) -> T | None:
        """Текущий ресурс или None если не загружен."""
        return self._resource

    @property
    def source_path(self) -> str | None:
        """Путь к файлу-источнику ресурса."""
        return self._source_path

    @property
    def has_resource(self) -> bool:
        """Есть ли ресурс."""
        return self._resource is not None

    def _on_cleanup(self, resource: T) -> None:
        """Override для очистки."""
        pass

    def set_resource(self, resource: T, source_path: str | None = None) -> None:
        """Установить ресурс."""
        if self._resource is not None:
            self._on_cleanup(self._resource)
        self._resource = resource
        if source_path is not None:
            self._source_path = source_path

    def update_resource(self, resource: T) -> None:
        """Обновить ресурс (hot-reload)."""
        if self._resource is not None:
            self._on_cleanup(self._resource)
        self._resource = resource


class ResourceHandle(Generic[T, AssetT]):
    """
    Базовая умная ссылка на ресурс.

    Два режима работы:
    1. Direct — хранит raw объект напрямую (Texture, TcShader)
    2. Asset — хранит ссылку на Asset (lookup по имени через ResourceManager)

    Subclasses should set _asset_getter to enable from_name():
        _asset_getter = "get_mesh_asset"  # ResourceManager method name
    """

    # Override in subclasses: ResourceManager method name for get_*_asset()
    _asset_getter: str = ""

    def __init__(self):
        self._direct: T | None = None  # Raw object
        self._asset: AssetT | None = None  # Asset wrapper

    @classmethod
    def from_name(cls, name: str) -> "ResourceHandle[T, AssetT]":
        """
        Создать handle по имени (lookup в ResourceManager).

        Subclasses must set _asset_getter class attribute.
        """
        if not cls._asset_getter:
            return cls()

        from termin.assets.resources import ResourceManager

        rm = ResourceManager.instance()
        getter = getattr(rm, cls._asset_getter, None)
        if getter is None:
            return cls()

        asset = getter(name)
        if asset is not None:
            return cls.from_asset(asset)
        return cls()

    @classmethod
    def from_asset(cls, asset: AssetT) -> "ResourceHandle[T, AssetT]":
        """Создать handle с Asset."""
        handle = cls()
        handle._init_asset(asset)
        return handle

    @property
    def is_direct(self) -> bool:
        """True если хранится raw объект."""
        return self._direct is not None

    @property
    def is_asset(self) -> bool:
        """True если хранится Asset."""
        return self._asset is not None

    @property
    def name(self) -> str | None:
        """Имя ресурса (из Asset)."""
        if self._asset is not None:
            return self._asset.name  # type: ignore
        return None

    def get_asset(self) -> AssetT | None:
        """Получить Asset."""
        return self._asset

    def get(self) -> T | None:
        """
        Получить raw ресурс.

        Returns:
            Raw ресурс или None если недоступен
        """
        # Direct raw object
        if self._direct is not None:
            return self._direct

        # From asset
        if self._asset is not None:
            return self._get_resource_from_asset(self._asset)

        return None

    def _get_resource_from_asset(self, asset: AssetT) -> T | None:
        """
        Извлечь raw ресурс из Asset.

        Default implementation uses asset.resource property.
        Subclasses can override for custom behavior (e.g., ensure_loaded).
        """
        asset.ensure_loaded()
        return asset.resource  # type: ignore

    def get_or_none(self) -> T | None:
        """Алиас для get()."""
        return self.get()

    def _init_direct(self, resource: T) -> None:
        """Инициализировать с raw объектом."""
        self._direct = resource
        self._asset = None

    def _init_asset(self, asset: AssetT) -> None:
        """Инициализировать с Asset."""
        self._direct = None
        self._asset = asset

    def serialize(self) -> dict:
        """Сериализация для сохранения сцены."""
        if self._direct is not None:
            # Raw object - subclass должен реализовать _serialize_direct
            return self._serialize_direct()
        elif self._asset is not None:
            # Always include uuid and name for inspector display
            result = {
                "uuid": self._asset.uuid,
                "name": self._asset.name,
            }
            if self._asset.source_path:
                result["type"] = "path"
                result["path"] = str(self._asset.source_path)
            else:
                result["type"] = "named"
            return result
        else:
            return {"type": "none"}

    def _serialize_direct(self) -> dict:
        """
        Сериализовать raw объект.

        Subclasses должны переопределить.
        """
        return {"type": "direct_unsupported"}
