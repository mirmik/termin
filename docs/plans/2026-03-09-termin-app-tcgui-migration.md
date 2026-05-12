# Миграция termin.editor с Qt6 на termin-gui

## Цель

Заменить PyQt6 в редакторе на собственный GUI-фреймворк termin-gui (tcgui).
Параллельная реализация в `termin/editor_tcgui/` — старый редактор (`termin/editor/`) не трогаем до завершения.
Переключение через флаг в `run_editor.py`.

## Ключевые архитектурные решения

### 3D Viewport через FBO

Display не встраивается как отдельное окно. Вместо этого:
- Display рендерит в OpenGL Framebuffer Object (FBO)
- Виджет `Viewport3D` в tcgui владеет FBO, показывает его содержимое через `glBlitFramebuffer`
- Mouse/keyboard события приходят из tcgui и пробрасываются в C++ input manager

Это устраняет необходимость в `SDLEmbeddedWindowBackend` для редактора и убирает зависимость на Qt для встраивания окон.

### Параллельная реализация

```
termin/editor/          ← существующий Qt6 (не трогаем)
termin/editor_tcgui/    ← новая реализация на tcgui
```

Доменный код используется напрямую из обоих вариантов:
- `UndoStack`, `editor_commands.py`
- `SceneManager`, `ResourceManager`
- `ProjectFileWatcher`, `SceneFileController`, `ResourceLoader`
- `EditorSettings`

---

## Фаза 1 — FBO Backend (критический блокер)

Всё остальное зависит от этого.

### 1.1 C++: FBO-вариант `tc_render_surface`

Добавить в C++ (и Python-биндинги):
```
_render_surface_new_from_fbo(fbo_id: int, w: int, h: int) -> int
_render_surface_resize_fbo(ptr: int, new_fbo_id: int, w: int, h: int)
```
Display рендерит в этот FBO. Рендер-пайплайн не знает разницы.

### 1.2 Python: `FBOWindowBackend`

`termin/visualization/platform/backends/fbo_backend.py`:
- Создаёт FBO через `tgfx` graphics backend
- Оборачивает в `tc_render_surface` через `_render_surface_new_from_fbo`
- Реализует тот же интерфейс что `SDLEmbeddedWindowBackend` (poll_events, mouse/key dispatch) но без SDL-окна
- Input-события получает извне (от `Viewport3D` виджета)

### 1.3 tcgui: виджет `Viewport3D`

Новый виджет в `termin-gui/python/tcgui/widgets/viewport3d.py`:
- `layout()`: при изменении размера пересоздаёт FBO, вызывает `on_resize(w, h, fbo_id)`
- `render()`: `glBlitFramebuffer` из FBO в back-buffer (по clip-rect виджета)
- Пробрасывает все mouse/key события в `FBOWindowBackend`
- Коллбек `on_resize` → внешний код обновляет Display

---

## Фаза 2 — Точка входа

`termin/editor_tcgui/run_editor.py`:
```python
ui = UI(width=1600, height=900, title="Termin Editor")
win = EditorWindowTcgui(world, scene, engine.scene_manager, graphics)
win.build(ui)

engine.set_poll_events_callback(lambda: ui.poll())
engine.set_should_continue_callback(lambda: not win.should_close())
```

В корневом `run_editor.py` добавить флаг:
```
--ui=tcgui   (новый)
--ui=qt      (существующий, дефолт пока)
```

---

## Фаза 3 — Скелет EditorWindowTcgui

`termin/editor_tcgui/editor_window.py` — не наследуется ни от чего UI-специфичного.

Layout:
```
VStack
  MenuBar
  Splitter (horizontal, stretch)
    TabView [Scene | Rendering]      ← левая панель
    Viewport3D                       ← центр, растягивается
    ScrollArea > VStack [Inspector]  ← правая панель
  TabView [Project | Console]        ← нижняя панель
  StatusBar
```

Весь инициализационный код (ResourceLoader, ProjectFileWatcher, процессоры, SceneManager,
InteractionSystem) копируется без изменений — он Qt-free.

---

## Фаза 4 — MenuBar

`termin/editor_tcgui/menu_bar_controller.py`:
- Та же сигнатура конструктора (~25 коллбеков)
- Вместо `QMenuBar.addMenu + QAction.triggered.connect`:
  ```python
  menu_bar.add_menu("File", file_menu)
  menu_bar.register_shortcuts(ui)  # уже есть в tcgui
  ```
- `update_undo_redo_actions()` → `item.enabled = can_undo()`
- `update_play_action()` → `item.label = "Stop" / "Play"`

---

## Фаза 5 — Дерево сцены

`termin/editor_tcgui/scene_tree_controller.py`:
- `TreeWidget` (drag-drop уже есть: `draggable=True`, `on_drop`)
- `TreeNode.data = entity`
- `tree.on_select = lambda node: on_object_selected(node.data)`
- Инкрементальные операции: `add_entity`, `remove_entity`, `move_entity`
- Контекстное меню: `ui.show_overlay(menu, ...)` — паттерн из diffusion-editor

`SceneTreeModel(QAbstractItemModel)` удаляется. Логика обходов дерева переезжает в контроллер.

---

## Фаза 6 — Field Widgets

`termin/editor_tcgui/widgets/field_widgets.py`:

| Qt | tcgui |
|---|---|
| `FloatFieldWidget` (DoubleSpinBox) | `SpinBox` (decimals=3) |
| `Vec3FieldWidget` (3× DoubleSpinBox) | `HStack(SpinBox×3)` |
| `BoolFieldWidget` (QCheckBox) | `Checkbox` |
| `StringFieldWidget` (QLineEdit) | `TextInput` |
| `ColorFieldWidget` | `Button` → `ColorDialog` |
| `EnumFieldWidget` (QComboBox) | `ComboBox` |
| `ResourceFieldWidget` | `HStack(TextInput, Button)` |
| `IntFieldWidget` | `SpinBox` (step=1) |

Фаза независима — можно начать параллельно с Фазой 1.

---

## Фаза 7 — TransformInspector и EntityInspector

`termin/editor_tcgui/transform_inspector.py`:
- `QFormLayout` → `VStack(HStack(Label, widget), ...)`
- `DoubleSpinBox` → tcgui `SpinBox`
- `pyqtSignal` → коллбек `on_transform_changed: Callable`

`termin/editor_tcgui/entity_inspector.py`:
- Список компонентов: `QListWidget` → tcgui `ListWidget`
- `QScrollArea` → tcgui `ScrollArea`
- Контекстное меню компонента → tcgui Menu overlay

---

## Фаза 8 — InspectorController

`termin/editor_tcgui/inspector_controller.py`:
- Вместо `QStackedWidget`: каждая панель имеет `widget.visible`
- Показ нужной панели: остальные `visible = False`
- 8 инспекторов: Entity, Material, Display, Viewport, Pipeline, Texture, Mesh, GLB
- Mesh и GLB инспекторы используют `Viewport3D` для preview (зависят от Фазы 1)

---

## Фаза 9 — Project Browser

`termin/editor_tcgui/project_browser.py`:
- Дерево директорий: tcgui `TreeWidget`
- Список файлов: tcgui `ListWidget`
- Drag из файлов в сцену: drag-source в `ListWidget` (нужно добавить в tcgui)

---

## Фаза 10 — Console и Dialogs

**Console**: tcgui `TextArea` (readonly) + перехват лога через `tcbase.log` callback.

**Dialogs**:
- `MessageBox` — есть в tcgui ✓
- `FileDialog` — есть в tcgui ✓
- `InputDialog` (Rename entity и т.п.) — добавить в tcgui: `Dialog(Label + TextInput + OK/Cancel)`
- Scene Properties, Layers, Shadow Settings → `Dialog` + форма из field widgets (Фаза 6)

---

## Фаза 11 — Простые диалоги и действия

Форм-диалоги на основе field widgets (Фаза 6) + простые действия.

| Диалог/действие | Qt-оригинал | Объём |
|---|---|---|
| Settings (text editor path) | `settings_dialog.py` (102) | форма с browse |
| Project Settings (render sync) | `project_settings_dialog.py` (121) | 1 combo |
| Shadow Settings | `shadow_settings_dialog.py` (124) | 3 поля + apply |
| Layers & Flags | `layers_dialog.py` (128) | 2 скролла × 64 поля |
| Fullscreen | `editor_mode_controller.py` (30) | show/hide панелей |
| Run Standalone | `editor_window.py` (20) | subprocess + валидация |
| Undo Stack Viewer | `undo_stack_viewer.py` (96) | 2 списка |

---

## Фаза 12 — Game Mode и Scene конфигурация

| Диалог/действие | Qt-оригинал | Объём |
|---|---|---|
| Toggle Game Mode (Play/Stop) | `editor_mode_controller.py` (50+) | scene mode + UI state |
| Scene Properties | `scene_inspector.py` (596) | multi-tab форма |
| Agent Types | `agent_types_dialog.py` (279) | список + форма |
| SpaceMouse Settings | `spacemouse_settings_dialog.py` (207) | multi-group форма |

---

## Фаза 13 — Debug Viewers (простые)

Tree/list viewers для отладки. Паттерн: `Dialog` + `TreeWidget` + detail panel.

| Viewer | Qt-оригинал | Объём |
|---|---|---|
| Inspect Registry | `inspect_registry_viewer.py` (205) | tree + search + detail |
| NavMesh Registry | `navmesh_registry_viewer.py` (245) | tree + detail |
| Audio Debugger | `audio_debugger.py` (193) | status + channel list |
| Scene Manager Viewer | `scene_manager_viewer.py` (569) | tree + action buttons |

---

## Фаза 14 — Debug Viewers (сложные)

| Viewer | Qt-оригинал | Объём |
|---|---|---|
| Resource Manager Viewer | `resource_manager_viewer.py` (803) | multi-tab tree |
| Core Registry Viewer | `core_registry_viewer.py` (913) | multi-tab C API |
| Profiler Panel | `profiler_panel.py` (409) | graph widget + table |
| Modules Panel | `modules_panel.py` (513) | module list + compiler log |

---

## Фаза 15 — Сложные инструменты (отложить)

Большие standalone-инструменты, можно портировать последними.

| Инструмент | Qt-оригинал | Объём |
|---|---|---|
| Framegraph Debugger | `framegraph_debugger.py` (1116) | C++ core + dual modes + SDL |
| Pipeline Editor | `termin.nodegraph` (1000+) | полноценный node-graph UI |

---

## Фаза 16 — Избавление от Qt в shared-модулях

Четыре модуля из `termin/editor/` используются tcgui-редактором, но содержат Qt-зависимости.
Нужно переписать их как чисто Python (без PyQt6).

### 16.1 `ProjectFileWatcher` (HIGH)

Файл: `termin/editor/project_file_watcher.py`
Qt-зависимости: `QFileSystemWatcher`, `QTimer`

Переписать на `watchdog` или `os.scandir`-based polling:
- Обход директорий, отслеживание mtime
- Периодический rescan через таймер (callback из main loop или `threading.Timer`)
- Сохранить API: `watch_directory(path)`, `register_processor(...)`, `rescan()`, `project_path`

### 16.2 `EditorSettings` (HIGH)

Файл: `termin/editor/settings.py`
Qt-зависимости: `QSettings`

Переписать на `tcbase.Settings` (уже есть в termin-base):
- `from tcbase import Settings` → JSON-хранилище в `~/.config/{app}/settings.json`
- API: `get(key, default)`, `set(key, value)`, `contains(key)`, `group(prefix)` (context manager)
- Автосохранение при каждом `set()`
- `instance()`, `init_text_editor_if_empty()` — сохранить

### 16.3 `ResourceLoader` (HIGH)

Файл: `termin/editor/resource_loader.py`
Qt-зависимости: `QWidget` (parent), `QFileDialog`, `QMessageBox`

- Убрать `parent: QWidget` параметр
- Заменить `QFileDialog` / `QMessageBox` на callback-интерфейс (tcgui вызывает свои диалоги)
- Или: resource_loader уже не использует диалоги напрямую в tcgui пути — проверить и при необходимости вынести диалоговые вызовы в контроллер

### 16.4 `external_editor` (MEDIUM)

Файл: `termin/editor/external_editor.py`
Qt-зависимости: `QWidget`, `QMessageBox`

- `open_in_text_editor(path)` — ядро (`subprocess.Popen`) Qt-free
- Убрать `QMessageBox` — логировать ошибки через `log.error`

---

## Фаза 17 — Переключение

1. Переключить дефолт `run_editor.py` на `--ui=tcgui`
2. Регрессия: открыть проект, сущности, undo/redo, save/load, drag-drop
3. Удалить `--ui=qt` ветку
4. Удалить `termin/editor/`
5. Убрать `PyQt6` из зависимостей
6. Убрать Qt-код из `SDLEmbeddedWindowBackend`

---

## Что нужно добавить в termin-gui

| Компонент | Размер |
|---|---|
| `Viewport3D` виджет | средний |
| `InputDialog` | маленький |
| drag-source в `ListWidget` | маленький |

---

## Граф зависимостей

```
Фаза 1 (FBO Backend) ←── блокирует ──→ Фаза 2 → Фаза 3 → [4,5,8,9,10]
                                                         ↑
Фаза 6 (Field Widgets) ────────────────────────── блокирует Фазы 7,8
```

Рекомендуемый старт: **Фаза 1 + Фаза 6 параллельно**.
