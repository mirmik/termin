# Scene Extensions Architecture

## Цель

Сделать `tc_scene` расширяемой без хардкод-зависимостей на конкретные подсистемы (рендер, коллизии, editor-only state), чтобы:

- ядро сцены оставалось компактным и встраиваемым;
- приложение/движок могло подключать только нужные подсистемы;
- жизненный цикл расширений был централизован и предсказуем.

## Что считаем ядром сцены

Оставляем в `tc_scene`:

- entity pool + lifecycle компонентов;
- mode/update/fixed timestep;
- type lists/итераторы;
- `name`, `uuid`, `metadata`;
- `layer_names` / `flag_names`.

Все subsystem-specific данные (collision world, render scene state, viewport mount state и т.п.) должны жить в extension-ах.

## Термины

- `extension type` - зарегистрированный тип расширения (глобально).
- `extension instance` - объект расширения, прикрепленный к конкретной сцене.
- `scene profile` - набор extension type, который создается для сцены.

## Требования к архитектуре

1. Нулевая зависимость ядра сцены от конкретных C++ типов подсистем.
2. Строгий ownership: extension instance живет ровно столько, сколько живет сцена (если не detach вручную).
3. Простой доступ к extension через `tc_scene_ext_get` без скрытого состояния в подсистемах.
4. Возможность selective attach (какие extension нужны сцене, решает код создания/копирования сцены).
5. Совместимость с C API и C++/Python биндингами.

## C API (предлагаемый контракт)

```c
// tc_scene_extension.h

typedef uint64_t tc_scene_ext_type_id;

typedef struct tc_scene_ext_vtable {
    // Создание инстанса для сцены. Вернуть NULL = attach failed.
    void* (*create)(tc_scene_handle scene, void* type_userdata);

    // Уничтожение инстанса. Гарантируется 1 вызов на успешно созданный ext.
    void (*destroy)(void* ext, void* type_userdata);

    // Optional lifecycle hooks
    void (*on_scene_mode_changed)(void* ext, tc_scene_mode old_mode, tc_scene_mode new_mode);
    void (*on_scene_update)(void* ext, double dt);
    void (*on_scene_before_render)(void* ext);
    void (*on_scene_metadata_changed)(void* ext);
} tc_scene_ext_vtable;

// Регистрация типа extension (глобально)
bool tc_scene_ext_register(
    tc_scene_ext_type_id type_id,
    const char* debug_name,
    const tc_scene_ext_vtable* vtable,
    void* type_userdata
);

// Проверка регистрации
bool tc_scene_ext_is_registered(tc_scene_ext_type_id type_id);

// Attach/detach к конкретной сцене
bool tc_scene_ext_attach(tc_scene_handle scene, tc_scene_ext_type_id type_id);
void tc_scene_ext_detach(tc_scene_handle scene, tc_scene_ext_type_id type_id);
void tc_scene_ext_detach_all(tc_scene_handle scene);

// Получение указателя на инстанс (opaque)
void* tc_scene_ext_get(tc_scene_handle scene, tc_scene_ext_type_id type_id);
bool tc_scene_ext_has(tc_scene_handle scene, tc_scene_ext_type_id type_id);
```

## Идентификаторы extension-ов

Без строк в рантайме:

- `type_id` задается константой на стороне модуля (например, FNV-1a от строкового key на compile-time или просто фиксированный `uint64_t`).
- `debug_name` используется только для логов/диагностики.

Примеры:

- `TC_SCENE_EXT_COLLISION_WORLD`
- `TC_SCENE_EXT_RENDER_STATE`
- `TC_SCENE_EXT_RENDER_MOUNT`

## Жизненный цикл

1. Инициализация модуля:
   - модуль вызывает `tc_scene_ext_register(...)`.
2. Создание сцены:
   - `SceneManager` выбирает profile (`preview`, `gameplay`, `headless`);
   - attach-ит нужные extension type через `tc_scene_ext_attach`.
3. Кадровый цикл:
   - `tc_scene_update` вызывает core lifecycle;
   - затем вызывает hooks extension-ов (`on_scene_update`), если есть.
4. Перед рендером:
   - `tc_scene_before_render` вызывает core callbacks компонентов;
   - затем `on_scene_before_render` extension-ов.
5. Уничтожение сцены:
   - сначала `tc_scene_ext_detach_all`;
   - потом освобождение core данных сцены.

## Создание и копирование сцен

Отдельная система профилей не требуется.

- Код, который создает сцену, сам решает, какие extension attach-ить.
- Код, который копирует сцену, может перечислить extension-ы исходной сцены и создать/скопировать их в целевую.
- Никакого дополнительного "набора расширений" поверх этого механизма не вводим.

## Модель доступа из подсистем

Подсистема получает extension через обычный вызов:

- `ext = tc_scene_ext_get(scene, TYPE_ID)`.

Кэширование указателей как обязательный паттерн не вводим.
Если конкретной подсистеме когда-то понадобится optimization, она может сделать его локально, но это не часть базового контракта.

## Сериализация

Базовый `tc_scene` сериализует только core state.

Для extension-ов вводим optional extension-level сериализацию:

```c
typedef bool (*tc_scene_ext_serialize_fn)(void* ext, tc_value* out_dict);
typedef bool (*tc_scene_ext_deserialize_fn)(void* ext, const tc_value* dict);
```

Рекомендуемый формат в scene data:

```json
{
  "extensions": {
    "collision_world": { ... },
    "render_state": { ... }
  }
}
```

`metadata` остается универсальным каналом для app-specific данных, но не заменяет typed extension state.

## Потоки и синхронизация

Базовое правило: все API `tc_scene_ext_*` вызываются из того же потока, что и scene update/render orchestration.

Если нужен multi-thread:

- синхронизация полностью на стороне extension instance;
- `tc_scene` не берет на себя locks для extension state.

## Ошибки и деградация

- `attach` неуспешен -> явный `false` + `ERROR` лог.
- Подсистема, которой нужен extension, должна явно проверять `NULL` и переходить в predictable режим (например, disable specific pass).
- Без silent fallback.

## План миграции

### Этап 1. Инфраструктура

- Добавить `tc_scene_extension.{h,c}`.
- Встроить storage extension instances в `ScenePool`.
- Подключить `attach/detach/get` API.

### Этап 2. Collision

- Реализовать `collision_world` как extension type.
- Удалить прямое поле `collision_worlds` из `tc_scene` после переходного периода.
- API `tc_scene_get_collision_world` оставить как shim над extension (временно).

### Этап 3. Render scene state

- Перенести `lighting`, `skybox`, `background` в `render_state` extension.
- Перевести render engine на typed extension pointer cached at attach.
- Старые `tc_scene_get_lighting` и skybox API временно оставить как shim.

### Этап 4. Optional render mount state

- Рассмотреть перенос `pipeline_templates` и `viewport_configs` в отдельный extension (`render_mount`).
- Либо оставить в core, если это признано базовой частью scene orchestration.

### Этап 5. Удаление shim API

- После миграции всех потребителей убрать legacy прямые поля/функции.

## Почему не только metadata

`metadata` полезна для конфигов и app-specific расширения, но не заменяет extension framework:

- нет typed ownership/lifecycle hooks;
- нет четкого контракта create/destroy;
- нет быстрой typed-интеграции без парсинга/кастов;
- трудно централизованно управлять подсистемами сцены.

## Минимальный итоговый инвариант

`tc_scene` знает только:

- core ECS/lifecycle/state;
- generic extension registry + opaque pointers.

Все subsystem-specific runtime объекты живут в extension-ах.
