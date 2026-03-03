# Scene Extensions Architecture

## Цель

Сделать `tc_scene` компактным ядром ECS/lifecycle без хардкод-зависимостей на подсистемы (рендер, коллизии, editor-only state), а subsystem-specific runtime state держать в extension-ах.

## Что считаем ядром сцены

Оставляем в `tc_scene`:

- entity pool + lifecycle компонентов;
- mode/update/fixed timestep;
- type lists/итераторы;
- `name`, `uuid`, `metadata`;
- `layer_names` / `flag_names`.

Все subsystem-specific данные (`collision_world`, `render_state`, и т.п.) живут в extension-ах.

## Термины

- `extension type` - зарегистрированный тип расширения (глобально).
- `extension instance` - объект расширения, прикрепленный к конкретной сцене.
- `type_id` - runtime идентификатор типа extension (`uint64_t`).
- `persistence_key` - строковый ключ extension в сериализации (`extensions.<key>`).

## Текущий C API (фактический)

```c
// tc_scene_extension.h

typedef uint64_t tc_scene_ext_type_id;

typedef struct tc_scene_ext_vtable {
    void* (*create)(tc_scene_handle scene, void* type_userdata);
    void (*destroy)(void* ext, void* type_userdata);

    // Optional runtime hooks
    void (*on_scene_update)(void* ext, double dt, void* type_userdata);
    void (*on_scene_before_render)(void* ext, void* type_userdata);

    // Optional persistence hooks
    bool (*serialize)(void* ext, tc_value* out_data, void* type_userdata);
    bool (*deserialize)(void* ext, const tc_value* in_data, void* type_userdata);
} tc_scene_ext_vtable;

bool tc_scene_ext_register(
    tc_scene_ext_type_id type_id,
    const char* debug_name,
    const char* persistence_key,
    const tc_scene_ext_vtable* vtable,
    void* type_userdata
);

bool tc_scene_ext_attach(tc_scene_handle scene, tc_scene_ext_type_id type_id);
void tc_scene_ext_detach(tc_scene_handle scene, tc_scene_ext_type_id type_id);
void* tc_scene_ext_get(tc_scene_handle scene, tc_scene_ext_type_id type_id);

// Scene-level persistence entrypoints
// Format: { "<persistence_key>": <payload-dict>, ... }
tc_value tc_scene_ext_serialize_scene(tc_scene_handle scene);
void tc_scene_ext_deserialize_scene(tc_scene_handle scene, const tc_value* extensions_dict);

// Runtime hook dispatch (called from tc_scene loops)
void tc_scene_ext_on_scene_update(tc_scene_handle scene, double dt);
void tc_scene_ext_on_scene_before_render(tc_scene_handle scene);
```

## Жизненный цикл

1. Инициализация модуля:
   - модуль вызывает `tc_scene_ext_register(...)`.
2. Создание сцены:
   - код создания сцены attach-ит нужные extension type.
3. Кадровый цикл:
   - `tc_scene_update` / `tc_scene_editor_update` вызывают `tc_scene_ext_on_scene_update(...)`.
4. Перед рендером:
   - `tc_scene_before_render` вызывает `tc_scene_ext_on_scene_before_render(...)`.
5. Уничтожение сцены:
   - `tc_scene_ext_detach_all(...)` и освобождение instance через `destroy`.

## Плюсы текущей модели

- Core scene не знает C++ конкретных типов подсистем.
- Ownership extension instance централизован.
- Persistence extension-ов типизирована и отдельна от `metadata`.
- Поддерживаются selective attach и plug-in model на уровне сцен.

## Сериализация

Рекомендуемый формат scene data:

```json
{
  "extensions": {
    "collision_world": {},
    "render_state": {
      "background_color": [0.05, 0.05, 0.08, 1.0],
      "lighting": {
        "ambient_color": [1.0, 1.0, 1.0],
        "ambient_intensity": 0.1,
        "shadow_settings": { "method": 1, "softness": 1.0, "bias": 0.005 }
      },
      "skybox": {
        "type": 1,
        "color": [0.5, 0.7, 0.9],
        "top_color": [0.4, 0.6, 0.9],
        "bottom_color": [0.6, 0.5, 0.4]
      }
    }
  }
}
```

`metadata` остаётся универсальным каналом для app-specific конфигов, но не заменяет extension state.

## Статус миграции

### Уже сделано

- Этап 1: инфраструктура extension-ов (`register/attach/get/detach`).
- Этап 2: `collision_world` перенесён в extension; старый scene API работает как shim.
- Этап 3: `lighting/skybox/background` перенесены в `render_state` extension.
- Этап 4: `pipeline_templates` и `viewport_configs` перенесены в `render_mount` extension.
- Scene serialization пишет extension state в `extensions.*`.
- `TcSceneRef::serialize()` больше не пишет top-level `scene_pipelines`/`viewport_configs`; данные идут через `extensions.render_mount`.
- `TcSceneRef::load_from_data()` поддерживает legacy top-level поля, адаптируя их в `extensions.render_mount`.
- Добавлены runtime hooks `on_scene_update` и `on_scene_before_render`.

### Что осталось

- Перевести потребителей на extension-first API и убрать legacy shim API из минимального `tc_scene`.
- После полного перевода потребителей удалить fallback чтения legacy top-level полей (`render_state` и `render_mount`).

## Минимальный итоговый инвариант

`tc_scene` знает только:

- core ECS/lifecycle/state;
- generic extension registry + opaque pointers.

Все subsystem-specific runtime объекты живут в extension-ах.
