# План миграции SceneManager в C++

## Статус: Этапы 1-5 завершены

### Выполнено:

#### Этап 1: C++ lifecycle методы ✓
- `_paths: map<string, string>` в C++ SceneManager
- `get_scene_path()` / `set_scene_path()`
- `create_scene(name)` - создаёт сцену + регистрирует
- `close_scene(name)` - unregister + destroy
- `close_all_scenes()`
- Python bindings

#### Этап 2: C++ File I/O ✓
- `read_json_file(path)` - читает файл, возвращает строку
- `write_json_file(path, json)` - атомарная запись
- Python bindings
- Python SceneManager использует C++ file I/O

#### Этап 3: C++ callbacks ✓
- `set_on_after_render(callback)`
- `set_on_before_scene_close(callback)`
- `invoke_after_render()` / `invoke_before_scene_close(name)`
- Python bindings с GIL

#### Этап 4: Editor state в EditorWindow ✓
- `_collect_editor_state()` в EditorWindow
- `_apply_editor_state()` в EditorWindow
- EditorWindow использует `_apply_editor_state` напрямую

#### Этап 5: Упрощение Python SceneManager ✓
- Удалён game timer (QTimer, _game_loop_tick, _update_timer_state)
- Упрощён код с 700 до 459 строк
- Делегирование в C++: file I/O, path storage, mode management

## Текущая архитектура

### C++ SceneManager (scene_manager.hpp/cpp):
```cpp
class SceneManager {
public:
    // Scene lifecycle
    tc_scene_handle create_scene(const std::string& name);
    void close_scene(const std::string& name);
    void close_all_scenes();

    // Scene registration
    void register_scene(const std::string& name, tc_scene_handle scene);
    void unregister_scene(const std::string& name);

    // Scene access
    tc_scene_handle get_scene(const std::string& name) const;
    bool has_scene(const std::string& name) const;
    std::vector<std::string> scene_names() const;

    // Paths
    std::string get_scene_path(const std::string& name) const;
    void set_scene_path(const std::string& name, const std::string& path);

    // File I/O
    static std::string read_json_file(const std::string& path);
    static void write_json_file(const std::string& path, const std::string& json);

    // Mode
    tc_scene_mode get_mode(const std::string& name) const;
    void set_mode(const std::string& name, tc_scene_mode mode);
    bool has_play_scenes() const;

    // Update cycle
    virtual bool tick(double dt);
    void before_render();
    void request_render();
    bool consume_render_request();

    // Callbacks
    void set_on_after_render(AfterRenderCallback callback);
    void set_on_before_scene_close(BeforeSceneCloseCallback callback);
    void invoke_after_render();
    void invoke_before_scene_close(const std::string& name);

protected:
    std::unordered_map<std::string, tc_scene_handle> _scenes;
    std::unordered_map<std::string, std::string> _paths;
    bool _render_requested = false;
    AfterRenderCallback _on_after_render;
    BeforeSceneCloseCallback _on_before_scene_close;
};
```

### Python SceneManager (459 строк):
Тонкая обёртка над C++ SceneManager:
- Хранит TcScene объекты для Python доступа (`_scenes: dict[str, Scene]`)
- Хранит editor data временно при загрузке (`_editor_data`)
- Делегирует логику в C++

## Этап 6: tick() интеграция с RenderingManager (TODO)

Для полной миграции tick() в C++ нужно:
1. Вызов RenderingManager.render_all() из C++
2. Вызов _on_after_render callback после рендера
3. Профайлер секции в C++

Это требует доступа к RenderingManager из C++, что создаёт
зависимости между модулями. Оставлено для будущей работы.

## Почему нельзя сделать чистый реэкспорт

Python код использует TcScene объекты (не только handles):
- `scene_manager.get_scene("editor")` возвращает Scene
- Scene используется для entity manipulation, raycast, etc.

C++ SceneManager хранит tc_scene_handle (числа).
Python wrapper хранит TcScene объекты для Python доступа.

Для чистого реэкспорта нужно либо:
1. C++ возвращает TcScene объекты (сложно из-за модульности)
2. Lookup TcScene по handle где-то ещё

Текущая архитектура (тонкая Python обёртка) - оптимальный компромисс.
