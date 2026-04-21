# Архитектура редактора

Короткая карта того, что у редактора где лежит после MVC-рефакторинга. Для подробностей процесса см. [`refactor-editor-mvc.md`](refactor-editor-mvc.md).

## Слои

```
┌──────────────────────┐   ┌──────────────────────┐
│  View (Qt)           │   │  View (tcgui)        │
│  termin/editor/      │   │  termin/editor_tcgui/│
│  — QWidgets          │   │  — tcgui widgets     │
│  — SDL embed         │   │  — FBOSurface        │
└──────────┬───────────┘   └──────────┬───────────┘
           │                          │
           └────────────┬─────────────┘
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
           │  termin/_native/…       │
           │  termin/visualization/… │
           └─────────────────────────┘
```

**Правило**: `editor_core/` не импортирует Qt и не импортирует tcgui. Нарушать нельзя.

## Что где живёт

### `termin/editor_core/`

UI-agnostic слой. Модели состояния + сервисы.

| Файл | Что |
|------|-----|
| `signal.py` | `Signal` — минимальный pub/sub (`connect`/`disconnect`/`emit`). Используется везде, где модель уведомляет view о смене состояния. |
| `dialog_service.py` | Абстрактный `DialogService` — show_error / show_input / show_choice. Шлёт через callbacks (одинаково для sync Qt и async tcgui). |
| `entity_operations.py` | `EntityOperations` — create / delete / rename / reparent / duplicate + drops prefab/fbx/glb. Все scene-tree CRUD живут тут. View вызывает, модель исполняет, диалоги приходят через `DialogService`. |
| `inspector_model.py` | `InspectorKind` enum + `InspectorModel` — какой инспектор активен, что в нём target, набор `show_*` методов + `resync_from_selection` (диспатч по типу выделенного объекта). View подписывается на `changed` Signal. |
| `rendering_model.py` | `RenderingModel` — состояние displays/viewports/render targets: editor_display_ptr, offscreen_context, selected_display/viewport, display_input_managers dict. Методы: `attach_scene`, `detach_scene`, `remove_viewports_for_scene`, `sync_viewport_configs_to_scene`, `sync_render_target_configs_to_scene`, `apply_display_input`, `find_viewport_config`. |

### `termin/editor/` — Qt view

- `qt_dialog_service.py` — `DialogService` через `QMessageBox`/`QInputDialog`.
- `scene_tree_controller.py` — только QTreeView + контекстное меню; делегирует операции в `EntityOperations`.
- `inspector_controller.py` — QStackedWidget + panel-specific widgets; подписывается на `InspectorModel.changed`.
- `rendering_controller.py` — QTabWidget + SDL embedding (QWindow.fromWinId); делегирует всё, что можно, в `RenderingModel`.
- `viewport_list_widget.py` — QTreeView для дерева Display→Viewport→Entity.
- `editor_window.py` — оркестратор: создаёт модели, сервисы, контроллеры, связывает их коллбэками.

### `termin/editor_tcgui/` — tcgui view

Параллельная структура:

- `tcgui_dialog_service.py`
- `scene_tree_controller.py`
- `inspector_controller.py`
- `rendering_controller.py`
- `viewport_list_widget.py` — tcgui TreeWidget + toolbar; Signal-based API (тот же API, что у Qt — через `editor_core.Signal` вместо pyqtSignal).
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
3. В Qt `InspectorController` зарегистрируй новый widget в `_stack` и добавь ветку в `_on_model_changed` → call panel's set_target.
4. То же в tcgui `InspectorControllerTcgui`: положи widget в `_panel_by_kind`, добавь ветку в `_on_model_changed`.

### Добавить новый диалог

Если диалог триггерится из shared-кода (editor_core), добавь метод в `DialogService` и реализуй в обеих Qt/tcgui обёртках. Если диалог — UI-specific и живёт в одном view, можно звать `QInputDialog`/`show_input_dialog` напрямую.

### Подписаться на селекшн rendering-панели

```python
rendering_model.selection_changed.connect(my_handler)

def my_handler(model: RenderingModel) -> None:
    display = model.selected_display
    viewport = model.selected_viewport
    ...
```

## Sync sdk после правок Python

Файлы термина надо синкать в четыре точки, иначе `sdk/bin/termin_launcher` запустит устаревшее:

```
termin-app/install/lib/python/termin/
sdk/lib/python/termin/
sdk/lib/python3.10/site-packages/termin/
~/.pyenv/versions/3.10.19/lib/python3.10/site-packages/termin/
```

(См. заметку в `memory/termin_lib_sync_locations.md`.)

## Что ещё открыто

- **Диалоги в view-specific коде** (`pipeline_inspector`, `project_browser`, `scene_manager_viewer`) зовут Qt/tcgui API напрямую. Перевод на `DialogService` — opportunistic: при следующем касании этих модулей.
- **Доп. дубликаты Qt/tcgui** в `get_all_viewports_info`, `_on_add_viewport_requested` — остались в контроллерах как view-ориентированный код; перенос в модель не принёс бы архитектурного win'а.
