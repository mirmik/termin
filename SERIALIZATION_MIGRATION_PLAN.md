# План миграции сериализации сцены в C++

## Обзор

Перенос сериализации/десериализации сцены из Python в C++ с использованием `nos::trent` для JSON.

**Не трогаем:** core_c (tc_value остаётся для inspect, но сериализация через trent)

## Зависимости

- `nos::trent` - JSON-like dict, уже используется в проекте (trent lib)
- `entity_lib` - Entity, Component, ComponentRegistry
- `tc_scene` - уже есть в C++

---

## Фаза 1: Entity сериализация

### 1.1 Entity::serialize() → trent

**Файл:** `cpp/termin/entity/entity.cpp`

```cpp
nos::trent Entity::serialize() const {
    if (!valid() || !serializable()) {
        return nos::trent();  // nil
    }

    nos::trent data;

    // Base data (из существующего serialize_base, но в trent)
    data["uuid"] = uuid();
    data["name"] = name();
    data["priority"] = priority();
    data["visible"] = visible();
    data["enabled"] = enabled();
    data["pickable"] = pickable();
    data["selectable"] = selectable();
    data["layer"] = static_cast<int64_t>(layer());
    data["flags"] = static_cast<int64_t>(flags());

    // Pose
    double pos[3], rot[4], scl[3];
    get_local_position(pos);
    get_local_rotation(rot);
    get_local_scale(scl);

    data["pose"]["position"] = {pos[0], pos[1], pos[2]};
    data["pose"]["rotation"] = {rot[0], rot[1], rot[2], rot[3]};
    data["scale"] = {scl[0], scl[1], scl[2]};

    // Components
    nos::trent components_list = nos::trent::array();
    for (size_t i = 0; i < component_count(); i++) {
        Component* comp = component_at(i);
        if (comp && comp->serializable()) {
            components_list.push_back(comp->serialize());
        }
    }
    data["components"] = std::move(components_list);

    // Children (рекурсия)
    nos::trent children_list = nos::trent::array();
    for (Entity* child : children()) {
        if (child && child->serializable()) {
            children_list.push_back(child->serialize());
        }
    }
    if (!children_list.empty()) {
        data["children"] = std::move(children_list);
    }

    return data;
}
```

### 1.2 Entity::deserialize_base() - создание entity

**Файл:** `cpp/termin/entity/entity.cpp`

```cpp
// Создаёт entity из данных (Phase 1 - без компонентов)
static Entity Entity::deserialize_base(
    const nos::trent& data,
    tc_scene_handle scene
) {
    std::string uuid = data["uuid"].as_string_or("");
    std::string name = data["name"].as_string_or("Entity");

    if (uuid.empty()) {
        return Entity();  // invalid
    }

    // Получить pool из scene
    tc_entity_pool_handle pool_handle;
    if (tc_scene_handle_valid(scene)) {
        tc_entity_pool* pool = tc_scene_entity_pool(scene);
        pool_handle = tc_entity_pool_registry_find(pool);
    } else {
        pool_handle = standalone_pool_handle();
    }

    // Создать entity с UUID
    Entity ent = Entity::create_with_uuid(pool_handle, name, uuid);
    if (!ent.valid()) {
        return ent;
    }

    // Восстановить базовые свойства
    ent.set_priority(data["priority"].as_int_or(0));
    ent.set_visible(data["visible"].as_bool_or(true));
    ent.set_enabled(data["enabled"].as_bool_or(true));
    ent.set_pickable(data["pickable"].as_bool_or(true));
    ent.set_selectable(data["selectable"].as_bool_or(true));
    ent.set_layer(data["layer"].as_int_or(0));
    ent.set_flags(data["flags"].as_int_or(0));

    // Pose
    if (data.contains("pose")) {
        auto& pose = data["pose"];
        if (pose.contains("position")) {
            auto& p = pose["position"];
            ent.set_local_position(p[0].as_double(), p[1].as_double(), p[2].as_double());
        }
        if (pose.contains("rotation")) {
            auto& r = pose["rotation"];
            ent.set_local_rotation(r[0].as_double(), r[1].as_double(),
                                   r[2].as_double(), r[3].as_double());
        }
    }
    if (data.contains("scale")) {
        auto& s = data["scale"];
        ent.set_local_scale(s[0].as_double(), s[1].as_double(), s[2].as_double());
    }

    return ent;
}
```

### 1.3 Entity::deserialize_components() - Phase 2

**Файл:** `cpp/termin/entity/entity.cpp`

```cpp
void Entity::deserialize_components(const nos::trent& data, tc_scene_handle scene) {
    if (!valid()) return;

    if (!data.contains("components")) return;

    auto& components = data["components"];
    for (size_t i = 0; i < components.size(); i++) {
        auto& comp_data = components[i];

        std::string type_name = comp_data["type"].as_string_or("");
        if (type_name.empty()) continue;

        // Создать компонент через registry
        Component* comp = ComponentRegistry::instance().create(type_name);
        if (!comp) {
            tc::Log::warn("[Entity] Unknown component type: %s", type_name.c_str());
            continue;
        }

        // Десериализовать данные компонента
        if (comp_data.contains("data")) {
            comp->deserialize_data(comp_data["data"], scene);
        }

        // Добавить к entity
        add_component(comp);
    }
}
```

---

## Фаза 2: Component сериализация через trent

### 2.1 Component::serialize() → trent

**Файл:** `cpp/termin/entity/component.hpp`

```cpp
virtual nos::trent serialize() const {
    nos::trent result;
    result["type"] = type_name();
    result["data"] = serialize_data();
    return result;
}

virtual nos::trent serialize_data() const {
    // Конвертировать tc_inspect результат в trent
    // Или переписать на чистый trent
    return tc_value_to_trent(tc_inspect_serialize(...));
}

virtual void deserialize_data(const nos::trent& data, tc_scene_handle scene) {
    // Конвертировать trent в tc_value и использовать tc_inspect
    // Или переписать на чистый trent
}
```

### 2.2 Конвертер tc_value ↔ trent (УЖЕ ЕСТЬ)

**Файл:** `cpp/termin/render/tc_value_trent.hpp`

```cpp
namespace tc {
    nos::trent tc_value_to_trent(const tc_value& v);
    tc_value trent_to_tc_value(const nos::trent& t);
}
```

Используем существующий конвертер для совместимости с tc_inspect.

---

## Фаза 3: Scene сериализация

### 3.1 TcScene::serialize() → trent

**Файл:** `cpp/termin/tc_scene.cpp`

```cpp
nos::trent TcScene::serialize() const {
    nos::trent result;

    result["uuid"] = uuid();
    result["background_color"] = {bg[0], bg[1], bg[2], bg[3]};

    // Root entities (без parent, serializable)
    nos::trent entities = nos::trent::array();
    for (Entity* e : get_root_entities()) {
        if (e->serializable()) {
            entities.push_back(e->serialize());
        }
    }
    result["entities"] = std::move(entities);

    // Layer/flag names
    nos::trent layer_names, flag_names;
    for (int i = 0; i < 64; i++) {
        const char* ln = get_layer_name(i);
        if (ln && ln[0]) layer_names[std::to_string(i)] = ln;
        const char* fn = get_flag_name(i);
        if (fn && fn[0]) flag_names[std::to_string(i)] = fn;
    }
    result["layer_names"] = std::move(layer_names);
    result["flag_names"] = std::move(flag_names);

    // Viewport configs
    nos::trent viewport_configs = nos::trent::array();
    for (auto& vc : _viewport_configs) {
        viewport_configs.push_back(serialize_viewport_config(vc));
    }
    result["viewport_configs"] = std::move(viewport_configs);

    // Pipeline templates
    nos::trent pipelines = nos::trent::array();
    for (int i = 0; i < pipeline_template_count(); i++) {
        auto t = pipeline_template_at(i);
        if (t.is_valid) {
            nos::trent p;
            p["uuid"] = t.uuid;
            pipelines.push_back(p);
        }
    }
    result["scene_pipelines"] = std::move(pipelines);

    // Lighting
    result["ambient_color"] = {ambient[0], ambient[1], ambient[2]};
    result["ambient_intensity"] = ambient_intensity();
    result["shadow_settings"] = serialize_shadow_settings();

    // Skybox
    result["skybox_type"] = skybox_type();
    result["skybox_color"] = {...};
    result["skybox_top_color"] = {...};
    result["skybox_bottom_color"] = {...};

    // Metadata
    if (!_metadata.is_nil()) {
        result["metadata"] = _metadata;
    }

    return result;
}
```

### 3.2 TcScene::load_from_data() - двухфазная десериализация

**Файл:** `cpp/termin/tc_scene.cpp`

```cpp
int TcScene::load_from_data(const nos::trent& data, bool update_settings) {
    tc_scene_handle scene_h = handle();

    if (update_settings) {
        // Background color
        if (data.contains("background_color")) {
            auto& bg = data["background_color"];
            set_background_color(bg[0].as_double(), bg[1].as_double(),
                                 bg[2].as_double(), bg[3].as_double());
        }

        // Lighting
        // ... ambient_color, ambient_intensity, shadow_settings

        // Skybox
        // ... skybox_type, skybox_color, etc.

        // Layer/flag names
        if (data.contains("layer_names")) {
            for (auto& [k, v] : data["layer_names"].items()) {
                set_layer_name(std::stoi(k), v.as_string().c_str());
            }
        }
        // ... flag_names

        // Viewport configs
        clear_viewport_configs();
        if (data.contains("viewport_configs")) {
            for (auto& vc_data : data["viewport_configs"]) {
                add_viewport_config(deserialize_viewport_config(vc_data));
            }
        }

        // Pipeline templates
        clear_pipeline_templates();
        if (data.contains("scene_pipelines")) {
            for (auto& sp : data["scene_pipelines"]) {
                std::string uuid = sp["uuid"].as_string_or("");
                if (!uuid.empty()) {
                    auto templ = TcScenePipelineTemplate::find_by_uuid(uuid);
                    if (templ.is_valid) {
                        add_pipeline_template(templ);
                    }
                }
            }
        }

        // Metadata
        if (data.contains("metadata")) {
            set_metadata(data["metadata"]);
        }
    }

    // === Two-phase deserialization ===

    // Collect (entity, data) pairs
    std::vector<std::pair<Entity, nos::trent>> entity_data_pairs;

    // Phase 1: Create entity hierarchy
    if (data.contains("entities")) {
        for (auto& ent_data : data["entities"]) {
            deserialize_entity_hierarchy(ent_data, scene_h, entity_data_pairs);
        }
    }

    // Phase 2: Deserialize components
    for (auto& [ent, ent_data] : entity_data_pairs) {
        ent.deserialize_components(ent_data, scene_h);
    }

    return entity_data_pairs.size();
}

void TcScene::deserialize_entity_hierarchy(
    const nos::trent& data,
    tc_scene_handle scene,
    std::vector<std::pair<Entity, nos::trent>>& pairs
) {
    Entity ent = Entity::deserialize_base(data, scene);
    if (!ent.valid()) return;

    // Collect for phase 2
    pairs.emplace_back(ent, data);

    // Children
    if (data.contains("children")) {
        for (auto& child_data : data["children"]) {
            deserialize_entity_hierarchy(child_data, scene, pairs);
            // TODO: set_parent после создания
        }
    }
}
```

---

## Фаза 4: ViewportConfig сериализация

**Файл:** `cpp/termin/viewport_config.cpp` (новый или добавить в существующий)

```cpp
nos::trent serialize_viewport_config(const ViewportConfig& vc) {
    nos::trent data;
    data["name"] = vc.name;
    data["display_name"] = vc.display_name;
    data["camera_uuid"] = vc.camera_uuid;
    data["region"] = {vc.x, vc.y, vc.w, vc.h};
    data["depth"] = vc.depth;
    data["input_mode"] = static_cast<int>(vc.input_mode);
    data["block_input_in_editor"] = vc.block_input_in_editor;
    data["pipeline_uuid"] = vc.pipeline_uuid;
    data["layer_mask"] = format_hex(vc.layer_mask);
    data["enabled"] = vc.enabled;
    return data;
}

ViewportConfig deserialize_viewport_config(const nos::trent& data) {
    ViewportConfig vc;
    vc.name = data["name"].as_string_or("default");
    vc.display_name = data["display_name"].as_string_or("");
    vc.camera_uuid = data["camera_uuid"].as_string_or("");
    // ... остальные поля
    return vc;
}
```

---

## Фаза 5: JSON I/O

**Используем trent напрямую:**

```cpp
// Сериализация в JSON строку
std::string TcScene::to_json_string() const {
    nos::trent data = serialize();
    std::ostringstream oss;
    nos::print_to(oss, data);  // или json_print_to
    return oss.str();
}

// Десериализация из JSON строки
void TcScene::from_json_string(const std::string& json) {
    nos::trent data = nos::json::parse(json);
    load_from_data(data, true);
}

// Сохранение в файл
void TcScene::save_to_file(const std::string& path) {
    std::ofstream f(path);
    nos::trent data = serialize();
    nos::json_print_to(f, data, 2);  // indent=2
}

// Загрузка из файла
void TcScene::load_from_file(const std::string& path) {
    std::ifstream f(path);
    nos::trent data = nos::json::parse(f);
    load_from_data(data, true);
}
```

---

## Фаза 6: Python bindings

**Файл:** `cpp/termin/tc_scene_bindings.cpp`

```cpp
// Expose to Python
m.def("serialize", [](TcScene& scene) {
    nos::trent data = scene.serialize();
    return trent_to_python_dict(data);  // конвертер в Python dict
});

m.def("load_from_data", [](TcScene& scene, nb::dict data, bool update_settings) {
    nos::trent tdata = python_dict_to_trent(data);
    return scene.load_from_data(tdata, update_settings);
});
```

Или проще - возвращать JSON string и парсить в Python:

```cpp
m.def("serialize_json", &TcScene::to_json_string);
m.def("load_from_json", &TcScene::from_json_string);
```

---

## Порядок реализации

**Конвертер tc_value ↔ trent уже есть:** `cpp/termin/render/tc_value_trent.hpp`
- `tc::trent_to_tc_value(const nos::trent& t)`
- `tc::tc_value_to_trent(const tc_value& v)`

1. **Entity::serialize()** с children
2. **Entity::deserialize_base()** - создание entity
3. **Entity::deserialize_components()**
4. **TcScene::serialize()**
5. **TcScene::load_from_data()** с двухфазной десериализацией
6. **ViewportConfig** сериализация
7. **JSON I/O** (to_json_string, from_json_string)
8. **Python bindings**
9. **Тесты**
10. **Миграция Python кода** на вызовы C++

---

## Файлы для изменения

| Файл | Изменения |
|------|-----------|
| `cpp/termin/entity/entity.hpp` | Добавить serialize(), deserialize_base(), deserialize_components() |
| `cpp/termin/entity/entity.cpp` | Реализация методов |
| `cpp/termin/entity/component.hpp` | serialize() → trent |
| `cpp/termin/tc_scene.hpp` | Добавить serialize(), load_from_data() |
| `cpp/termin/tc_scene.cpp` | Реализация |
| `cpp/termin/tc_scene_bindings.cpp` | Python bindings |
| `cpp/termin/viewport_config.cpp` | Сериализация ViewportConfig |

**Используем существующие:**
| `cpp/termin/render/tc_value_trent.hpp` | Конвертер tc_value ↔ trent |

---

## Оценка трудозатрат

| Фаза | Оценка |
|------|--------|
| Entity сериализация | 1 день |
| TcScene сериализация | 1.5 дня |
| ViewportConfig | 0.5 дня |
| JSON I/O | 0.5 дня |
| Python bindings | 0.5 дня |
| Тесты | 1 день |
| Миграция Python | 1 день |
| **Итого** | **~6 дней** |
