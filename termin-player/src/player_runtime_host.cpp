#define PY_SSIZE_T_CLEAN
#include "termin/player/player_runtime_host.hpp"

#include <Python.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cctype>
#include <csignal>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <memory>
#include <optional>
#include <sstream>
#include <stdexcept>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include <tcbase/tc_log.h>
#include <tcbase/trent/json.h>

#include <termin/bootstrap/bootstrap.hpp>
#include <termin/engine/engine_core.hpp>
#include <termin/modules/term_modules_integration.hpp>
#include <termin/platform/offscreen_render_surface.hpp>
#include <termin/platform/sdl_backend_window.hpp>
#include <termin/input/window_input_bridge.hpp>
#include <termin/render/rendering_manager.hpp>
#include <termin/render/tc_display_handle.hpp>
#include <termin/runtime/runtime_package.hpp>
#include <termin/scene/scene_manager.hpp>
#include <termin/tc_scene.hpp>
#include <tgfx2/device_factory.hpp>
#include <tgfx2/graphics_host.hpp>

#include <termin_modules/module_cpp_backend.hpp>
#include <termin_modules/module_python_backend.hpp>

extern "C" {
#include <core/tc_scene.h>
#include <render/tc_render_target.h>
#include <render/tc_viewport_input_manager.h>
#include <render/tc_viewport.h>
}

#ifdef _WIN32
#include <windows.h>
#else
#include <linux/limits.h>
#include <unistd.h>
#endif

namespace fs = std::filesystem;

namespace termin::player {

PlayerRuntimeHost::Impl* g_active_host = nullptr;

namespace {

std::atomic<int> g_requested_shutdown_signal{0};

int exit_code_for_signal(int signum) {
    return 128 + signum;
}

#ifdef _WIN32
BOOL WINAPI player_console_ctrl_handler(DWORD ctrl_type) {
    switch (ctrl_type) {
    case CTRL_C_EVENT:
    case CTRL_BREAK_EVENT:
    case CTRL_CLOSE_EVENT:
    case CTRL_SHUTDOWN_EVENT:
        g_requested_shutdown_signal.store(SIGINT);
        return TRUE;
    default:
        return FALSE;
    }
}
#else
void player_signal_handler(int signum) {
    g_requested_shutdown_signal.store(signum);
}
#endif

void install_player_signal_handlers() {
#ifdef _WIN32
    SetConsoleCtrlHandler(player_console_ctrl_handler, TRUE);
#else
    std::signal(SIGINT, player_signal_handler);
    std::signal(SIGTERM, player_signal_handler);
#endif
}

fs::path get_executable_dir() {
#ifdef _WIN32
    char path[MAX_PATH];
    GetModuleFileNameA(NULL, path, MAX_PATH);
    return fs::path(path).parent_path();
#else
    char path[PATH_MAX];
    ssize_t len = readlink("/proc/self/exe", path, sizeof(path) - 1);
    if (len != -1) {
        path[len] = '\0';
        return fs::path(path).parent_path();
    }
    return fs::current_path();
#endif
}

std::string env_path_separator() {
#ifdef _WIN32
    return ";";
#else
    return ":";
#endif
}

void set_env_value(const char* name, const std::string& value) {
#ifdef _WIN32
    _putenv_s(name, value.c_str());
#else
    setenv(name, value.c_str(), 1);
#endif
}

void set_env_if_missing(const char* name, const fs::path& value) {
    if (std::getenv(name) != nullptr) {
        return;
    }
    set_env_value(name, value.string());
}

void prepend_env_path(const char* name, const fs::path& value) {
    if (value.empty()) {
        return;
    }
    std::string next = value.string();
    const char* current = std::getenv(name);
    if (current != nullptr && current[0] != '\0') {
        next += env_path_separator();
        next += current;
    }
    set_env_value(name, next);
}

void configure_bundle_runtime_paths(const fs::path& bundle_root, const fs::path& exe_dir) {
    prepend_env_path("PATH", exe_dir);
    prepend_env_path("PATH", bundle_root);
    prepend_env_path("PATH", bundle_root / "bin");
    prepend_env_path("PATH", bundle_root / "lib");
}

fs::path resolve_bundle_root(const fs::path& exe_dir) {
    std::error_code ec;
    if (fs::exists(exe_dir / "app.json", ec)) {
        return exe_dir;
    }

    fs::path parent = exe_dir.parent_path();
    if (!parent.empty() && fs::exists(parent / "app.json", ec)) {
        return parent;
    }

    return parent.empty() ? exe_dir : parent;
}

std::string read_text_file(const fs::path& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        throw std::runtime_error("failed to open file: " + path.string());
    }
    std::ostringstream out;
    out << in.rdbuf();
    if (!in.good() && !in.eof()) {
        throw std::runtime_error("failed to read file: " + path.string());
    }
    return out.str();
}

const nos::trent* dict_get(const nos::trent& t, const char* key) {
    if (!t.is_dict()) {
        return nullptr;
    }
    return t._get(key);
}

std::string string_field(const nos::trent& t, const char* key, const std::string& def = "") {
    const nos::trent* value = dict_get(t, key);
    if (!value || !value->is_string()) {
        return def;
    }
    return value->as_string();
}

bool bool_field(const nos::trent& t, const char* key, bool def = false) {
    const nos::trent* value = dict_get(t, key);
    if (!value || !value->is_bool()) {
        return def;
    }
    return value->as_bool();
}

bool vector_contains(const std::vector<std::string>& values, const std::string& value);
std::string canonical_backend_name(const std::string& value);

std::vector<std::string> required_backend_list(
    const nos::trent& owner,
    const char* field,
    const std::string& context
) {
    const nos::trent* values = dict_get(owner, field);
    if (!values || !values->is_list() || values->as_list().empty()) {
        throw std::runtime_error(context + " must be a non-empty list");
    }
    std::vector<std::string> result;
    size_t index = 0;
    for (const nos::trent& item : values->as_list()) {
        if (!item.is_string() || item.as_string().empty()) {
            throw std::runtime_error(
                context + "[" + std::to_string(index) + "] must be a non-empty string"
            );
        }
        const std::string backend = canonical_backend_name(item.as_string());
        const tgfx::BackendType type = tgfx::backend_from_name(backend);
        if (type == tgfx::BackendType::Null) {
            throw std::runtime_error(context + " contains unsupported backend '" + item.as_string() + "'");
        }
        if (vector_contains(result, backend)) {
            throw std::runtime_error(context + " contains duplicate backend '" + backend + "'");
        }
        result.push_back(backend);
        ++index;
    }
    return result;
}

std::vector<std::string> package_runtime_backends(const fs::path& manifest_path) {
    if (!fs::is_regular_file(manifest_path)) {
        throw std::runtime_error("package manifest not found for backend selection: " + manifest_path.string());
    }

    const nos::trent root = nos::json::parse(read_text_file(manifest_path));
    if (!root.is_dict()) {
        throw std::runtime_error("package manifest root is not an object: " + manifest_path.string());
    }
    const nos::trent* requirements = dict_get(root, "target_requirements");
    if (!requirements || !requirements->is_dict()) {
        throw std::runtime_error("package manifest target_requirements must be an object");
    }
    return required_backend_list(
        *requirements,
        "backends",
        "package manifest target_requirements.backends"
    );
}

bool vector_contains(const std::vector<std::string>& values, const std::string& value) {
    return std::find(values.begin(), values.end(), value) != values.end();
}

std::string join_strings(const std::vector<std::string>& values, const char* separator) {
    std::ostringstream stream;
    for (size_t index = 0; index < values.size(); ++index) {
        if (index != 0) {
            stream << separator;
        }
        stream << values[index];
    }
    return stream.str();
}

std::string lowercase(std::string value) {
    for (char& ch : value) {
        ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
    }
    return value;
}

std::string canonical_backend_name(const std::string& value) {
    const std::string lowered = lowercase(value);
    tgfx::BackendType backend = tgfx::backend_from_name(lowered);
    if (backend != tgfx::BackendType::Null || lowered == "null") {
        return tgfx::backend_name(backend);
    }
    return lowered;
}

fs::path relative_to_root(const fs::path& root, const std::string& value) {
    fs::path path(value);
    if (path.is_absolute()) {
        return path;
    }
    return root / path;
}

fs::path find_python_stdlib(const fs::path& bundle_root) {
#ifdef _WIN32
    fs::path lib_dir = bundle_root / "python" / "Lib";
    if (fs::exists(lib_dir / "os.py")) {
        return lib_dir;
    }
    return {};
#else
    fs::path lib_dir = bundle_root / "lib";
    if (!fs::exists(lib_dir)) {
        return {};
    }
    for (const auto& entry : fs::directory_iterator(lib_dir)) {
        if (!entry.is_directory()) {
            continue;
        }
        const std::string name = entry.path().filename().string();
        if (name.rfind("python3.", 0) == 0 && fs::exists(entry.path() / "os.py")) {
            return entry.path();
        }
    }
    return {};
#endif
}

std::string python_string_literal(const fs::path& path) {
    std::string src = path.string();
    std::string out = "'";
    for (char ch : src) {
        if (ch == '\\' || ch == '\'') {
            out.push_back('\\');
        }
        out.push_back(ch);
    }
    out.push_back('\'');
    return out;
}

std::string python_argv_literal(const std::vector<std::string>& args) {
    std::string out = "[";
    for (size_t i = 0; i < args.size(); ++i) {
        if (i > 0) {
            out += ", ";
        }
        out += "'";
        for (char ch : args[i]) {
            if (ch == '\\' || ch == '\'') {
                out.push_back('\\');
            }
            out.push_back(ch);
        }
        out += "'";
    }
    out += "]";
    return out;
}

void set_python_argv(int argc, char** argv) {
    std::vector<wchar_t*> wargv;
    wargv.reserve(static_cast<size_t>(argc));
    for (int i = 0; i < argc; ++i) {
        wargv.push_back(Py_DecodeLocale(argv[i], nullptr));
    }
    PySys_SetArgvEx(argc, wargv.data(), 0);
    for (wchar_t* item : wargv) {
        PyMem_RawFree(item);
    }
}

struct CliOptions {
    fs::path app_manifest_override;
    std::string backend;
    int width = 0;
    int height = 0;
    int exit_after_frames = 0;
    std::optional<bool> fullscreen;
    bool mcp_enabled = false;
    std::vector<std::string> python_argv;
};

int parse_int_arg(const std::string& arg, const char* name) {
    try {
        size_t consumed = 0;
        int value = std::stoi(arg, &consumed);
        if (consumed != arg.size() || value <= 0) {
            throw std::invalid_argument("invalid");
        }
        return value;
    } catch (const std::exception&) {
        throw std::runtime_error(std::string("termin_player: ") + name + " requires a positive integer");
    }
}

CliOptions parse_cli(int argc, char** argv, const fs::path& default_bundle_root) {
    CliOptions options;
    options.python_argv.emplace_back("termin.player");

    for (int i = 1; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--backend") {
            if (i + 1 >= argc) {
                throw std::runtime_error("termin_player: --backend requires a value");
            }
            options.backend = argv[++i];
            continue;
        }
        const std::string backend_prefix = "--backend=";
        if (arg.rfind(backend_prefix, 0) == 0) {
            options.backend = arg.substr(backend_prefix.size());
            continue;
        }
        if (arg == "--width" || arg == "-W") {
            if (i + 1 >= argc) {
                throw std::runtime_error("termin_player: --width requires a value");
            }
            options.width = parse_int_arg(argv[++i], "--width");
            continue;
        }
        if (arg == "--height" || arg == "-H") {
            if (i + 1 >= argc) {
                throw std::runtime_error("termin_player: --height requires a value");
            }
            options.height = parse_int_arg(argv[++i], "--height");
            continue;
        }
        if (arg == "--windowed") {
            options.fullscreen = false;
            continue;
        }
        if (arg == "--fullscreen") {
            options.fullscreen = true;
            continue;
        }
        if (arg == "--mcp") {
            options.mcp_enabled = true;
            continue;
        }
        if (arg == "--exit-after-frames") {
            if (i + 1 >= argc) {
                throw std::runtime_error("termin_player: --exit-after-frames requires a value");
            }
            options.exit_after_frames = parse_int_arg(argv[++i], "--exit-after-frames");
            continue;
        }
        const std::string exit_after_frames_prefix = "--exit-after-frames=";
        if (arg.rfind(exit_after_frames_prefix, 0) == 0) {
            options.exit_after_frames = parse_int_arg(
                arg.substr(exit_after_frames_prefix.size()),
                "--exit-after-frames"
            );
            continue;
        }
        if (arg == "--bundle" || arg == "--app") {
            if (i + 1 >= argc) {
                throw std::runtime_error("termin_player: " + arg + " requires a value");
            }
            options.app_manifest_override = argv[++i];
            continue;
        }
        const std::string bundle_prefix = "--bundle=";
        if (arg.rfind(bundle_prefix, 0) == 0) {
            options.app_manifest_override = arg.substr(bundle_prefix.size());
            continue;
        }
        const std::string app_prefix = "--app=";
        if (arg.rfind(app_prefix, 0) == 0) {
            options.app_manifest_override = arg.substr(app_prefix.size());
            continue;
        }
        options.python_argv.push_back(std::move(arg));
    }

    if (options.app_manifest_override.empty()) {
        options.app_manifest_override = default_bundle_root / "app.json";
    }
    options.python_argv.push_back("--bundle");
    options.python_argv.push_back(options.app_manifest_override.string());
    return options;
}

void apply_smoke_env(CliOptions& options) {
    if (options.exit_after_frames > 0) {
        return;
    }
    const char* value = std::getenv("TERMIN_PLAYER_EXIT_AFTER_FRAMES");
    if (value == nullptr || value[0] == '\0') {
        return;
    }
    options.exit_after_frames = parse_int_arg(value, "TERMIN_PLAYER_EXIT_AFTER_FRAMES");
}

struct PlayerWindowSettings {
    int width = 1280;
    int height = 720;
    bool fullscreen = true;
    bool vsync = true;
};

int positive_window_int_field(
    const nos::trent& t,
    const char* key,
    int def,
    const char* context
) {
    const nos::trent* value = dict_get(t, key);
    if (!value) {
        return def;
    }
    if (!value->is_numer()) {
        tc_log_warn("termin_player: %s.%s must be a positive integer, using %d", context, key, def);
        return def;
    }
    const double numeric = value->as_numer_default(def);
    const int64_t parsed = value->as_integer_default(def);
    if (static_cast<double>(parsed) != numeric || parsed <= 0 || parsed > INT32_MAX) {
        tc_log_warn("termin_player: %s.%s must be a positive integer, using %d", context, key, def);
        return def;
    }
    return static_cast<int>(parsed);
}

bool window_bool_field(
    const nos::trent& t,
    const char* key,
    bool def,
    const char* context
) {
    const nos::trent* value = dict_get(t, key);
    if (!value) {
        return def;
    }
    if (!value->is_bool()) {
        tc_log_warn(
            "termin_player: %s.%s must be a boolean, using %s",
            context,
            key,
            def ? "true" : "false"
        );
        return def;
    }
    return value->as_bool();
}

PlayerWindowSettings player_window_settings_from_manifest(const nos::trent& root) {
    PlayerWindowSettings settings;
    const nos::trent* runtime = dict_get(root, "runtime");
    if (!runtime) {
        return settings;
    }
    if (!runtime->is_dict()) {
        tc_log_warn("termin_player: app manifest runtime field must be an object; using default window settings");
        return settings;
    }
    const nos::trent* window = dict_get(*runtime, "window");
    if (!window) {
        return settings;
    }
    if (!window->is_dict()) {
        tc_log_warn("termin_player: app manifest runtime.window field must be an object; using default window settings");
        return settings;
    }

    settings.width = positive_window_int_field(*window, "width", settings.width, "runtime.window");
    settings.height = positive_window_int_field(*window, "height", settings.height, "runtime.window");
    settings.fullscreen = window_bool_field(*window, "fullscreen", settings.fullscreen, "runtime.window");
    settings.vsync = window_bool_field(*window, "vsync", settings.vsync, "runtime.window");
    return settings;
}

struct AppManifest {
    fs::path bundle_root;
    fs::path app_manifest_path;
    fs::path package_root;
    fs::path package_manifest_path;
    fs::path project_modules_root;
    fs::path project_python_root;
    fs::path module_manifest_path;
    std::vector<std::string> runtime_backends;
    std::string project_name = "Termin Player";
    PlayerWindowSettings window;
    bool modules_enabled = false;
};

AppManifest load_app_manifest(const fs::path& app_manifest_path) {
    if (!fs::is_regular_file(app_manifest_path)) {
        throw std::runtime_error("app manifest not found: " + app_manifest_path.string());
    }

    AppManifest manifest;
    manifest.app_manifest_path = fs::absolute(app_manifest_path).lexically_normal();
    manifest.bundle_root = manifest.app_manifest_path.parent_path();

    const nos::trent root = nos::json::parse(read_text_file(manifest.app_manifest_path));
    if (!root.is_dict()) {
        throw std::runtime_error("app manifest root must be an object: " + manifest.app_manifest_path.string());
    }

    manifest.project_name = string_field(root, "project_name", "Termin Player");
    manifest.window = player_window_settings_from_manifest(root);

    const nos::trent* package = dict_get(root, "package");
    if (!package || !package->is_dict()) {
        throw std::runtime_error("app manifest field 'package' must be an object");
    }
    manifest.package_root = relative_to_root(manifest.bundle_root, string_field(*package, "root", "package"));
    manifest.package_manifest_path = relative_to_root(
        manifest.bundle_root,
        string_field(*package, "manifest", "package/manifest.json")
    );
    const nos::trent* runtime = dict_get(root, "runtime");
    if (!runtime || !runtime->is_dict()) {
        throw std::runtime_error("app manifest field 'runtime' must be an object");
    }
    manifest.runtime_backends = required_backend_list(
        *runtime,
        "backends",
        "app manifest runtime.backends"
    );
    const std::vector<std::string> package_backends = package_runtime_backends(
        manifest.package_manifest_path
    );
    if (manifest.runtime_backends != package_backends) {
        throw std::runtime_error(
            "app manifest runtime.backends does not match package manifest "
            "target_requirements.backends"
        );
    }
    const nos::trent* modules = runtime && runtime->is_dict() ? dict_get(*runtime, "modules") : nullptr;
    if (modules && modules->is_dict()) {
        manifest.modules_enabled = bool_field(*modules, "enabled", false);
        manifest.project_modules_root = relative_to_root(
            manifest.bundle_root,
            string_field(*modules, "root", "package/modules")
        );
        manifest.project_python_root = manifest.project_modules_root / "python";
        manifest.module_manifest_path = relative_to_root(
            manifest.bundle_root,
            string_field(*modules, "manifest", "package/modules/modules.json")
        );
    }
    return manifest;
}

PyObject* native_request_quit(PyObject*, PyObject* args);
PyObject* native_should_quit(PyObject*, PyObject*);
PyObject* native_exit_code(PyObject*, PyObject*);

PyMethodDef native_methods[] = {
    {"request_quit", native_request_quit, METH_VARARGS, "Request player shutdown."},
    {"should_quit", native_should_quit, METH_NOARGS, "Return whether shutdown was requested."},
    {"exit_code", native_exit_code, METH_NOARGS, "Return requested player exit code."},
    {nullptr, nullptr, 0, nullptr},
};

PyModuleDef native_module = {
    PyModuleDef_HEAD_INIT,
    "_termin_player_native",
    "Native bridge for packaged termin_player.",
    -1,
    native_methods,
    nullptr,
    nullptr,
    nullptr,
    nullptr,
};

PyObject* init_native_module() {
    return PyModule_Create(&native_module);
}

void ensure_native_module_registered() {
    static bool registered = false;
    if (registered) {
        return;
    }
    PyImport_AppendInittab("_termin_player_native", init_native_module);
    registered = true;
}

std::string module_event_name(termin_modules::ModuleEventKind kind) {
    switch (kind) {
    case termin_modules::ModuleEventKind::Discovered:
        return "discovered";
    case termin_modules::ModuleEventKind::Loading:
        return "loading";
    case termin_modules::ModuleEventKind::Loaded:
        return "loaded";
    case termin_modules::ModuleEventKind::Unloading:
        return "unloading";
    case termin_modules::ModuleEventKind::Unloaded:
        return "unloaded";
    case termin_modules::ModuleEventKind::Reloading:
        return "reloading";
    case termin_modules::ModuleEventKind::Failed:
        return "failed";
    }
    return "unknown";
}

} // namespace

struct PlayerRuntimeHost::Impl {
    CliOptions cli;
    AppManifest manifest;
    fs::path exe_dir;
    fs::path bundle_root;
    fs::path python_stdlib;
    bool python_initialized = false;
    bool quit_requested = false;
    int exit_code = 0;

    std::unique_ptr<EngineCore> engine;
    std::unique_ptr<WindowedGraphicsSession> graphics_session;
    BackendWindowPtr window;
    std::optional<TcDisplay> display;
    termin::runtime::RuntimePackageLoadResult package;
    TcSceneRef scene;
    std::string scene_name;
    std::vector<std::string> registered_scene_names;
    bool scene_attached = false;
    std::vector<tc_viewport_handle> viewports;
    std::vector<tc_viewport_input_manager*> viewport_input_managers;
    std::vector<std::string> backend_attempts;

    termin_modules::ModuleRuntime modules_runtime;
    TermModulesIntegration modules_integration;
    bool modules_configured = false;
    bool module_live_scene_sync_enabled = false;
    bool modules_loaded = false;

    int run(int argc, char** argv) {
        try {
            exe_dir = get_executable_dir();
            bundle_root = resolve_bundle_root(exe_dir);
            cli = parse_cli(argc, argv, bundle_root);
            apply_smoke_env(cli);
            manifest = load_app_manifest(cli.app_manifest_override);
            bundle_root = manifest.bundle_root;

            configure_backend_attempts();

            set_env_if_missing("TERMIN_SDK", bundle_root);
            configure_bundle_runtime_paths(bundle_root, exe_dir);
            g_requested_shutdown_signal.store(0);

            python_stdlib = find_python_stdlib(bundle_root);
            if (python_stdlib.empty()) {
                throw std::runtime_error("bundled Python stdlib was not found under " + bundle_root.string());
            }

            initialize_python(argc, argv);
            install_player_signal_handlers();
            termin::bootstrap::bootstrap_player();

            engine = std::make_unique<EngineCore>();
            modules_integration.set_scene_manager(engine->scene_manager);
            load_project_modules();
            load_package();
            register_scenes();
            enable_module_live_scene_sync();
            initialize_window_and_rendering();
            install_runtime_facade();
            run_loop();
            shutdown();
            return exit_code;
        } catch (const std::exception& ex) {
            tc_log_error("termin_player: %s", ex.what());
            std::cerr << "termin_player: " << ex.what() << "\n";
            shutdown();
            return 1;
        }
    }

    void request_quit(int requested_exit_code) {
        exit_code = requested_exit_code;
        quit_requested = true;
        if (window) {
            window->set_should_close(true);
        }
        if (engine) {
            engine->stop();
        }
    }

    void configure_backend_attempts() {
        std::string explicit_backend;
        const char* override_source = nullptr;
        if (!cli.backend.empty()) {
            explicit_backend = canonical_backend_name(cli.backend);
            override_source = "--backend";
        } else {
            const char* environment_backend = std::getenv("TERMIN_BACKEND");
            if (environment_backend != nullptr && environment_backend[0] != '\0') {
                explicit_backend = canonical_backend_name(environment_backend);
                override_source = "TERMIN_BACKEND";
            }
        }

        if (override_source != nullptr) {
            if (!vector_contains(manifest.runtime_backends, explicit_backend)) {
                throw std::runtime_error(
                    std::string(override_source) + " selects backend '" + explicit_backend +
                    "', which is not packaged; available backends: " +
                    join_strings(manifest.runtime_backends, ", ")
                );
            }
            backend_attempts = {explicit_backend};
            set_env_value("TERMIN_BACKEND", explicit_backend);
            tc_log_info(
                "termin_player: explicit %s override selects packaged backend '%s' without fallback",
                override_source,
                explicit_backend.c_str()
            );
            return;
        }

        backend_attempts = manifest.runtime_backends;
        set_env_value("TERMIN_BACKEND", backend_attempts.front());
        tc_log_info(
            "termin_player: packaged backend initialization order: %s",
            join_strings(backend_attempts, ", ").c_str()
        );
    }

    bool consume_shutdown_signal() {
        int signum = g_requested_shutdown_signal.exchange(0);
        if (signum == 0) {
            return false;
        }
        tc_log_info("termin_player: shutdown requested by signal %d", signum);
        request_quit(exit_code_for_signal(signum));
        return true;
    }

    void initialize_python(int argc, char** argv) {
        ensure_native_module_registered();

        static std::string python_home_str =
#ifdef _WIN32
            python_stdlib.parent_path().string();
#else
            bundle_root.string();
#endif
        python_home_str =
#ifdef _WIN32
            python_stdlib.parent_path().string();
#else
            bundle_root.string();
#endif
        static std::wstring python_home_wstr;
        python_home_wstr.assign(python_home_str.begin(), python_home_str.end());
        Py_SetPythonHome(python_home_wstr.c_str());
        Py_NoSiteFlag = 0;
        Py_IgnoreEnvironmentFlag = 1;

        Py_Initialize();
        if (!Py_IsInitialized()) {
            throw std::runtime_error("failed to initialize Python");
        }
        python_initialized = true;
        set_python_argv(argc, argv);

        fs::path site_packages = python_stdlib / "site-packages";
        fs::path project_python = manifest.project_python_root;
        std::string code =
            "import sys\n"
            "site_packages = " + python_string_literal(site_packages) + "\n"
            "project_python = " + python_string_literal(project_python) + "\n"
            "for p in (site_packages, project_python):\n"
            "    if p and p not in sys.path:\n"
            "        sys.path.insert(0, p)\n"
            "sys.argv = " + python_argv_literal(cli.python_argv) + "\n";

        if (PyRun_SimpleString(code.c_str()) != 0) {
            PyErr_Print();
            throw std::runtime_error("failed to configure Python sys.path");
        }
    }

    void install_runtime_facade() {
        if (!python_initialized) {
            return;
        }

        std::string code =
            "import _termin_player_native\n"
            "try:\n"
            "    import termin.player.runtime as _termin_player_runtime\n"
            "    class _NativePlayerRuntime:\n"
            "        display = None\n"
            "        viewport = None\n"
            "        scene = None\n"
            "        @property\n"
            "        def exit_code(self):\n"
            "            return _termin_player_native.exit_code()\n"
            "        def request_quit(self, exit_code=0):\n"
            "            _termin_player_native.request_quit(int(exit_code))\n"
            "    _termin_player_runtime._active_runtime = _NativePlayerRuntime()\n"
            "except Exception:\n"
            "    import traceback\n"
            "    traceback.print_exc()\n";
        PyGILState_STATE gil = PyGILState_Ensure();
        if (PyRun_SimpleString(code.c_str()) != 0) {
            PyErr_Print();
            tc_log_error("termin_player: failed to install Python runtime facade");
        }
        PyGILState_Release(gil);
    }

    void clear_runtime_facade() {
        if (!python_initialized) {
            return;
        }
        PyGILState_STATE gil = PyGILState_Ensure();
        if (PyRun_SimpleString(
                "try:\n"
                "    import termin.player.runtime as _termin_player_runtime\n"
                "    _termin_player_runtime._active_runtime = None\n"
                "except Exception:\n"
                "    pass\n"
            ) != 0) {
            PyErr_Clear();
        }
        PyGILState_Release(gil);
    }

    void load_package() {
        termin::runtime::RuntimePackageLoader loader;
        package = loader.load(manifest.package_root.string());
        if (!package.ok) {
            throw std::runtime_error("failed to load runtime package: " + package.message);
        }
        engine->rendering_manager.render_engine()->configure_shader_artifacts(
            package.shader_runtime.artifact_root,
            package.shader_runtime.cache_root,
            package.shader_runtime.compiler_path,
            package.shader_runtime.dev_compile_enabled
        );
        scene = package.scene;
        if (!scene.valid()) {
            throw std::runtime_error("runtime package returned invalid scene");
        }
        scene_name = package.entry_scene_identity;
    }

    termin_modules::ModuleEnvironment make_module_environment(bool sync_live_scenes) const {
        termin_modules::ModuleEnvironment environment;
        environment.sdk_prefix = bundle_root;
        environment.cmake_prefix_path = bundle_root;
        environment.lib_dir = bundle_root / "lib";
        environment.project_root = manifest.project_modules_root;
        environment.project_venv_path = fs::path();
        environment.python_executable = "";
        environment.use_project_venv = false;
        environment.allow_python_package_install = false;
        environment.sync_live_scenes = sync_live_scenes;
        return environment;
    }

    void configure_modules_runtime(bool sync_live_scenes) {
        if (modules_configured && module_live_scene_sync_enabled == sync_live_scenes) {
            return;
        }

        termin_modules::ModuleEnvironment environment = make_module_environment(sync_live_scenes);
        modules_integration.set_environment(environment);
        modules_runtime.set_environment(environment);
        modules_integration.configure_runtime(modules_runtime);

        if (!modules_configured) {
            modules_runtime.register_backend(std::make_shared<termin_modules::CppModuleBackend>());
            modules_runtime.register_backend(std::make_shared<termin_modules::PythonModuleBackend>());
            modules_runtime.set_event_callback([](const termin_modules::ModuleEvent& event) {
                if (event.kind == termin_modules::ModuleEventKind::Failed) {
                    tc_log_error(
                        "termin_player: module %s failed: %s",
                        event.module_id.c_str(),
                        event.message.c_str()
                    );
                    return;
                }
                tc_log_info(
                    "termin_player: module %s %s",
                    event.module_id.c_str(),
                    module_event_name(event.kind).c_str()
                );
            });
            modules_runtime.set_build_output_callback([](const std::string& module_id, const std::string& line) {
                tc_log_info("termin_player: [%s] %s", module_id.c_str(), line.c_str());
            });
        }

        modules_configured = true;
        module_live_scene_sync_enabled = sync_live_scenes;
    }

    void load_project_modules() {
        if (!manifest.modules_enabled) {
            return;
        }
        if (!fs::is_directory(manifest.project_modules_root)) {
            tc_log_error(
                "termin_player: project modules enabled but directory is missing: %s",
                manifest.project_modules_root.string().c_str()
            );
            return;
        }
        if (!fs::is_regular_file(manifest.module_manifest_path)) {
            tc_log_error(
                "termin_player: project module manifest is missing: %s",
                manifest.module_manifest_path.string().c_str()
            );
            return;
        }

        configure_modules_runtime(false);
        modules_runtime.discover(manifest.project_modules_root);
        if (!modules_runtime.last_error().empty()) {
            tc_log_error("termin_player: module discovery failed: %s", modules_runtime.last_error().c_str());
        }

        modules_loaded = modules_runtime.load_all();
        if (!modules_loaded && !modules_runtime.last_error().empty()) {
            tc_log_error("termin_player: module load failed: %s", modules_runtime.last_error().c_str());
        }
    }

    void enable_module_live_scene_sync() {
        if (modules_configured) {
            configure_modules_runtime(true);
        }
    }

    void unload_project_modules() {
        if (!modules_configured) {
            return;
        }
        std::vector<std::string> loaded_ids;
        for (const termin_modules::ModuleRecord* record : modules_runtime.list()) {
            if (record && record->state == termin_modules::ModuleState::Loaded) {
                loaded_ids.push_back(record->spec.id);
            }
        }
        std::reverse(loaded_ids.begin(), loaded_ids.end());
        for (const std::string& module_id : loaded_ids) {
            if (!modules_runtime.unload_module(module_id)) {
                tc_log_error(
                    "termin_player: failed to unload module '%s': %s",
                    module_id.c_str(),
                    modules_runtime.last_error().c_str()
                );
            }
        }
        modules_loaded = false;
    }

    void register_scenes() {
        SceneManager* manager = &engine->scene_manager;
        for (const termin::runtime::RuntimePackageScene& packaged_scene : package.scenes) {
            manager->register_scene(packaged_scene.identity, packaged_scene.scene.handle());
            manager->set_scene_path(packaged_scene.identity, packaged_scene.scene.source_path());
            manager->set_mode(packaged_scene.identity, TC_SCENE_MODE_INACTIVE);
            registered_scene_names.push_back(packaged_scene.identity);
        }
        manager->set_mode(scene_name, TC_SCENE_MODE_PLAY);
    }

    tc_display_handle display_factory(const std::string& requested_name) {
        if (!display || !display->is_valid()) {
            tc_log_error("termin_player: display requested before display initialization");
            return TC_DISPLAY_HANDLE_INVALID;
        }
        display->set_name(requested_name.empty() ? "Main" : requested_name);
        return display->handle();
    }

    void initialize_window_and_rendering() {
        const int window_width = cli.width > 0 ? cli.width : manifest.window.width;
        const int window_height = cli.height > 0 ? cli.height : manifest.window.height;
        const bool fullscreen = cli.fullscreen.value_or(manifest.window.fullscreen);
        const tgfx::PresentationMode presentation_mode = manifest.window.vsync
            ? tgfx::PresentationMode::VSync
            : tgfx::PresentationMode::Immediate;

        for (const std::string& backend : backend_attempts) {
            if (!tgfx::backend_is_compiled(tgfx::backend_from_name(backend))) {
                tc_log_error(
                    "termin_player: packaged backend '%s' is not compiled into this player",
                    backend.c_str()
                );
                continue;
            }
            set_env_value("TERMIN_BACKEND", backend);
            tc_log_info("termin_player: initializing packaged backend '%s'", backend.c_str());
            try {
                std::unique_ptr<WindowedGraphicsSession> candidate_session =
                    create_native_windowed_graphics();
                BackendWindowPtr candidate_window = candidate_session->create_window(WindowConfig{
                    manifest.project_name,
                    window_width,
                    window_height,
                    presentation_mode,
                });
                graphics_session = std::move(candidate_session);
                window = std::move(candidate_window);
                tc_log_info("termin_player: initialized packaged backend '%s'", backend.c_str());
                break;
            } catch (const std::exception& error) {
                tc_log_error(
                    "termin_player: backend '%s' initialization failed: %s",
                    backend.c_str(),
                    error.what()
                );
            }
        }
        if (!graphics_session || !window) {
            throw std::runtime_error(
                "failed to initialize any requested packaged backend with presentation mode '" +
                std::string(manifest.window.vsync ? "vsync" : "immediate") + "'"
            );
        }
        engine->rendering_manager.render_engine()->set_graphics_host(
            graphics_session->graphics());
        if (fullscreen) {
            window->set_fullscreen(true);
        }

        auto [width, height] = window->framebuffer_size();
        if (width <= 0 || height <= 0) {
            width = window_width;
            height = window_height;
        }
        tc_display_handle handle = create_offscreen_display(
            &graphics_session->graphics().device(), width, height, "Main");
        if (!tc_display_handle_valid(handle)) {
            throw std::runtime_error("failed to create offscreen display");
        }
        display.emplace(handle);

        RenderingManager& manager = engine->rendering_manager;
        manager.set_display_factory([this](const std::string& name) {
            return display_factory(name);
        });
        manager.set_pipeline_factory(nullptr);

        viewports = manager.attach_scene_full(scene.handle());
        if (viewports.empty()) {
            throw std::runtime_error("scene has no attachable viewport config");
        }
        disable_unrenderable_unused_render_targets(manager);
        scene_attached = true;
        tc_log_info("termin_player: attached scene rendering: %zu viewport(s)", viewports.size());
        setup_input(manager);
    }

    void setup_input(RenderingManager& manager) {
        if (!display || !display->is_valid()) {
            tc_log_error("termin_player: cannot set up input without display");
            return;
        }

        tc_input_manager* router = manager.display_input_endpoint(display->handle());
        if (router == nullptr) {
            tc_log_error("termin_player: failed to create display input router");
            return;
        }

        if (window) {
            attach_window_input_display(*window, display->handle());
        }

        int active_viewports = 0;
        for (tc_viewport_handle viewport : viewports) {
            if (!tc_viewport_handle_valid(viewport)) {
                continue;
            }

            const char* raw_mode = tc_viewport_get_input_mode(viewport);
            std::string mode = raw_mode && raw_mode[0] != '\0' ? raw_mode : "simple";
            if (mode == "none" || mode == "editor") {
                continue;
            }
            const char* viewport_name = tc_viewport_get_name(viewport);
            if (mode != "simple" && mode != "basic") {
                tc_log_warn(
                    "termin_player: unknown viewport input mode '%s' for viewport '%s'",
                    mode.c_str(),
                    viewport_name ? viewport_name : ""
                );
                continue;
            }

            if (tc_viewport_get_input_manager(viewport) != nullptr) {
                ++active_viewports;
                continue;
            }

            tc_viewport_input_manager* input = tc_viewport_input_manager_new(viewport);
            if (input == nullptr) {
                tc_log_error(
                    "termin_player: failed to create input manager for viewport '%s'",
                    viewport_name ? viewport_name : ""
                );
                continue;
            }
            viewport_input_managers.push_back(input);
            ++active_viewports;
        }

        tc_log_info("termin_player: input configured for %d viewport(s)", active_viewports);
    }

    void clear_input() {
        if (window) {
            attach_window_input_display(*window, TC_DISPLAY_HANDLE_INVALID);
        }
        for (tc_viewport_input_manager* input : viewport_input_managers) {
            tc_viewport_input_manager_free(input);
        }
        viewport_input_managers.clear();
    }

    void disable_unrenderable_unused_render_targets(RenderingManager& manager) {
        std::vector<tc_render_target_handle> viewport_targets;
        viewport_targets.reserve(viewports.size());
        for (tc_viewport_handle viewport : viewports) {
            tc_render_target_handle rt = tc_viewport_get_render_target(viewport);
            if (tc_render_target_handle_valid(rt)) {
                viewport_targets.push_back(rt);
            }
        }

        for (tc_render_target_handle rt : manager.managed_render_targets()) {
            if (!tc_render_target_handle_valid(rt)) {
                continue;
            }
            bool used_by_viewport = std::any_of(
                viewport_targets.begin(),
                viewport_targets.end(),
                [rt](tc_render_target_handle candidate) {
                    return tc_render_target_handle_eq(candidate, rt);
                }
            );
            if (used_by_viewport) {
                continue;
            }
            if (tc_render_target_get_camera(rt) != nullptr &&
                tc_pipeline_handle_valid(tc_render_target_get_pipeline(rt))) {
                continue;
            }
            tc_render_target_set_enabled(rt, false);
            const char* name = tc_render_target_get_name(rt);
            tc_log_warn(
                "termin_player: disabled unused render target '%s' because it has no camera or pipeline",
                name ? name : ""
            );
        }
    }

    void sync_surface_size() {
        if (!window || !display) {
            return;
        }
        auto [width, height] = window->framebuffer_size();
        if (width <= 0 || height <= 0) {
            return;
        }
        auto [current_width, current_height] = display->get_size();
        if (width == current_width && height == current_height) {
            return;
        }
        if (!display->resize(width, height)) {
            tc_log_error("termin_player: display surface resize failed");
        }
    }

    void run_loop() {
        g_active_host = this;
        auto loop_connection = engine->attach_loop_client(EngineLoopClient{
            .poll_events = [this]() {
                consume_shutdown_signal();
                if (window) {
                    window->poll_events();
                }
                sync_surface_size();
            },
            .should_continue = [this]() {
                consume_shutdown_signal();
                return !quit_requested && window && !window->should_close();
            },
            .on_shutdown = []() {},
        });
        engine->scene_manager.request_render();

        int presented_frames = 0;
        engine->scene_manager.set_on_after_render([this, &presented_frames]() {
            render_present();
            if (cli.exit_after_frames > 0) {
                // Test harness hook: let packaged runtime prove that rendering
                // and shutdown work without relying on an external SIGTERM.
                ++presented_frames;
                if (presented_frames >= cli.exit_after_frames) {
                    request_quit(0);
                }
            }
        });

        tc_log_info("termin_player: starting native C++ runtime host");
        engine->run();
        render_present();
        loop_connection.detach();
        g_active_host = nullptr;
    }

    void render_present() {
        if (!window || !display || !display->is_valid()) {
            return;
        }
        window->present(tgfx::TextureHandle{display->color_texture_id()});
    }

    void shutdown() {
        g_active_host = nullptr;
        clear_runtime_facade();
        unload_project_modules();

        RenderingManager* manager = engine ? &engine->rendering_manager : nullptr;
        if (manager != nullptr) {
            clear_input();
            manager->set_display_factory(nullptr);
            if (scene_attached && scene.valid()) {
                manager->detach_scene_full(scene.handle());
                scene_attached = false;
            }
            if (display && display->is_valid()) {
                manager->remove_display(display->handle());
            }
        }

        if (display && display->is_valid()) {
            display->destroy();
        }
        display.reset();

        if (engine) {
            for (const std::string& registered_name : registered_scene_names) {
                engine->scene_manager.unregister_scene(registered_name);
            }
        }
        registered_scene_names.clear();
        scene = TcSceneRef();
        for (termin::runtime::RuntimePackageScene& packaged_scene : package.scenes) {
            if (packaged_scene.scene.valid()) {
                packaged_scene.scene.destroy();
            }
        }
        package = termin::runtime::RuntimePackageLoadResult();

        if (engine) {
            engine->scene_manager.set_on_after_render(nullptr);
            engine.reset();
        }

        if (window) {
            window->close();
            window.reset();
        }
        if (graphics_session) {
            graphics_session->close();
            graphics_session.reset();
        }

        termin::bootstrap::shutdown_runtime();

        // Deliberately do not call Py_FinalizeEx() here. The editor follows the
        // same rule: native destructors and callbacks can still touch Python, and
        // finalization was the old player shutdown crash boundary.
        python_initialized = Py_IsInitialized();
    }
};

namespace {

PyObject* native_request_quit(PyObject*, PyObject* args) {
    int exit_code = 0;
    if (!PyArg_ParseTuple(args, "|i", &exit_code)) {
        return nullptr;
    }
    if (g_active_host != nullptr) {
        g_active_host->request_quit(exit_code);
    }
    Py_RETURN_NONE;
}

PyObject* native_should_quit(PyObject*, PyObject*) {
    if (g_active_host == nullptr) {
        Py_RETURN_FALSE;
    }
    if (g_active_host->quit_requested) {
        Py_RETURN_TRUE;
    }
    Py_RETURN_FALSE;
}

PyObject* native_exit_code(PyObject*, PyObject*) {
    int exit_code = g_active_host == nullptr ? 0 : g_active_host->exit_code;
    return PyLong_FromLong(exit_code);
}

} // namespace

PlayerRuntimeHost::PlayerRuntimeHost()
    : impl_(new Impl()) {}

PlayerRuntimeHost::~PlayerRuntimeHost() {
    if (impl_ != nullptr) {
        impl_->shutdown();
        delete impl_;
        impl_ = nullptr;
    }
}

int PlayerRuntimeHost::run(int argc, char** argv) {
    return impl_->run(argc, argv);
}

void PlayerRuntimeHost::request_quit(int exit_code) {
    impl_->request_quit(exit_code);
}

} // namespace termin::player
