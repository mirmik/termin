# Миграция SceneManager в C++ - ЗАВЕРШЕНА

## Результат

**Python SceneManager: 9 строк** (было ~700) - чистый реэкспорт!

### C++ SceneManager (`cpp/termin/scene/scene_manager.hpp/cpp`):
- Scene lifecycle: `create_scene`, `close_scene`, `copy_scene`
- Scene access: `get_scene`, `has_scene`, `scene_names`
- File I/O: `load_scene`, `save_scene`, `read_json_file`, `write_json_file`
- Path management: `get_scene_path`, `set_scene_path`
- Mode management: `get_mode`, `set_mode`, `has_play_scenes`
- Update cycle: `tick`, `tick_and_render`, `before_render`
- Callbacks: `set_on_after_render`, `set_on_before_scene_close`

### Python SceneManager (`termin/editor/scene_manager.py`):
Чистый реэкспорт из C++:
```python
from termin._native.scene import SceneManager, SceneMode
```

### EditorWindow:
- `_editor_data: dict` - хранение editor state
- `_store_editor_data` - сохранение при загрузке
- `_collect_editor_state` - сбор при сохранении
- `_apply_editor_state` - применение после загрузки
- `_on_before_scene_close(scene_name)` - принимает имя, получает scene через get_scene

### SceneFileController:
- `store_editor_data` callback
- `collect_editor_data` callback
- `_extract_editor_data` - извлечение из файла

## Ключевые изменения

1. **C++ bindings возвращают TcScene** (не tuple handles)
2. **tick_and_render()** - полный цикл в C++ с RenderingManager
3. **Editor data в EditorWindow** (не в SceneManager)
4. **Убран game timer** (не используется)
5. **Убраны editor callbacks** из SceneManager (10 штук)
6. **Убран resource_manager** из SceneManager

## Архитектура

```
C++ SceneManager (scene_manager.cpp)
├── Хранит tc_scene_handle (числа)
├── Возвращает TcScene через from_handle()
├── File I/O, mode, tick_and_render
└── RenderingManager::instance().render_all()

Python SceneManager (9 строк)
└── Чистый реэкспорт из termin._native.scene

EditorWindow
├── _editor_data: dict[str, dict]
├── _store_editor_data(name, data)
├── _collect_editor_state() -> dict
└── _apply_editor_state(data)
```
