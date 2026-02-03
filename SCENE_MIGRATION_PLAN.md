# План миграции Scene в C++ (полный реэкспорт)

## Цель

Заменить `class Scene(TcScene)` на `Scene = TcScene` (чистый реэкспорт).

---

## Фаза 1: Удаление `_current_scene` глобала

### 1.1 Проблема

Компоненты используют `get_current_scene()` в `start()` для получения сцены.
Но `self.entity.scene` уже работает во время `start()`.

### 1.2 Файлы для изменения

| Файл | Изменение |
|------|-----------|
| `termin/tween/component.py` | Заменить `get_current_scene()` на `self.entity.scene` |
| `termin/physics/physics_world_component.py` | Заменить `get_current_scene()` на `self.entity.scene` |
| `termin/physics/rigid_body_component.py` | Заменить `get_current_scene()` на `self.entity.scene` |
| `termin/physics/fem_physics_world_component.py` | Заменить `get_current_scene()` на `self.entity.scene` |
| `termin/navmesh/agent_component.py` | Заменить `get_current_scene()` на `self.entity.scene` |
| `termin/audio/components/audio_source.py` | Заменить `get_current_scene()` на `self.entity.scene` |
| `termin/editor/module_watcher.py` | Получать scene через другой механизм (editor context) |

### 1.3 После изменений

- Удалить `_current_scene` глобал из `_scene.py`
- Удалить `get_current_scene()` функцию
- Удалить установку `_current_scene` в `update()`, `editor_update()`, `add()`

---

## Фаза 2: Конструктор TcScene

### 2.1 Текущий Python конструктор

```python
def __init__(self, background_color=(0.05, 0.05, 0.08, 1.0), uuid=None, name=""):
    super().__init__()
    self.set_py_wrapper(self)
    self.uuid = uuid or ""
    self.name = name
    self.set_background_color(...)
```

### 2.2 Требуемые изменения в C++

**Файл:** `cpp/termin/tc_scene.cpp`

```cpp
// Добавить конструктор с параметрами
TcScene::TcScene(const std::string& name, const std::string& uuid) {
    _h = tc_scene_create();
    if (!uuid.empty()) set_uuid(uuid);
    if (!name.empty()) set_name(name);
}
```

**Файл:** `cpp/termin/tc_scene_bindings.cpp`

```cpp
nb::class_<TcScene>(m, "TcScene")
    .def(nb::init<>())
    .def(nb::init<const std::string&, const std::string&>(),
         nb::arg("name") = "", nb::arg("uuid") = "")
    .def("set_background_color", ...)  // уже есть
```

### 2.3 py_wrapper

`set_py_wrapper` нужен для callback'ов из C в Python.
В чистом C++ сценарии он не нужен.
Оставить как опциональный метод для Python-расширений.

---

## Фаза 3: Numpy convenience properties

### 3.1 Текущие Python properties

```python
@property
def background_color(self) -> np.ndarray:
    r, g, b, a = self.get_background_color()
    return np.array([r, g, b, a], dtype=np.float32)
```

### 3.2 Решение: Добавить в C++ bindings

**Файл:** `cpp/termin/tc_scene_bindings.cpp`

```cpp
.def_prop_rw("background_color",
    [](TcScene& self) {
        auto [r, g, b, a] = self.get_background_color();
        // Return as numpy array or tuple
        return nb::make_tuple(r, g, b, a);
    },
    [](TcScene& self, nb::object value) {
        // Accept tuple, list, or numpy array
        auto arr = nb::cast<std::array<float, 4>>(value);
        self.set_background_color(arr[0], arr[1], arr[2], arr[3]);
    })
```

Аналогично для:
- `skybox_color`, `skybox_top_color`, `skybox_bottom_color`
- `ambient_color`

### 3.3 skybox_type string ↔ int

Текущий Python код конвертирует "gradient"/"solid"/"none" ↔ int.

**Решение:** Добавить в C++ bindings:

```cpp
.def_prop_rw("skybox_type_str",
    [](TcScene& self) -> std::string {
        int t = self.get_skybox_type();
        if (t == TC_SKYBOX_GRADIENT) return "gradient";
        if (t == TC_SKYBOX_SOLID) return "solid";
        return "none";
    },
    [](TcScene& self, const std::string& s) {
        int t = TC_SKYBOX_GRADIENT;
        if (s == "solid") t = TC_SKYBOX_SOLID;
        else if (s == "none") t = TC_SKYBOX_NONE;
        self.set_skybox_type(t);
    })
```

---

## Фаза 4: Entity add/remove

### 4.1 Текущий Python код

```python
def add(self, entity):
    entity = self.migrate_entity(entity)
    for component in entity.components:
        self.register_component(component)  # Теперь не нужно!
    entity.on_added(self)
    # Рекурсивно для children
    return entity
```

### 4.2 После исправления tc_entity_pool_migrate

Миграция теперь автоматически регистрирует компоненты.

### 4.3 Решение: Добавить add_entity в C++

**Файл:** `cpp/termin/tc_scene.cpp`

```cpp
Entity TcScene::add_entity(Entity& entity) {
    Entity migrated = migrate_entity(entity);
    if (!migrated.valid()) return migrated;

    // Notify entity
    migrated.on_added_to_scene(_h);

    // Recursively notify children
    for (Entity child : migrated.children()) {
        notify_entity_added_recursive(child);
    }

    return migrated;
}

void TcScene::notify_entity_added_recursive(Entity& entity) {
    entity.on_added_to_scene(_h);
    for (Entity child : entity.children()) {
        notify_entity_added_recursive(child);
    }
}
```

### 4.4 Entity.on_added_to_scene

Уже существует в C++: `Entity::on_added_to_scene(tc_scene_handle scene)`

---

## Фаза 5: Component search

### 5.1 Текущий Python код

```python
def find_component(self, component_type: type) -> Component | None:
    for entity in self.get_all_entities():
        comp = entity.get_component(component_type)
        if comp is not None:
            return comp
    return None
```

### 5.2 Решение

Эти методы ищут по Python типу. В C++ мы ищем по type_name строке.

**Вариант A:** Добавить helper в Python (не в классе Scene):

```python
# termin/visualization/core/scene_utils.py
def find_component_by_type(scene, component_type):
    type_name = component_type.__name__
    for entity in scene.get_all_entities():
        comp = entity.get_component_by_type(type_name)
        if comp:
            return comp
    return None
```

**Вариант B:** Добавить в C++ bindings как свободную функцию.

---

## Фаза 6: Editor metadata helpers

### 6.1 Текущий Python код

```python
@property
def editor_viewport_camera_name(self) -> str | None:
    return self.get_metadata_value("termin.editor.viewport_camera_name")
```

### 6.2 Решение

Это editor-specific. Можно:
- Оставить в editor коде (не в Scene)
- Или добавить в C++ bindings

**Рекомендация:** Вынести в `termin/editor/scene_metadata.py`:

```python
def get_editor_viewport_camera_name(scene):
    return scene.get_metadata_value("termin.editor.viewport_camera_name")
```

---

## Фаза 7: Serialization

### 7.1 Статус

Уже реализовано в C++:
- `TcScene::serialize()` → trent
- `TcScene::load_from_data()`
- `serialize_cpp()`, `load_from_data_cpp()` bindings
- `to_json_string()`, `from_json_string()`

### 7.2 Python compatibility

Текущий Python использует:
```python
data = scene.serialize()  # Возвращает dict
Scene.deserialize(data)   # Создаёт Scene из dict
```

**Решение:** Алиасы в bindings:

```cpp
.def("serialize", [](TcScene& self) {
    return trent_to_python(self.serialize());
})

// classmethod deserialize
m.def("deserialize_scene", [](nb::dict data) {
    TcScene scene;
    scene.load_from_data(python_to_trent(data), true);
    return scene;
});
```

---

## Фаза 8: destroy() и lifecycle

### 8.1 Текущий Python код

```python
def destroy(self):
    for entity in self.get_all_entities():
        for tc_ref in entity.tc_components:
            tc_ref.on_destroy()
    TcScene.destroy(self)
```

### 8.2 Решение

Перенести в C++:

```cpp
void TcScene::destroy() {
    // Call on_destroy for all components
    for (Entity& e : get_all_entities()) {
        for (size_t i = 0; i < e.component_count(); i++) {
            tc_component* c = e.component_at(i);
            tc_component_on_destroy(c);
        }
    }
    tc_scene_destroy(_h);
}
```

---

## Фаза 9: Финальная структура ✅ DONE

### 9.1 termin/visualization/core/scene/__init__.py

```python
"""Scene module - container for entities and scene configuration."""

from termin._native.scene import TcScene as Scene, deserialize_scene
from termin.lighting import ShadowSettings

from ._helpers import find_component, find_components, dispatch_input

__all__ = [
    "Scene",
    "ShadowSettings",
    "deserialize_scene",
    "find_component",
    "find_components",
    "dispatch_input",
]
```

### 9.2 Удалено

- ✅ `termin/visualization/core/scene/_scene.py`
- ✅ `termin/visualization/core/scene/lighting.py`
- ✅ `get_current_scene()` (удалено ранее)
- ✅ `_current_scene` глобал (удалено ранее)

---

## Порядок выполнения

1. **Фаза 1:** ✅ DONE - Удалить `_current_scene` (рефакторинг компонентов)
2. **Фаза 2:** ✅ DONE - Конструктор TcScene с параметрами (name, uuid)
3. **Фаза 3:** ✅ DONE - Vec3/Vec4 properties (заменили numpy на Vec3/Vec4)
4. **Фаза 4:** ✅ DONE - `add()` упрощён (migration auto-registers, only notify callbacks)
5. **Фаза 5:** ✅ DONE - `find_component_by_name` оптимизирован (использует get_components_of_type)
6. **Фаза 6:** ✅ DONE - Editor metadata - редактор использует metadata API напрямую
7. **Фаза 7:** ✅ DONE - Serialization (serialize/load_from_data/deserialize_scene)
8. **Фаза 8:** ✅ DONE - destroy() перенесён в C++ bindings
9. **Фаза 9:** ✅ DONE - Scene = TcScene (чистый реэкспорт)

---

## Риски

1. **Обратная совместимость** - код использующий `Scene(background_color=...)` должен работать
2. **py_wrapper** - некоторые callback'и могут перестать работать
3. **Тесты** - нужно обновить тесты сериализации

---

## Оценка

| Фаза | Сложность |
|------|-----------|
| Фаза 1 | Средняя (много файлов) |
| Фаза 2 | Низкая |
| Фаза 3 | Низкая |
| Фаза 4 | Низкая |
| Фаза 5 | Низкая |
| Фаза 6 | Низкая |
| Фаза 7 | Готово |
| Фаза 8 | Низкая |
| Фаза 9 | Низкая |
