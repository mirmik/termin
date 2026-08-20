# Technical Notes: Scene Lifecycle, Viewports & Rendering

## Общая архитектура

Три компонента образуют вертикаль управления сценой и рендерингом:

```
GameModeModel (Python)  — оркестрация переходов Play/Stop/Pause
        │
        ▼
SceneManager (C++)      — реестр сцен и их жизненный цикл (режимы, tick)
RenderingManager (C++)  — владелец дисплеев, вьюпортов, рендер-таргетов, пайплайнов
```

`EngineCore::tick_and_render()` (engine_core.cpp:42) связывает их в покадровом цикле:

```
scene_manager.tick(dt)          → should_render?
  rendering_manager.render_all(true)
    → render_mount prepare для реально запланированных сцен
    → offscreen → present
  scene_manager.invoke_after_render()
```

GameModeModel стоит над этим циклом и управляет «крупными» переходами (запуск/остановка игры), переключая сцены между режимами и перемонтируя рендер.

---

## 1. SceneManager — жизненный цикл сцен

**Файлы:**
- `termin-engine/include/termin/scene/scene_manager.hpp`
- `termin-engine/src/scene_manager.cpp`

### Модель состояний

Сцена находится в одном из трёх режимов (`tc_scene_mode`):

| Режим | Поведение в `tick()` |
|---|---|
| `INACTIVE` | Не тикается, не рендерится. Сцена «заморожена». |
| `STOP` | Вызывается `tc_scene_editor_update()` — минимальный цикл для gizmo, инспектора. |
| `PLAY` | Вызывается `tc_scene_update()` — полная симуляция (физика, скрипты). |

SceneManager **не управляет** вьюпортами, дисплеями или рендер-таргетами. Его зона ответственности — только реестр сцен и их mode.

Запись реестра адресуется строгим `SceneKey { identity, role }`. `identity`
обозначает сцену проекта, а transient `SceneRole` различает authoring-экземпляр
редактора и runtime-экземпляр той же сцены. Поэтому
`AUTHORING("Scenes/Main.scene")` и `RUNTIME("Scenes/Main.scene")` могут
существовать одновременно. Роль не сериализуется в `.scene`, а `tc_scene.name`
остаётся коротким диагностическим именем и не используется как ключ реестра.
Для файлов проекта `identity` всегда является нормализованным project-relative
POSIX-путём с суффиксом `.scene`; абсолютный source path хранится отдельно.

### Ключевые операции

- `create_scene(key, extensions)` — аллокация через `tc_scene_new` и строгая регистрация по identity/role;
- `close_scene(key)` или `close_scene(handle)` — дерегистрация и освобождение через `tc_scene_free`. Перед удалением вызывает role-aware `invoke_before_scene_close()`, чтобы RenderingManager или editor успел отмонтировать точный экземпляр;
- `copy_scene(source_key, destination_key)` — создание глубокой копии, в том числе Play-модель `AUTHORING(identity)` → `RUNTIME(identity)` без изменения identity;
- `get_scene(key)` / `key_of(handle)` — однозначное разрешение в обе стороны;
- `rekey_scene(source, destination)` — атомарная смена identity при Save As без
  смены экземпляра или роли;
- `set_mode(key, mode)` или handle-вариант — переключение режима точного экземпляра.

Name-only lookup намеренно отсутствует: если обе роли одной identity загружены,
выбор «единственной подходящей» сцены сделал бы поведение зависимым от порядка
загрузки.

### Правила рендеринга на уровне SceneManager

`tick(dt)` возвращает `true` (требуется рендер), если:
- Есть хотя бы одна сцена в режиме `PLAY`, **или**
- Выставлен флаг `_render_requested` (через `request_render()`)

Режим `STOP` сам по себе рендер не запускает — он тикает сцены для редактора,
но не вызывает `render_all()`, а значит и render lifecycle `prepare_render`.

---

## 2. RenderingManager — дисплеи, вьюпорты, рендер-таргеты

**Файлы:**
- `termin-engine/include/termin/render/rendering_manager.hpp`
- `termin-engine/src/rendering_manager.cpp`

### Ключевые сущности

```
Display (tc_display)
  ├─ render_surface (окно/область вывода)
  ├─ список Viewport'ов
  └─ display-owned input endpoint

Viewport (tc_viewport_handle)
  ├─ rect (регион на дисплее в нормализованных координатах 0-1)
  ├─ depth (порядок отрисовки)
  ├─ scene (привязанная сцена)
  ├─ render_target (куда рендерится; владеет color+depth текстурами)
  └─ managed_by (имя пайплайна, если вьюпорт управляется пайплайном)

RenderTarget (tc_render_target_handle)
  ├─ color_texture, depth_texture (GPU-текстуры)
  ├─ camera (компонент камеры)
  ├─ scene (привязанная сцена)
  ├─ dynamic_resolution (автоматически подстраивается под pixel_rect вьюпорта)
  └─ pipeline (опциональный пайплайн)
```

Важное различие: **Viewport** — это presentation/layout slot. Он может быть пустым и сам не владеет output-текстурами. **RenderTarget** владеет color/depth текстурами и явно назначается viewport'у, когда этот viewport должен что-то показывать.

### Два списка дисплеев

| Список | Назначение | Кто чистит при detach_scene_full |
|---|---|---|
| `displays_` | Сценовые дисплеи | Да (`unmount_scene` по всем) |
| `editor_displays_` | Редакторские дисплеи | Нет (пропускаются) |

Это разделение позволяет редакторским вьюпортам (gizmo, инспектор) пережить detach игровой сцены.

### Модель offscreen-first рендеринга

Рендеринг двухфазный:

**Фаза 1 — `render_all_offscreen()`:**
1. Установить offscreen GL-контекст (с share-group от первого дисплея)
2. `sync_viewport_resolutions()` — синхронизировать dynamic-resolution render target'ы с актуальными pixel_rect'ами вьюпортов
3. Отрендерить managed render target'ы (те, что созданы сценами и отслеживаются `RenderingManager`)
4. Выполнить сценовые пайплайны (`render_scene_pipeline_offscreen`) — для каждого attached_scene, для каждого pipeline:
   - Собрать `ViewportContext` для каждого target-вьюпорта пайплайна (камера, output-текстуры, layer_mask)
   - Собрать lights
   - Вызвать `engine->render_scene_pipeline_offscreen()`
5. Отрендерить RT-backed viewport'ы, которые не управляются scene pipeline. Viewport без `RenderTarget` пропускается.

**Фаза 2 — `present_all()`:**
- Для каждого дисплея (сценовые + редакторские):
  - Сделать контекст дисплея текущим
  - Очистить surface (серый цвет)
  - Отсортировать вьюпорты по depth
  - Для каждого вьюпорта с `RenderTarget`: взять output color texture из render target, блитить в регион дисплея
  - Swap buffers

Ключевое свойство: **все рендерится в offscreen-контексте в общей share-group**, поэтому текстуры, созданные при offscreen-рендере, видны при present на любом дисплее.

### Монтирование/демонтирование сцен (attach_scene_full / detach_scene_full)

**`attach_scene_full(scene)`** — полное подключение сцены к рендеру:
1. Восстановить managed render target'ы из `render_target_configs` сцены (с камерами, pipelines, настройками разрешения)
2. Создать вьюпорты из `viewport_configs` сцены:
   - Для каждого конфига: `get_or_create_display(display_name)` — найти или создать дисплей через factory
   - Аллоцировать вьюпорт, установить rect, depth, scene
   - Найти render target по имени из конфига; если target не найден или имя пустое, оставить viewport пустым
   - Добавить вьюпорт на дисплей
3. `apply_scene_pipelines()` — скомпилировать шаблоны пайплайнов, пометить вьюпорты как `managed_by`
4. Добавить сцену в `attached_scenes_`

**`detach_scene_full(scene)`** — полное отключение:
1. Вызвать `on_render_detach(RenderAttachmentContext)` пока все scene-owned
   pipelines, viewports и targets ещё доступны, затем удалить compiled pipelines
2. `unmount_scene(scene, display)` для каждого сценового дисплея:
   - Найти все вьюпорты на дисплее, ссылающиеся на эту сцену
   - Для каждого: удалить с дисплея, освободить вьюпорт
   - Если render target не зарегистрирован в `managed_render_targets_` и больше нигде не используется — освободить и его
3. Пройти по scene index в `RenderTopology`, освободить принадлежащие сцене targets
4. Удалить сцену из live topology

Дисплеи **не удаляются автоматически** при detach — только если выставлен флаг `auto_remove_when_empty` и на дисплее не осталось вьюпортов (`try_auto_remove_display`).

### ViewportConfig и RenderTargetConfig — откуда берутся настройки

Настройки хранятся в `tc_scene_render_mount` — это extension сцены. При сохранении сцены редактор синхронизирует текущее состояние дисплеев/вьюпортов/RT в конфиги через `sync_scene_render_state()`. При attach они восстанавливаются.

### Render lifecycle и debug geometry

Render-aware компоненты подключаются capability `tc_render_lifecycle`, а не
методами базовой scene-компоненты. Существующий `render_mount` вызывает
`on_render_attach`, `prepare_render` и `on_render_detach`; поэтому сцена без
подключённого рендера не собирает отладочную геометрию и не получает renderer в
обычном `update`.

Типы отладочной геометрии регистрируются процессными metadata-записями со
stable id, display name, category и default enabled state. Значения галочек и
frame-local массив примитивов принадлежат runtime-части `render_mount` и не
сериализуются. На каждом `prepare_render` mount очищает массив, временно выдаёт
компонентам узкий backend-neutral drawer и закрывает его по окончании фазы.
Компонент может публиковать линии и wire primitives, но не получает
`ImmediateRenderer` и не становится обычным `Drawable`.

`DebugGeometryPass` читает готовый массив в согласованной framegraph-фазе и
переводит его в pass-owned `ImmediateRenderer`. Реестр не хранит callbacks или
ссылки на компоненты: при выгрузке модуля его registration удаляется, а уже
собранные примитивы этого типа перестают перечисляться и окончательно исчезают
при подготовке следующего кадра. Scene Properties строит список галочек прямо
из реестра, без hardcoded перечня типов.

Коллайдеры используют этот же путь как тип `physics.colliders`.
`ColliderComponent` публикует канонические box/sphere/capsule/convex-hull
примитивы из `prepare_render`; отдельного обходящего сцену
`ColliderGizmoPass` и отдельного framegraph-ресурса для них нет. Быстрая кнопка
`C` в editor viewport переключает ту же scene setting, что и Scene Properties.

---

## 3. GameModeModel — оркестрация Play/Stop

**Файл:** `termin-app/termin/editor_core/game_mode_model.py`

Это Python-класс без прямых знаний о C++ структурах. Он оркестрирует editor-owned
часть перехода, а gameplay lifecycle, primary scene и безопасную смену render
attachment оставляет `EngineCore::RuntimeSession`.

### Запуск игры (`_start_game_mode`)

```
1. Сохранить состояния редактора:
   - expanded entity UUIDs из scene tree
   - камеру редакторского вьюпорта → scene metadata
   - render state сцены (viewport_configs + render_target_configs)
     → render_connector.sync_scene_render_state()

2. Запустить RuntimeSession и создать игровую копию с тем же identity:
   engine.begin_session(controller)
   runtime_key = SceneKey(identity, RUNTIME)
   game_scene = scene_manager.copy_scene(authoring_key, runtime_key)

3. Привязать копию к RuntimeSession и отключить authoring-сцену от рендера:
   engine.bind_runtime_scene(game_scene)
   render_session.detach(authoring_key, save_state=False)
   // save_state=False — конфиги уже сохранены на шаге 1

4. Запросить initial primary через WorldContext:
   context.request_primary_scene(game_scene)

5. Перевести authoring-сцену в INACTIVE. Runtime-сцена пока остаётся INACTIVE.

6. На safe point следующего EngineCore tick RuntimeSession:
   - монтирует runtime-сцену в render topology;
   - публикует её как primary;
   - активирует её в PLAY.

7. `refresh_primary_scene()` переключает editor presentation на фактически
   committed primary и эмитит `mode_entered`.
```

### Остановка игры (`_stop_game_mode`)

```
1. Вернуть editor presentation и render session к точной AUTHORING-сцене.

2. Завершить RuntimeSession. EngineCore деактивирует primary, снимает gameplay
   render attachment, отвязывает runtime-сцены и вызывает controller.stop.

3. Удалить все RUNTIME-инстансы, созданные во время этой Play-сессии. Снимок
   handle-ов до Play отделяет session-owned сцены от существовавших ранее.

4. Восстановить исходный mode authoring-сцены и эмитить сигналы Stop.
```

### Зачем нужна копия сцены (copy_scene)

Игровая сцена — это полная копия редакторской на момент запуска. Это даёт:
- Изоляцию: симуляция не портит редакторскую сцену
- Возможность вернуться к исходному состоянию при остановке
- Редакторская сцена в INACTIVE не тикается и не рендерится — экономия ресурсов

---

## 4. Полный флоу перехода редактор → игра → редактор

```
Пользователь нажимает Play
        │
        ▼
GameModeModel._start_game_mode()
  ├─ sync_scene_render_state()     — сохранить viewport/render_target конфиги в сцену
  ├─ begin_session(controller)     — создать world-level lifecycle
  ├─ copy_scene(AUTHORING(identity), RUNTIME(identity))
  ├─ bind_runtime_scene(runtime)
  ├─ detach(authoring)
  ├─ request_primary_scene(runtime)
  └─ set_mode(authoring, INACTIVE)

EngineCore safe point
  ├─ attach runtime render topology
  ├─ publish primary
  └─ activate runtime в PLAY

GameModeModel.refresh_primary_scene()
  └─ переключить editor presentation на committed primary

        ... игра работает ...

Пользователь нажимает Stop
        │
        ▼
GameModeModel._stop_game_mode()
  ├─ attach editor presentation к AUTHORING(identity)
  ├─ attach authoring render session
  ├─ end_session()                  — deactivate/detach/unbind/controller.stop
  ├─ reconcile authoring rendering
  ├─ close Play-owned RUNTIME scenes
  └─ restore authoring mode
```

---

## 5. Ключевые инварианты и философия

### Разделение ответственности
- **SceneManager** не знает про рендер. Он управляет временем жизни и режимами сцен.
- **RenderingManager** не знает про режимы сцен (INACTIVE/STOP/PLAY). Он рендерит всё, что к нему примонтировано через `attach_scene_full`.
- **RuntimeSession** выполняет gameplay activation и транзакционную смену render attachment на safe point EngineCore.
- **GameModeModel** компонует RuntimeSession с editor presentation и владеет transient runtime-сценами, созданными во время Play.

### Offscreen-first
Рендеринг всегда идёт в offscreen-текстуры, даже если результат потом показывается на единственном дисплее. Это позволяет пайплайнам собирать вьюпорты с разных дисплеев и рендерить их в одном проходе.

### Дисплеи симметричны
Нет понятия «главный дисплей». Все дисплеи равноправны. Разделение на `displays_` и `editor_displays_` — только для корректной очистки при detach сцены.

### Конфигурация хранится в сцене
`viewport_configs` и `render_target_configs` — это часть данных сцены (через extension `tc_scene_render_mount`). При save/load сцены конфигурация рендера сохраняется и восстанавливается вместе с ней. GameModeModel синхронизирует конфиги перед копированием сцены, чтобы game-копия унаследовала настройки рендера редактора.

### Динамическое разрешение
Render target с `dynamic_resolution=true` автоматически подстраивает размер текстур под `pixel_rect` своего вьюпорта (в `sync_viewport_resolutions()` и `render_scene_pipeline_offscreen()`). Это позволяет вьюпортам менять размер (ресайз окна, сплит-панели) без ручного управления текстурами.

### Владение GPU-ресурсами
- Viewport без render target — пустой presentation slot и не владеет GPU output
- `tc_render_target` владеет `tc_texture` output'ом
- `RenderingManager` владеет скомпилированными пайплайнами (в `scene_pipelines_`)
- При `shutdown()` все ресурсы освобождаются в правильном порядке
