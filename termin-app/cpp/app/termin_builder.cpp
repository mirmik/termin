#include <tcbase/trent/json.h>
#include <tcbase/trent/trent.h>

#include <filesystem>
#include <cstdlib>
#include <cstdio>
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

struct GlobalOptions {
    fs::path project_root;
    fs::path profiles_path;
    bool dry_run = false;
};

struct ParsedArgs {
    std::string command;
    std::string profile_name;
    GlobalOptions options;
};

struct BuildProfile {
    std::string name;
    std::string target;
    std::string entry_scene;
    std::string output_dir;
    const nos::trent* raw = nullptr;
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
        throw std::runtime_error("failed to fork build backend process");
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
        throw std::runtime_error("failed to wait for build backend process");
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
        << "termin_builder - Termin project build profile utility\n"
        << "\n"
        << "Usage:\n"
        << "  termin_builder --help\n"
        << "  termin_builder profiles [--project <dir>] [--profiles <file>]\n"
        << "  termin_builder profile <name> [--project <dir>] [--profiles <file>]\n"
        << "  termin_builder build <name> [--project <dir>] [--profiles <file>] [--dry-run]\n"
        << "\n"
        << "Profile file:\n"
        << "  project_settings/build_profiles.json\n"
        << "\n"
        << "Expected schema:\n"
        << "  {\n"
        << "    \"profiles\": {\n"
        << "      \"dev\": {\n"
        << "        \"target\": \"desktop\",\n"
        << "        \"entry_scene\": \"Main.scene\",\n"
        << "        \"output_dir\": \"dist/dev\"\n"
        << "      }\n"
        << "    }\n"
        << "  }\n";
}

void print_usage_error() {
    std::cerr
        << "Usage: termin_builder profiles|profile <name>|build <name> [options]\n"
        << "Run 'termin_builder --help' for full help.\n";
}

bool is_option_with_value(const std::string& arg) {
    return arg == "--project" || arg == "--profiles";
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
    if (parsed.command != "profiles" && parsed.command != "profile" && parsed.command != "build") {
        throw std::runtime_error("unknown command: " + parsed.command);
    }

    int i = 2;
    if (parsed.command == "profile" || parsed.command == "build") {
        if (i >= argc || std::string(argv[i]).rfind("-", 0) == 0) {
            throw std::runtime_error("missing profile name");
        }
        parsed.profile_name = argv[i++];
    }

    for (; i < argc; ++i) {
        std::string arg = argv[i];
        auto take_value = [&]() -> std::string {
            if (i + 1 >= argc) {
                throw std::runtime_error("missing value for " + arg);
            }
            return argv[++i];
        };

        if (arg == "--project") {
            parsed.options.project_root = take_value();
        } else if (arg == "--profiles") {
            parsed.options.profiles_path = take_value();
        } else if (arg == "--dry-run") {
            parsed.options.dry_run = true;
        } else if (is_option_with_value(arg)) {
            (void)take_value();
        } else {
            throw std::runtime_error("unknown option: " + arg);
        }
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

fs::path resolve_profiles_path(const GlobalOptions& options, const fs::path& project_root) {
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
    profile.raw = &value;
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

void list_profiles(const nos::trent& profiles) {
    const auto& dict = profiles.as_dict_except();
    if (dict.empty()) {
        std::cout << "No build profiles defined.\n";
        return;
    }
    for (const auto& item : dict) {
        std::cout << item.first;
        if (item.second.is_dict()) {
            const std::string target = optional_string_field(item.second, "target");
            if (!target.empty()) {
                std::cout << " (" << target << ")";
            }
        }
        std::cout << "\n";
    }
}

BuildProfile find_profile(const nos::trent& profiles, const std::string& name) {
    const nos::trent* value = profiles._get(name);
    if (value == nullptr) {
        throw std::runtime_error("unknown build profile: " + name);
    }
    return read_profile(name, *value);
}

void print_profile_summary(const fs::path& project_root, const fs::path& profiles_path, const BuildProfile& profile) {
    std::cout
        << "Profile: " << profile.name << "\n"
        << "Project: " << project_root << "\n"
        << "Profiles: " << profiles_path << "\n"
        << "Target: " << profile.target << "\n"
        << "Entry scene: " << profile.entry_scene << "\n"
        << "Output dir: " << profile.output_dir << "\n";
}

int command_profiles(const GlobalOptions& options) {
    fs::path project_root = find_project_root(options.project_root);
    fs::path profiles_path = resolve_profiles_path(options, project_root);
    nos::trent root = load_profiles_file(profiles_path);

    std::cout << "Project: " << project_root << "\n";
    std::cout << "Profiles: " << profiles_path << "\n";
    list_profiles(profile_map(root));
    return 0;
}

int command_profile(const ParsedArgs& args) {
    fs::path project_root = find_project_root(args.options.project_root);
    fs::path profiles_path = resolve_profiles_path(args.options, project_root);
    nos::trent root = load_profiles_file(profiles_path);
    BuildProfile profile = find_profile(profile_map(root), args.profile_name);
    print_profile_summary(project_root, profiles_path, profile);
    return 0;
}

int command_build(const ParsedArgs& args) {
    fs::path project_root = find_project_root(args.options.project_root);
    fs::path profiles_path = resolve_profiles_path(args.options, project_root);
    nos::trent root = load_profiles_file(profiles_path);
    BuildProfile profile = find_profile(profile_map(root), args.profile_name);
    print_profile_summary(project_root, profiles_path, profile);

    if (args.options.dry_run) {
        std::cout << "Dry run: build execution skipped.\n";
        return 0;
    }

    if (profile.target != "desktop") {
        std::cerr
            << "termin_builder: unsupported build target '"
            << profile.target << "'.\n";
        return 3;
    }

    fs::path output_dir = profile.output_dir;
    if (!output_dir.is_absolute()) {
        output_dir = project_root / output_dir;
    }

    configure_python_backend_environment();
    std::vector<std::string> command = {
#ifdef _WIN32
        "python",
#else
        "python3",
#endif
        "-m",
        "termin.project_builder.profile_build",
        "desktop",
        "--project-root",
        project_root.string(),
        "--entry-scene",
        profile.entry_scene,
        "--output-dir",
        output_dir.string(),
    };

    std::cout << "Executing desktop build backend...\n" << std::flush;
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
        if (args.command == "profiles") {
            return command_profiles(args.options);
        }
        if (args.command == "profile") {
            return command_profile(args);
        }
        if (args.command == "build") {
            return command_build(args);
        }
        throw std::runtime_error("unknown command: " + args.command);
    } catch (const std::exception& exc) {
        std::cerr << "termin_builder: " << exc.what() << "\n";
        print_usage_error();
        return 2;
    }
}
