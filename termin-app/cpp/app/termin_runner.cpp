#include <tcbase/trent/json.h>
#include <tcbase/trent/trent.h>

#include <cstdlib>
#include <filesystem>
#include <iostream>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

#ifdef _WIN32
#include <process.h>
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#else
#include <sys/wait.h>
#include <unistd.h>
#endif

namespace {

namespace fs = std::filesystem;

constexpr const char* kDefaultProfilePath = "project_settings/build_profiles.json";

struct RunnerOptions {
    fs::path project_root;
    fs::path profiles_path;
    std::string mode = "build";
    bool build_if_missing = false;
    bool rebuild = false;
    bool dry_run = false;
    std::optional<std::string> backend;
    std::optional<std::string> scene_override;
    std::vector<std::string> player_args;
};

struct ParsedArgs {
    std::string command;
    std::string profile_name;
    RunnerOptions options;
};

struct BuildProfile {
    std::string name;
    std::string target;
    std::string entry_scene;
    std::string output_dir;
};

fs::path executable_dir() {
#ifdef _WIN32
    std::vector<char> buffer(MAX_PATH);
    DWORD size = GetModuleFileNameA(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    while (size == buffer.size()) {
        buffer.resize(buffer.size() * 2);
        size = GetModuleFileNameA(nullptr, buffer.data(), static_cast<DWORD>(buffer.size()));
    }
    if (size == 0) {
        return fs::current_path();
    }
    return fs::path(std::string(buffer.data(), size)).parent_path();
#else
    std::vector<char> buffer(4096);
    ssize_t size = readlink("/proc/self/exe", buffer.data(), buffer.size() - 1);
    if (size <= 0) {
        return fs::current_path();
    }
    buffer[static_cast<size_t>(size)] = '\0';
    return fs::path(buffer.data()).parent_path();
#endif
}

std::string env_path_separator() {
#ifdef _WIN32
    return ";";
#else
    return ":";
#endif
}

std::string current_env(const char* name) {
    const char* value = std::getenv(name);
    return value == nullptr ? std::string() : std::string(value);
}

void set_env_value(const char* name, const std::string& value) {
#ifdef _WIN32
    _putenv_s(name, value.c_str());
#else
    setenv(name, value.c_str(), 1);
#endif
}

void prepend_env_path(const char* name, const fs::path& value) {
    if (value.empty()) {
        return;
    }
    std::string current = current_env(name);
    std::string next = value.string();
    if (!current.empty()) {
        next += env_path_separator();
        next += current;
    }
    set_env_value(name, next);
}

std::vector<fs::path> python_module_paths(const fs::path& install_root, const fs::path& exe_dir) {
    std::vector<fs::path> paths;
    const fs::path lib_dir = install_root / "lib";
    std::error_code ec;
    if (fs::exists(lib_dir, ec)) {
        for (const fs::directory_entry& entry : fs::directory_iterator(lib_dir, ec)) {
            if (ec) {
                break;
            }
            if (!entry.is_directory(ec)) {
                continue;
            }
            const std::string name = entry.path().filename().string();
            if (name.rfind("python3.", 0) == 0) {
                fs::path site_packages = entry.path() / "site-packages";
                if (fs::exists(site_packages, ec)) {
                    paths.push_back(site_packages);
                }
            }
        }
    }

    fs::path sdk_python = install_root / "lib" / "python";
    if (fs::exists(sdk_python, ec)) {
        paths.push_back(sdk_python);
    }

    for (fs::path dir = exe_dir; !dir.empty(); dir = dir.parent_path()) {
        fs::path dev_python = dir / "termin-app";
        if (fs::exists(dev_python / "termin" / "__init__.py", ec)) {
            paths.push_back(dev_python);
            break;
        }
        if (dir == dir.root_path()) {
            break;
        }
    }

    return paths;
}

void configure_python_backend_environment() {
    fs::path exe_dir = executable_dir();
    fs::path install_root = exe_dir.parent_path();

    if (current_env("TERMIN_SDK").empty()) {
        set_env_value("TERMIN_SDK", install_root.string());
    }
    prepend_env_path("PATH", exe_dir);

    std::string pythonpath = current_env("PYTHONPATH");
    for (const fs::path& path : python_module_paths(install_root, exe_dir)) {
        if (!fs::exists(path)) {
            continue;
        }
        if (!pythonpath.empty()) {
            pythonpath = path.string() + env_path_separator() + pythonpath;
        } else {
            pythonpath = path.string();
        }
    }
    if (!pythonpath.empty()) {
        set_env_value("PYTHONPATH", pythonpath);
    }
}

int run_process(const std::vector<std::string>& args) {
    if (args.empty()) {
        throw std::runtime_error("cannot run empty command");
    }

#ifdef _WIN32
    std::vector<const char*> argv;
    argv.reserve(args.size() + 1);
    for (const std::string& arg : args) {
        argv.push_back(arg.c_str());
    }
    argv.push_back(nullptr);
    return _spawnvp(_P_WAIT, args.front().c_str(), argv.data());
#else
    pid_t pid = fork();
    if (pid < 0) {
        throw std::runtime_error("failed to fork runner backend process");
    }
    if (pid == 0) {
        std::vector<char*> argv;
        argv.reserve(args.size() + 1);
        for (const std::string& arg : args) {
            argv.push_back(const_cast<char*>(arg.c_str()));
        }
        argv.push_back(nullptr);
        execvp(args.front().c_str(), argv.data());
        std::perror(args.front().c_str());
        _exit(127);
    }

    int status = 0;
    if (waitpid(pid, &status, 0) < 0) {
        throw std::runtime_error("failed to wait for runner backend process");
    }
    if (WIFEXITED(status)) {
        return WEXITSTATUS(status);
    }
    if (WIFSIGNALED(status)) {
        return 128 + WTERMSIG(status);
    }
    return 1;
#endif
}

void print_help() {
    std::cout
        << "termin_runner - Termin project run profile utility\n"
        << "\n"
        << "Usage:\n"
        << "  termin_runner --help\n"
        << "  termin_runner run <profile> [--project <dir>] [--profiles <file>] [options] [-- player-args...]\n"
        << "\n"
        << "Options:\n"
        << "  --mode build|project      Run built output or source project scene (default: build).\n"
        << "  --build-if-missing        Build the profile if build.json is missing.\n"
        << "  --rebuild                 Build the profile before running.\n"
        << "  --dry-run                 Print the resolved command without executing it.\n"
        << "  --backend <name>          Set TERMIN_BACKEND for the player process.\n"
        << "  --scene <path>            Override profile entry_scene in project mode.\n"
        << "  --width <pixels>          Forward to termin.player.\n"
        << "  --height <pixels>         Forward to termin.player.\n"
        << "  --title <text>            Forward to termin.player.\n";
}

void print_usage_error() {
    std::cerr
        << "Usage: termin_runner run <profile> [options]\n"
        << "Run 'termin_runner --help' for full help.\n";
}

std::string take_value(int argc, char** argv, int& index, const std::string& option) {
    if (index + 1 >= argc) {
        throw std::runtime_error("missing value for " + option);
    }
    return argv[++index];
}

ParsedArgs parse_args(int argc, char** argv) {
    ParsedArgs parsed;
    if (argc >= 2) {
        const std::string first = argv[1];
        if (first == "--help" || first == "-h" || first == "help") {
            parsed.command = "help";
            return parsed;
        }
    }
    if (argc < 2) {
        throw std::runtime_error("missing command");
    }

    parsed.command = argv[1];
    if (parsed.command != "run") {
        throw std::runtime_error("unknown command: " + parsed.command);
    }

    int i = 2;
    if (i >= argc || std::string(argv[i]).rfind("-", 0) == 0) {
        throw std::runtime_error("missing profile name");
    }
    parsed.profile_name = argv[i++];

    for (; i < argc; ++i) {
        std::string arg = argv[i];
        if (arg == "--") {
            for (++i; i < argc; ++i) {
                parsed.options.player_args.emplace_back(argv[i]);
            }
            break;
        }
        if (arg == "--project") {
            parsed.options.project_root = take_value(argc, argv, i, arg);
        } else if (arg == "--profiles") {
            parsed.options.profiles_path = take_value(argc, argv, i, arg);
        } else if (arg == "--mode") {
            parsed.options.mode = take_value(argc, argv, i, arg);
        } else if (arg == "--build-if-missing") {
            parsed.options.build_if_missing = true;
        } else if (arg == "--rebuild") {
            parsed.options.rebuild = true;
        } else if (arg == "--dry-run") {
            parsed.options.dry_run = true;
        } else if (arg == "--backend") {
            parsed.options.backend = take_value(argc, argv, i, arg);
        } else if (arg == "--scene") {
            parsed.options.scene_override = take_value(argc, argv, i, arg);
        } else if (arg == "--width" || arg == "--height" || arg == "--title" ||
                   arg == "-W" || arg == "-H" || arg == "-t") {
            parsed.options.player_args.emplace_back(arg);
            parsed.options.player_args.emplace_back(take_value(argc, argv, i, arg));
        } else {
            throw std::runtime_error("unknown option: " + arg);
        }
    }

    if (parsed.options.mode != "build" && parsed.options.mode != "project") {
        throw std::runtime_error("unsupported run mode: " + parsed.options.mode);
    }
    if (parsed.options.rebuild) {
        parsed.options.build_if_missing = true;
    }
    return parsed;
}

bool has_termin_project_file(const fs::path& dir) {
    std::error_code ec;
    if (!fs::exists(dir, ec) || !fs::is_directory(dir, ec)) {
        return false;
    }
    for (const fs::directory_entry& entry : fs::directory_iterator(dir, ec)) {
        if (ec) {
            return false;
        }
        if (entry.is_regular_file(ec) && entry.path().extension() == ".terminproj") {
            return true;
        }
    }
    return false;
}

fs::path find_project_root(const fs::path& requested) {
    fs::path start = requested.empty() ? fs::current_path() : requested;
    start = fs::absolute(start);
    std::error_code ec;
    start = fs::weakly_canonical(start, ec);
    if (ec) {
        start = fs::absolute(requested.empty() ? fs::current_path() : requested);
    }

    if (fs::is_regular_file(start, ec)) {
        start = start.parent_path();
    }

    for (fs::path dir = start; !dir.empty(); dir = dir.parent_path()) {
        if (has_termin_project_file(dir)) {
            return dir;
        }
        if (dir == dir.root_path()) {
            break;
        }
    }

    throw std::runtime_error("could not find a .terminproj file from: " + start.string());
}

fs::path resolve_profiles_path(const RunnerOptions& options, const fs::path& project_root) {
    if (!options.profiles_path.empty()) {
        fs::path path = options.profiles_path;
        if (!path.is_absolute()) {
            path = fs::current_path() / path;
        }
        return fs::absolute(path);
    }
    return project_root / kDefaultProfilePath;
}

const nos::trent& profile_map(const nos::trent& root) {
    if (!root.is_dict()) {
        throw std::runtime_error("build profiles root must be a JSON object");
    }
    const nos::trent* profiles = root._get("profiles");
    if (profiles == nullptr) {
        throw std::runtime_error("build profiles file must contain a 'profiles' object");
    }
    if (!profiles->is_dict()) {
        throw std::runtime_error("'profiles' must be a JSON object");
    }
    return *profiles;
}

std::string optional_string_field(const nos::trent& object, const char* key) {
    const nos::trent* value = object._get(key);
    if (value == nullptr || value->is_nil()) {
        return "";
    }
    if (!value->is_string()) {
        throw std::runtime_error(std::string("profile field must be a string: ") + key);
    }
    return value->as_string();
}

BuildProfile read_profile(const std::string& name, const nos::trent& value) {
    if (!value.is_dict()) {
        throw std::runtime_error("profile '" + name + "' must be a JSON object");
    }

    BuildProfile profile;
    profile.name = name;
    profile.target = optional_string_field(value, "target");
    profile.entry_scene = optional_string_field(value, "entry_scene");
    profile.output_dir = optional_string_field(value, "output_dir");

    if (profile.target.empty()) {
        throw std::runtime_error("profile '" + name + "' has no target");
    }
    if (profile.entry_scene.empty()) {
        throw std::runtime_error("profile '" + name + "' has no entry_scene");
    }
    if (profile.output_dir.empty()) {
        throw std::runtime_error("profile '" + name + "' has no output_dir");
    }
    return profile;
}

nos::trent load_profiles_file(const fs::path& path) {
    std::error_code ec;
    if (!fs::exists(path, ec)) {
        throw std::runtime_error("build profiles file does not exist: " + path.string());
    }
    return nos::json::parse_file(path.string());
}

BuildProfile find_profile(const nos::trent& profiles, const std::string& name) {
    const nos::trent* value = profiles._get(name);
    if (value == nullptr) {
        throw std::runtime_error("unknown build profile: " + name);
    }
    return read_profile(name, *value);
}

fs::path resolve_output_dir(const fs::path& project_root, const BuildProfile& profile) {
    fs::path output_dir = profile.output_dir;
    if (!output_dir.is_absolute()) {
        output_dir = project_root / output_dir;
    }
    return output_dir;
}

void print_command(const std::vector<std::string>& command) {
    for (std::size_t i = 0; i < command.size(); ++i) {
        if (i != 0) {
            std::cout << ' ';
        }
        std::cout << command[i];
    }
    std::cout << "\n";
}

int maybe_build_profile(
    const ParsedArgs& args,
    const fs::path& project_root,
    const fs::path& profiles_path,
    const fs::path& build_json_path
) {
    const bool build_missing = !fs::exists(build_json_path);
    if (!args.options.rebuild && !build_missing) {
        return 0;
    }

    if (!args.options.build_if_missing) {
        std::cerr
            << "termin_runner: build file does not exist: " << build_json_path << "\n"
            << "Run 'termin build " << args.profile_name
            << " --project " << project_root.string()
            << "' or pass --build-if-missing.\n";
        return 4;
    }

    std::vector<std::string> build_command = {
        "termin_builder",
        "build",
        args.profile_name,
        "--project",
        project_root.string(),
        "--profiles",
        profiles_path.string(),
    };

    if (args.options.dry_run) {
        std::cout << "Build command: ";
        print_command(build_command);
        return 0;
    }

    std::cout << "Executing build profile before run...\n";
    return run_process(build_command);
}

std::vector<std::string> python_module_command() {
    return {
#ifdef _WIN32
        "python",
#else
        "python3",
#endif
        "-m",
        "termin.player",
    };
}

int command_run(const ParsedArgs& args) {
    fs::path project_root = find_project_root(args.options.project_root);
    fs::path profiles_path = resolve_profiles_path(args.options, project_root);
    nos::trent root = load_profiles_file(profiles_path);
    BuildProfile profile = find_profile(profile_map(root), args.profile_name);
    fs::path output_dir = resolve_output_dir(project_root, profile);
    fs::path build_json_path = output_dir / "build.json";

    std::cout
        << "Profile: " << profile.name << "\n"
        << "Project: " << project_root << "\n"
        << "Profiles: " << profiles_path << "\n"
        << "Run mode: " << args.options.mode << "\n"
        << "Target: " << profile.target << "\n"
        << "Entry scene: " << profile.entry_scene << "\n"
        << "Output dir: " << profile.output_dir << "\n";

    if (profile.target != "desktop" && args.options.mode == "build") {
        std::cerr
            << "termin_runner: unsupported build run target '"
            << profile.target << "'.\n";
        return 3;
    }

    configure_python_backend_environment();
    if (args.options.backend.has_value()) {
        set_env_value("TERMIN_BACKEND", *args.options.backend);
    }

    std::vector<std::string> command = python_module_command();
    if (args.options.mode == "build") {
        int build_code = maybe_build_profile(args, project_root, profiles_path, build_json_path);
        if (build_code != 0) {
            return build_code;
        }
        command.emplace_back("--build");
        command.emplace_back(build_json_path.string());
    } else {
        command.emplace_back(project_root.string());
        command.emplace_back("--scene");
        command.emplace_back(args.options.scene_override.value_or(profile.entry_scene));
    }

    command.insert(command.end(), args.options.player_args.begin(), args.options.player_args.end());

    std::cout << "Player command: ";
    print_command(command);
    if (args.options.dry_run) {
        std::cout << "Dry run: player execution skipped.\n";
        return 0;
    }
    return run_process(command);
}

} // namespace

int main(int argc, char** argv) {
    try {
        ParsedArgs args = parse_args(argc, argv);
        if (args.command == "help") {
            print_help();
            return 0;
        }
        if (args.command == "run") {
            return command_run(args);
        }
        throw std::runtime_error("unknown command: " + args.command);
    } catch (const std::exception& exc) {
        std::cerr << "termin_runner: " << exc.what() << "\n";
        print_usage_error();
        return 2;
    }
}
