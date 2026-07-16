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
  scene_manager.before_render() → уведомить сцены
  rendering_manager.render_all(true) → offscreen → present
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

### Ключевые операции

- `create_scene(name, extensions)` — аллокация через `tc_scene_new`, регистрация в `_scenes`
- `close_scene(name)` — дерегистрация и освобождение через `tc_scene_free`. Перед удалением вызывает `invoke_before_scene_close()`, чтобы RenderingManager (или editor) успел отмонтировать сцену.
- `copy_scene(…)` — создание глубокой копии (используется GameModeModel для создания игровой сцены из редакторской)
- `set_mode(name, mode)` — переключение режима

### Правила рендеринга на уровне SceneManager

`tick(dt)` возвращает `true` (требуется рендер), если:
- Есть хотя бы одна сцена в режиме `PLAY`, **или**
- Выставлен флаг `_render_requested` (через `request_render()`)

Режим `STOP` сам по себе рендер не запускает — он тикает сцены для редактора, но не вызывает `before_render()` / `render_all()`.

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
  └─ DisplayInputRouter (опционально)

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

---

## 3. GameModeModel — оркестрация Play/Stop

**Файл:** `termin-app/termin/editor_core/game_mode_model.py`

Это Python-класс без прямых знаний о C++ структурах. Он оркеструет переходы, дёргая SceneManager, RenderingManager (через RenderConnector), и EditorConnector.

### Запуск игры (`_start_game_mode`)

```
1. Сохранить состояния редактора:
   - expanded entity UUIDs из scene tree
   - камеру редакторского вьюпорта → scene metadata
   - render state сцены (viewport_configs + render_target_configs)
     → render_connector.sync_scene_render_state()

2. Создать игровую копию сцены:
   game_scene = scene_manager.copy_scene(editor_name, editor_name + "(game)")

3. Отключить редакторскую сцену от рендера:
   render_connector.detach_scene_from_render(editor_name, save_state=False)
   // save_state=False — конфиги уже сохранены на шаге 1

4. Подключить редактор к игровой сцене:
   editor_connector.attach_editor_to_scene(game_name, transfer_camera_state=True)

5. Подключить игровую сцену к рендеру:
   render_connector.attach_scene_to_render(game_name)

6. Переключить режимы:
   editor_scene → INACTIVE
   game_scene   → PLAY

7. Эмитнуть сигналы (state_changed, mode_entered)
```

### Остановка игры (`_stop_game_mode`)

```
1. Отключить редактор от игровой сцены:
   editor_connector.detach_editor_from_scene(save_state=True)

2. Отключить игровую сцену от рендера:
   render_connector.detach_scene_from_render(game_name, save_state=False)

3. Удалить игровую сцену:
   scene_manager.close_scene(game_name)

4. Переключить редакторскую сцену в STOP

5. Подключить редактор обратно к редакторской сцене:
   editor_connector.attach_editor_to_scene(editor_name, restore_state=True)

6. Подключить редакторскую сцену к рендеру:
   render_connector.attach_scene_to_render(editor_name)

7. Эмитнуть сигналы
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
  ├─ copy_scene()                  — создать (game)-копию
  ├─ detach_scene_from_render()    — RenderingManager::detach_scene_full()
  │    ├─ unmount_scene со всех displays_
  │    ├─ освободить standalone RT сцены
  │    └─ detach_scene (пайплайны)
  ├─ attach_editor_to_scene(game)  — editor переключается на game-сцену
  ├─ attach_scene_to_render(game)  — RenderingManager::attach_scene_full()
  │    ├─ восстановить render_target_configs → standalone RT
  │    ├─ создать вьюпорты из viewport_configs → на дисплеи
  │    └─ apply_scene_pipelines → скомпилировать, пометить managed_by
  ├─ set_mode(editor, INACTIVE)
  └─ set_mode(game, PLAY)

        ... игра работает ...

Пользователь нажимает Stop
        │
        ▼
GameModeModel._stop_game_mode()
  ├─ detach_editor_from_scene()      — сохранить состояние редактора
  ├─ detach_scene_from_render(game)  — RenderingManager::detach_scene_full()
  ├─ close_scene(game)               — SceneManager уничтожает сцену
  ├─ set_mode(editor, STOP)
  ├─ attach_editor_to_scene(editor, restore_state=True)
  └─ attach_scene_to_render(editor)  — RenderingManager::attach_scene_full()
       (восстанавливает редакторские вьюпорты из конфигов сцены)
```

---

## 5. Ключевые инварианты и философия

### Разделение ответственности
- **SceneManager** не знает про рендер. Он управляет временем жизни и режимами сцен.
- **RenderingManager** не знает про режимы сцен (INACTIVE/STOP/PLAY). Он рендерит всё, что к нему примонтировано через `attach_scene_full`.
- **GameModeModel** — единственное место, где эти две оси пересекаются. Он решает, *какую* сцену и *когда* монтировать/демонтировать.

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
