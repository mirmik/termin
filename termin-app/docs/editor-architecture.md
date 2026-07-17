# Архитектура редактора

Короткая карта того, что у редактора где лежит после удаления Qt/PyQt frontend.

## Слои

```
┌──────────────────────┐
│  View (tcgui)        │
│  termin/editor_tcgui/│
│  — tcgui widgets     │
│  — FBOSurface        │
└──────────┬───────────┘
           │ uses
           ┌────────────▼────────────┐
           │  Controllers (per view) │
           │  editor/*_controller    │
           │  editor_tcgui/*_ctrl    │
           │  — wiring widgets to    │
           │    model                │
           │  — UI-specific setup    │
           └────────────┬────────────┘
                        │ delegates to
           ┌────────────▼────────────┐
           │  Core / Model           │
           │  termin/editor_core/    │
           │  — UI-agnostic state    │
           │  — business logic       │
           │  — services interfaces  │
           └────────────┬────────────┘
                        │ uses
           ┌────────────▼────────────┐
           │  Engine / Scene         │
           │  editor native module   │
           │  scene/render packages  │
           └─────────────────────────┘
```

**Правило**: `editor_core/` не импортирует UI framework напрямую. Нарушать нельзя.

## Что где живёт

### `termin/editor_core/`

UI-agnostic слой. Модели состояния + сервисы.

| Файл | Что |
|------|-----|
| `signal.py` | `Signal` — минимальный pub/sub (`connect`/`disconnect`/`emit`). Используется везде, где модель уведомляет view о смене состояния. |
| `dialog_service.py` | Абстрактный `DialogService` — show_error / show_input / show_choice. Шлёт через callbacks, чтобы core не зависел от конкретного UI. |
| `entity_operations.py` | `EntityOperations` — create / delete / rename / reparent / duplicate + drops prefab/glb. Все scene-tree CRUD живут тут. View вызывает, модель исполняет, диалоги приходят через `DialogService`. |
| `inspector_model.py` | `InspectorKind` enum + `InspectorModel` — какой инспектор активен, что в нём target, набор `show_*` методов + `resync_from_selection` (диспатч по типу выделенного объекта). View подписывается на `changed` Signal. |
| `rendering_model.py` | `RenderingModel` — состояние displays/viewports/render targets: editor_display_ptr, selected_display/viewport, display_input_managers dict. Методы: `attach_scene`, `detach_scene`, `remove_viewports_for_scene`, `sync_viewport_configs_to_scene`, `sync_render_target_configs_to_scene`, `apply_display_input`, `find_viewport_config`. |
| `prefab_edit_controller.py` | `PrefabEditController` — UI-agnostic isolation mode for editing `.prefab` files. |
| `project_session_controller.py` | Общий lifecycle проекта: stdlib sync, shader runtime, project modules, `InitScript.py`, resource scan и восстановление project root. UI frontend передаёт callbacks для ошибок и progress presentation. |
| `spacemouse_controller.py` | `SpaceMouseController` — libspnav integration; polling from the tcgui render loop. |
| `profiler_capture.py` | Общая bounded capture-сессия сырых кадров, статистика/hitch navigation и арбитраж process-global профайлера между несколькими frontend-потребителями. |
| `gizmo/` | Unified gizmo exports and Python collider/constraint helpers used by runtime rendering code. |

### `termin/editor/` — legacy entrypoint

Содержит только совместимые entrypoint-файлы (`python -m termin.editor`,
`termin.editor.run_editor`). Они запускают единственный production frontend —
native UI. UI-код здесь добавлять нельзя.

### `termin/editor_native/` — production native UI

Native frontend композирует главное окно и modeless secondary OS windows через
`NativeUiWindowManager`. `profiler_panel.py` остаётся лёгкой сглаженной сводкой
в dock, а `frame_profiler.py` — отдельный raw-frame frontend: bounded timeline,
пауза/follow, hitch navigation и несглаженное дерево выбранного кадра. Оба
frontend используют общий `ProfilerCaptureCoordinator`, поэтому lifetime одного
потребителя не выключает сбор у другого.

### `termin/editor_tcgui/` — tcgui view

- `tcgui_dialog_service.py`
- `scene_tree_controller.py`
- `inspector_controller.py`
- `rendering_controller.py`
- `scene_file_controller.py` — scene new/save/load/close и валидация scene path относительно проекта.
- `project_session_controller.py` — тонкий tcgui adapter над общим controller из `editor_core`.
- `project_build_controller.py` — run standalone, build package, Android/Quest build entry preparation.
- `editor_window_layout.py` — создание widget tree главного окна без wiring контроллеров.
- `viewport_interaction_hub.py` — viewport click/pointer/key handlers, overlay drawers, active tool counter.
- `debug_panel_controller.py` — Profiler/Modules panel visibility and throttled refresh.
- `fullscreen_controller.py` — сохранение/восстановление visibility состояния панелей fullscreen mode.
- `prefab_toolbar_controller.py` — presentation state toolbar-а prefab editing.
- `game_mode_ui_controller.py` — presentation state Play/Pause buttons, game-mode status и menu action sync.
- `resource_actions_controller.py` — material/components file loading and stdlib deploy.
- `editor_dialog_launcher.py` — запуск settings/viewer/debugger/pipeline диалогов и хранение их view-specific state.
- `component_extension_panel_controller.py` — lifecycle component editor extensions и их inspector/left-tab panels.
- `project_file_action_controller.py` — dispatch активации/выбора файлов project browser к scene/prefab/inspector/text editor actions.
- `viewport_geometry_controller.py` — viewport drag/drop, picking ray/plane helpers и world↔screen projection.
- `editor_interaction_coordinator.py` — undo/redo, selection↔tree/inspector sync, gizmo target и viewport event dispatch.
- `viewport_list_widget.py` — tcgui TreeWidget + toolbar; Signal-based API через `editor_core.Signal`.
- `editor_window.py`

## Паттерны

### Добавить новую scene-операцию

1. Добавь метод в `editor_core/entity_operations.py`, принимающий entity и нужные аргументы.
2. Используй `self._dialog_service` для диалогов.
3. Толкай `UndoCommand` через `self._undo_handler(cmd, False)`.
4. Обнови view через `self._view.xxx(...)` (add_entity / remove_entity / move_entity / update_entity / select_object).
5. Вызов из view: `self._ops.method(...)`.

### Добавить новый инспектор (kind)

1. Добавь enum-value в `InspectorKind` (`editor_core/inspector_model.py`).
2. Добавь метод `show_X(...)` на `InspectorModel` — он делает resolve target и вызывает `self.request(kind, target, label, **extras)`.
3. В tcgui `InspectorControllerTcgui`: положи widget в `_panel_by_kind`, добавь ветку в `_on_model_changed`.

### Добавить новый диалог

Если диалог триггерится из shared-кода (`editor_core`), добавь метод в `DialogService` и реализуй в tcgui-обёртке. Если диалог UI-specific, можно звать tcgui dialog API напрямую.

### Подписаться на селекшн rendering-панели

```python
rendering_model.selection_changed.connect(my_handler)

def my_handler(model: RenderingModel) -> None:
    display = model.selected_display
    viewport = model.selected_viewport
    ...
```

## Sync sdk после правок Python

Старый layout требовал синкать файлы термина в несколько точек, иначе `sdk/bin/termin_launcher` мог запустить устаревшее:

```
termin-app/install/lib/python3.10/site-packages/termin/
sdk/lib/python3.10/site-packages/termin/
~/.pyenv/versions/3.10.19/lib/python3.10/site-packages/termin/
```

Актуальный SDK/standalone layout не должен содержать `sdk/lib/python/termin/` или `termin-app/install/lib/python/termin/`: bundled запуск берет пакеты из `lib/python3.x/site-packages/termin/` на Linux и `python/Lib/site-packages/termin/` на Windows, а editable/test окружение берет Python-код из исходников. Windows не использует `sdk/Lib/`, потому что этот путь конфликтует с native `sdk/lib/` на case-insensitive filesystem.

(См. заметку в `memory/termin_lib_sync_locations.md`.)

## Что ещё открыто

- **Диалоги в view-specific коде** (`pipeline_inspector`, `project_browser`, `scene_manager_viewer`) зовут tcgui API напрямую. Перевод на `DialogService` — opportunistic: при следующем касании этих модулей.
- **Доп. дублирование в frontend-контроллерах** (`get_all_viewports_info`, `_on_add_viewport_requested`) осталось как view-ориентированный код; перенос в модель не принёс бы архитектурного win'а.
