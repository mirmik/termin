# Prefab Override System — Implementation Plan

## Overview

Система переопределений для prefab instances, аналогичная Unity:
- Instance сохраняет связь с исходным prefab
- Можно переопределять отдельные свойства (property overrides)
- При изменении prefab — все instances обновляются (кроме overridden свойств)
- Поддержка вложенных prefab (prefab внутри prefab)

---

## Phase 1: Core Infrastructure

### 1.1 PropertyPath (`termin/visualization/core/property_path.py`)

Утилита для адресации свойств внутри Entity hierarchy.

```python
class PropertyPath:
    """
    Путь к свойству внутри Entity.

    Форматы путей:
        "name"                                  # Entity.name
        "visible"                               # Entity.visible
        "transform.position"                    # Transform position (lin)
        "transform.rotation"                    # Transform rotation (ang)
        "transform.scale"                       # Transform scale
        "components/MeshRenderer/material"      # Компонент по типу
        "components/MeshRenderer/cast_shadow"   # Поле компонента
        "children/0/name"                       # Дочерний entity по индексу
        "children/ChildName/transform.position" # Дочерний entity по имени
    """

    @staticmethod
    def get(entity: Entity, path: str) -> Any:
        """Получить значение по пути."""

    @staticmethod
    def set(entity: Entity, path: str, value: Any) -> bool:
        """Установить значение по пути. Returns True if successful."""

    @staticmethod
    def exists(entity: Entity, path: str) -> bool:
        """Проверить существование пути."""

    @staticmethod
    def iter_all(entity: Entity, include_children: bool = True) -> Iterator[tuple[str, Any]]:
        """
        Итерировать по всем свойствам entity.
        Yields (path, value) для каждого свойства.
        """

    @staticmethod
    def diff(entity_a: Entity, entity_b: Entity) -> dict[str, tuple[Any, Any]]:
        """
        Найти различия между двумя entities.
        Returns {path: (value_a, value_b)} для различающихся свойств.
        """
```

**Свойства Entity для отслеживания:**
- `name`, `visible`, `active`, `pickable`, `selectable`, `layer`, `flags`, `priority`
- `transform.position`, `transform.rotation`, `transform.scale`
- Все поля всех компонентов (через inspect_fields)
- Рекурсивно для children

### 1.2 PrefabRegistry (`termin/visualization/core/prefab_registry.py`)

Глобальный реестр всех prefab instances для быстрого hot-reload.

```python
class PrefabRegistry:
    """
    Реестр prefab instances.

    Позволяет быстро найти все instances данного prefab
    без обхода всех сцен.
    """

    # prefab_uuid -> WeakSet[Entity]
    _instances: dict[str, weakref.WeakSet[Entity]] = {}

    @classmethod
    def register(cls, prefab_uuid: str, entity: Entity) -> None:
        """Зарегистрировать instance."""

    @classmethod
    def unregister(cls, prefab_uuid: str, entity: Entity) -> None:
        """Удалить instance из реестра."""

    @classmethod
    def get_instances(cls, prefab_uuid: str) -> list[Entity]:
        """Получить все живые instances prefab."""

    @classmethod
    def clear(cls) -> None:
        """Очистить реестр (при смене сцены)."""
```

---

## Phase 2: Prefab Asset

### 2.1 PrefabAsset (`termin/visualization/core/prefab_asset.py`)

Asset для .prefab файлов с поддержкой hot-reload.

```python
class PrefabAsset(DataAsset[dict]):
    """
    Asset для .prefab файла.

    Хранит сериализованные данные Entity hierarchy.
    Поддерживает hot-reload с обновлением всех instances.
    """

    _uses_binary = False  # JSON format

    @property
    def root_data(self) -> dict | None:
        """Данные корневой entity."""
        return self._data.get("root") if self._data else None

    def instantiate(
        self,
        parent: Transform3 | None = None,
        position: tuple[float, float, float] | None = None,
    ) -> Entity:
        """
        Создать instance префаба.

        1. Deserialize entity hierarchy (с новыми UUID)
        2. Добавить PrefabInstanceMarker
        3. Зарегистрировать в PrefabRegistry
        4. Attach to parent if provided

        Returns:
            Root entity of the instance.
        """

    def update_from(self, other: "PrefabAsset") -> None:
        """
        Hot-reload: обновить данные и все instances.

        1. Обновить self._data
        2. Найти все instances через PrefabRegistry
        3. Для каждого instance применить изменения (кроме overrides)
        """

    def apply_to_instance(self, entity: Entity) -> None:
        """
        Применить данные prefab к instance.

        Обходит все свойства prefab и применяет те,
        которые не переопределены в instance.
        """

    def _parse_content(self, content: str) -> dict | None:
        """Parse JSON content."""

    # Factory methods
    @classmethod
    def from_file(cls, path: Path) -> "PrefabAsset": ...

    @classmethod
    def from_entity(cls, entity: Entity, name: str) -> "PrefabAsset": ...
```

### 2.2 Формат .prefab файла

```json
{
  "version": "2.0",
  "uuid": "prefab-uuid-here",
  "root": {
    "uuid": "root-entity-uuid",
    "name": "MyPrefab",
    "priority": 0,
    "visible": true,
    "active": true,
    "pickable": true,
    "selectable": true,
    "layer": 0,
    "flags": 0,
    "pose": {
      "position": [0, 0, 0],
      "rotation": [0, 0, 0, 1]
    },
    "scale": [1, 1, 1],
    "components": [
      {
        "type": "MeshRenderer",
        "data": {
          "mesh": {"uuid": "mesh-uuid"},
          "material": {"uuid": "material-uuid"},
          "cast_shadow": true
        }
      }
    ],
    "children": [
      {
        "uuid": "child-entity-uuid",
        "name": "Child",
        ...
      }
    ]
  }
}
```

---

## Phase 3: Instance Marker

### 3.1 PrefabInstanceMarker (`termin/visualization/core/prefab_instance_marker.py`)

Компонент, связывающий Entity с исходным PrefabAsset.

```python
class PrefabInstanceMarker(Component):
    """
    Маркер prefab instance.

    Хранит:
    - Ссылку на prefab (uuid)
    - Переопределённые свойства (overrides)
    - Структурные изменения (добавленные/удалённые дети)
    """

    inspect_fields = {
        "prefab_uuid": InspectField(
            path="prefab_uuid",
            label="Prefab",
            kind="string",
            read_only=True,
        ),
        # TODO: кнопки Revert All, Apply to Prefab
    }

    def __init__(
        self,
        prefab_uuid: str = "",
        overrides: dict[str, Any] | None = None,
    ):
        super().__init__()
        self.prefab_uuid = prefab_uuid

        # path → value (переопределённые свойства)
        self.overrides: dict[str, Any] = overrides or {}

        # Структурные изменения
        self.added_children: list[str] = []      # UUID добавленных детей
        self.removed_children: list[str] = []    # UUID удалённых (prefab UUID)

    # --- Override management ---

    def set_override(self, path: str, value: Any) -> None:
        """Записать override."""
        self.overrides[path] = self._serialize_value(value)

    def clear_override(self, path: str) -> None:
        """Удалить override (revert to prefab)."""
        self.overrides.pop(path, None)

    def clear_all_overrides(self) -> None:
        """Удалить все overrides."""
        self.overrides.clear()

    def is_overridden(self, path: str) -> bool:
        """Проверить, переопределён ли путь."""
        return path in self.overrides

    def get_override(self, path: str) -> Any | None:
        """Получить override value или None."""
        return self.overrides.get(path)

    # --- Structural changes ---

    def mark_child_added(self, child_uuid: str) -> None:
        """Отметить добавленного ребёнка."""
        if child_uuid not in self.added_children:
            self.added_children.append(child_uuid)

    def mark_child_removed(self, prefab_child_uuid: str) -> None:
        """Отметить удалённого ребёнка (из prefab)."""
        if prefab_child_uuid not in self.removed_children:
            self.removed_children.append(prefab_child_uuid)

    # --- Lifecycle ---

    def on_added(self, scene: Scene) -> None:
        """Регистрируемся в PrefabRegistry."""
        if self.prefab_uuid:
            PrefabRegistry.register(self.prefab_uuid, self.entity)

    def on_removed(self) -> None:
        """Убираем из PrefabRegistry."""
        if self.prefab_uuid and self.entity:
            PrefabRegistry.unregister(self.prefab_uuid, self.entity)

    # --- Serialization ---

    def serialize_data(self) -> dict:
        """Сериализация для сохранения в сцене."""
        return {
            "prefab_uuid": self.prefab_uuid,
            "overrides": self.overrides,
            "added_children": self.added_children,
            "removed_children": self.removed_children,
        }

    @classmethod
    def deserialize(cls, data: dict, context=None) -> "PrefabInstanceMarker":
        """Десериализация."""
        return cls(
            prefab_uuid=data.get("prefab_uuid", ""),
            overrides=data.get("overrides", {}),
        )
        # TODO: added_children, removed_children
```

### 3.2 Вложенные prefab (Nested Prefabs)

Когда prefab содержит instance другого prefab:

```
OuterPrefab.prefab
└── Entity "Outer"
    └── [PrefabInstance of InnerPrefab]  ← вложенный prefab
        └── Entity "Inner"
```

При instantiate OuterPrefab:
1. Создаём Entity "Outer" с PrefabInstanceMarker(OuterPrefab)
2. Для вложенного — создаём Entity "Inner" с PrefabInstanceMarker(InnerPrefab)
3. Overrides OuterPrefab могут переопределять свойства Inner через путь:
   `"children/Inner/components/MeshRenderer/material"`

При hot-reload InnerPrefab:
1. Обновляются все прямые instances InnerPrefab
2. Обновляются вложенные instances внутри OuterPrefab instances
   (если соответствующие пути не overridden в OuterPrefab)

---

## Phase 4: Integration

### 4.1 ResourceManager Integration

```python
# В ResourceManager добавить:

class ResourceManager:
    _prefab_assets: dict[str, PrefabAsset] = {}

    def get_prefab(self, name: str) -> PrefabAsset | None: ...
    def get_prefab_by_uuid(self, uuid: str) -> PrefabAsset | None: ...
    def register_prefab(self, name: str, asset: PrefabAsset) -> None: ...

    def instantiate_prefab(
        self,
        name_or_uuid: str,
        parent: Transform3 | None = None,
        position: tuple[float, float, float] | None = None,
    ) -> Entity | None:
        """Convenience method для instantiate."""
```

### 4.2 FileWatcher Integration

```python
# В file watcher добавить обработку .prefab:

def _on_prefab_changed(self, path: Path) -> None:
    """Hot-reload prefab при изменении файла."""
    asset = self._find_prefab_asset(path)
    if asset is None:
        return

    # Reload and update all instances
    new_asset = PrefabAsset.from_file(path)
    asset.update_from(new_asset)
```

### 4.3 Entity Serialization Changes

При сериализации Entity проверяем PrefabInstanceMarker:

```python
def serialize(self) -> dict:
    marker = self.get_component(PrefabInstanceMarker)

    if marker is not None:
        # Сохраняем компактно: только ссылку + overrides
        return {
            "prefab_instance": {
                "prefab_uuid": marker.prefab_uuid,
                "overrides": marker.overrides,
                "added_children": marker.added_children,
                "removed_children": marker.removed_children,
            },
            # Плюс базовые данные instance
            "uuid": self.uuid,
            "transform": {...},  # всегда сохраняем transform
        }

    # Обычная сериализация
    return self._serialize_full()
```

При десериализации:

```python
@classmethod
def deserialize(cls, data: dict, context=None) -> Entity:
    if "prefab_instance" in data:
        return cls._deserialize_prefab_instance(data, context)
    return cls._deserialize_full(data, context)

@classmethod
def _deserialize_prefab_instance(cls, data: dict, context=None) -> Entity:
    prefab_data = data["prefab_instance"]
    prefab_uuid = prefab_data["prefab_uuid"]

    # Получаем prefab asset
    rm = ResourceManager.instance()
    prefab = rm.get_prefab_by_uuid(prefab_uuid)
    if prefab is None:
        raise ValueError(f"Prefab {prefab_uuid} not found")

    # Instantiate
    entity = prefab.instantiate()

    # Применяем overrides
    marker = entity.get_component(PrefabInstanceMarker)
    marker.overrides = prefab_data.get("overrides", {})

    for path, value in marker.overrides.items():
        PropertyPath.set(entity, path, value)

    # Восстанавливаем UUID и transform
    entity._uuid = data.get("uuid", entity.uuid)
    # ... transform ...

    return entity
```

---

## Phase 5: Editor Integration

### 5.1 Inspector Changes

При редактировании prefab instance через инспектор:

```python
class ComponentInspectorPanel:
    def _on_field_changed(self, path: str, old_value: Any, new_value: Any):
        # Проверяем, это prefab instance?
        marker = self._get_prefab_marker()
        if marker is not None:
            # Записываем override
            full_path = self._build_full_path(path)
            marker.set_override(full_path, new_value)

        # Применяем изменение
        # ...

    def _get_prefab_marker(self) -> PrefabInstanceMarker | None:
        if self._component is None or self._component.entity is None:
            return None
        return self._component.entity.get_component(PrefabInstanceMarker)
```

### 5.2 Visual Indication

В инспекторе показывать какие поля overridden:
- Жирный текст или цветовая метка для overridden полей
- Контекстное меню "Revert" для каждого overridden поля
- Кнопка "Revert All" в PrefabInstanceMarker

### 5.3 Scene Tree

В дереве сцены показывать:
- Иконка для prefab instances
- Tooltip с именем prefab
- Возможность "Unpack Prefab" (разорвать связь)

---

## Phase 6: Testing

### 6.1 Unit Tests

```python
# test_property_path.py
def test_get_entity_name(): ...
def test_set_transform_position(): ...
def test_get_component_field(): ...
def test_iter_all_properties(): ...

# test_prefab_asset.py
def test_instantiate_creates_marker(): ...
def test_instantiate_generates_new_uuids(): ...
def test_hot_reload_preserves_overrides(): ...

# test_prefab_instance_marker.py
def test_override_set_and_get(): ...
def test_clear_override(): ...
def test_serialization(): ...
```

### 6.2 Integration Tests

```python
def test_prefab_workflow():
    # 1. Create prefab from entity
    # 2. Instantiate
    # 3. Modify instance
    # 4. Save scene
    # 5. Load scene
    # 6. Verify overrides preserved
    # 7. Hot-reload prefab
    # 8. Verify non-overridden updated, overridden preserved
```

---

## Implementation Order

1. **PropertyPath** — базовый блок для всего
2. **PrefabRegistry** — простой, нужен для hot-reload
3. **PrefabInstanceMarker** — компонент маркера
4. **PrefabAsset** — основной класс
5. **ResourceManager integration** — регистрация и получение
6. **Entity serialization changes** — компактное сохранение instances
7. **FileWatcher integration** — hot-reload
8. **Editor integration** — UI для overrides

---

## Open Questions

1. **Undo/Redo для overrides** — как интегрировать с существующей системой?
2. **Prefab variants** — поддержка вариантов (prefab наследует другой prefab)?
3. **Breaking prefab link** — "Unpack Prefab" функциональность?

---

## Files to Create/Modify

### New Files:
- `termin/visualization/core/property_path.py`
- `termin/visualization/core/prefab_registry.py`
- `termin/visualization/core/prefab_asset.py`
- `termin/visualization/core/prefab_instance_marker.py`

### Modified Files:
- `termin/visualization/core/entity.py` — serialize/deserialize changes
- `termin/visualization/core/resources.py` — prefab management
- `termin/editor/prefab_persistence.py` — update to use PrefabAsset
- `termin/editor/editor_inspector.py` — override tracking
- `termin/editor/project_browser.py` — prefab instantiation
- `termin/editor/file_processors/` — add prefab processor
