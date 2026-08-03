#include <termin/runtime/runtime_package.hpp>

#include <filesystem>
#include <fstream>
#include <algorithm>
#include <cctype>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_set>

#include <tcbase/tc_log.h>
#include <tcbase/trent/json.h>

extern "C" {
#include <core/tc_component.h>
#include <core/tc_scene_extension.h>
}

namespace termin::runtime {

struct RuntimePackageResourceKeepalive {};

namespace {

const nos::trent* dict_get(const nos::trent& value, const char* key) {
    return value.is_dict() ? value._get(key) : nullptr;
}

std::string string_field(
    const nos::trent& value,
    const char* key,
    const std::string& fallback = ""
) {
    const nos::trent* field = dict_get(value, key);
    return field && field->is_string() ? field->as_string() : fallback;
}

double number_field(const nos::trent& value, const char* key, double fallback = 0.0) {
    const nos::trent* field = dict_get(value, key);
    return field && field->is_numer()
        ? static_cast<double>(field->as_numer())
        : fallback;
}

std::string read_text_file(const std::filesystem::path& path) {
    std::ifstream stream(path, std::ios::binary);
    if (!stream) {
        throw std::runtime_error("failed to open file: " + path.string());
    }
    std::ostringstream text;
    text << stream.rdbuf();
    if (!stream.good() && !stream.eof()) {
        throw std::runtime_error("failed to read file: " + path.string());
    }
    return text.str();
}

void validate_relative_path(const std::string& relative) {
    if (relative.empty()) {
        throw std::runtime_error("runtime package path must not be empty");
    }
    if (relative.find('\\') != std::string::npos) {
        throw std::runtime_error(
            "runtime package path must not contain backslashes: " + relative
        );
    }
    const std::filesystem::path path(relative);
    if (path.is_absolute() || path.has_root_name() || path.has_root_directory()) {
        throw std::runtime_error("runtime package path must be relative: " + relative);
    }
    for (const std::filesystem::path& segment : path) {
        if (segment == "." || segment == "..") {
            throw std::runtime_error(
                "runtime package path must not contain dot segments: " + relative
            );
        }
    }
}

std::string lowercase_copy(std::string value) {
    std::transform(value.begin(), value.end(), value.begin(), [](unsigned char ch) {
        return static_cast<char>(std::tolower(ch));
    });
    return value;
}

void validate_scene_identity(const std::string& identity) {
    if (identity.empty() || identity.front() == '/' || identity.back() == '/' ||
            identity.find('\\') != std::string::npos ||
            identity.find(':') != std::string::npos ||
            !lowercase_copy(identity).ends_with(".scene")) {
        throw std::runtime_error(
            "runtime scene identity must be a project-relative .scene path: " + identity
        );
    }
    for (const std::filesystem::path& segment : std::filesystem::path(identity)) {
        if (segment == "." || segment == "..") {
            throw std::runtime_error(
                "runtime scene identity must not contain dot segments: " + identity
            );
        }
    }
}

bool is_contained_path(
    const std::filesystem::path& root,
    const std::filesystem::path& candidate
) {
    auto root_it = root.begin();
    auto candidate_it = candidate.begin();
    for (; root_it != root.end(); ++root_it, ++candidate_it) {
        if (candidate_it == candidate.end() || *root_it != *candidate_it) {
            return false;
        }
    }
    return true;
}

std::filesystem::path package_path(
    const std::filesystem::path& root,
    const std::string& relative
) {
    validate_relative_path(relative);
    std::error_code error;
    const std::filesystem::path candidate =
        std::filesystem::weakly_canonical(root / relative, error);
    if (error) {
        throw std::runtime_error(
            "failed to resolve runtime package path '" + relative + "': " +
            error.message()
        );
    }
    if (!is_contained_path(root, candidate)) {
        throw std::runtime_error("runtime package path escapes bundle root: " + relative);
    }
    return candidate;
}

void validate_entity_types(const nos::trent& entity, const std::string& scene_path) {
    const nos::trent* components = dict_get(entity, "components");
    if (components && components->is_list()) {
        for (const nos::trent& component : components->as_list()) {
            const std::string type = string_field(component, "type");
            if (!type.empty() && !tc_component_registry_has(type.c_str())) {
                throw std::runtime_error(
                    "minimal runtime profile does not register component type '" +
                    type + "' required by packaged scene '" + scene_path + "'"
                );
            }
        }
    }
    const nos::trent* children = dict_get(entity, "children");
    if (children && children->is_list()) {
        for (const nos::trent& child : children->as_list()) {
            validate_entity_types(child, scene_path);
        }
    }
}

TcSceneRef load_scene(
    const std::filesystem::path& root,
    const std::string& relative,
    const RuntimePackageLoadOptions& options
) {
    const std::string source = read_text_file(package_path(root, relative));
    nos::trent data;
    try {
        data = nos::json::parse(source);
    } catch (const std::exception& exception) {
        throw std::runtime_error(
            "failed to parse packaged runtime scene '" + relative + "': " +
            exception.what()
        );
    }
    const nos::trent* extensions = dict_get(data, "extensions");
    if (extensions && extensions->is_dict() && !extensions->as_dict().empty()) {
        throw std::runtime_error(
            "minimal runtime profile does not register scene extensions required by '" +
            relative + "'"
        );
    }
    const nos::trent* entities = dict_get(data, "entities");
    if (entities && entities->is_list()) {
        for (const nos::trent& entity : entities->as_list()) {
            validate_entity_types(entity, relative);
        }
    }

    TcSceneRef scene = TcSceneRef::create("runtime-scene");
    if (!scene.valid()) {
        throw std::runtime_error("failed to create runtime scene");
    }
    try {
        for (tc_scene_ext_type_id type_id : options.scene_extensions) {
            const char* name = tc_scene_ext_type_debug_name(type_id);
            throw std::runtime_error(
                "minimal runtime profile does not register requested scene extension '" +
                std::string(name ? name : "<unregistered>") + "'"
            );
        }
        scene.set_source_path(package_path(root, relative).string());
        scene.load_from_data(data);
    } catch (...) {
        scene.destroy();
        throw;
    }
    return scene;
}

void destroy_loaded_scenes(RuntimePackageLoadResult& result) {
    for (RuntimePackageScene& packaged : result.scenes) {
        if (packaged.scene.valid()) {
            packaged.scene.destroy();
        }
    }
    result.scenes.clear();
    result.scene = {};
}

} // namespace

TcSceneRef RuntimePackageLoadResult::find_scene(const std::string& identity) const {
    for (const RuntimePackageScene& packaged : scenes) {
        if (packaged.identity == identity) {
            return packaged.scene;
        }
    }
    return {};
}

RuntimePackageLoadResult RuntimePackageLoader::load(
    const std::string& root_path,
    const RuntimePackageLoadOptions& options
) {
    RuntimePackageLoadResult result;
    try {
        if (options.bootstrap_profile != bootstrap::RuntimeBootstrapProfile::Minimal) {
            throw std::runtime_error(
                "minimal-only runtime build requires RuntimeBootstrapProfile::Minimal"
            );
        }
        bootstrap::bootstrap_runtime(bootstrap::RuntimeBootstrapProfile::Minimal);

        std::error_code root_error;
        const std::filesystem::path root =
            std::filesystem::canonical(root_path, root_error);
        if (root_error || !std::filesystem::is_directory(root)) {
            throw std::runtime_error(
                "runtime package root is not a directory: " + root_path
            );
        }
        const std::filesystem::path manifest_path = package_path(root, "manifest.json");
        if (!std::filesystem::is_regular_file(manifest_path)) {
            throw std::runtime_error("manifest.json not found in " + root.string());
        }
        const nos::trent manifest = nos::json::parse(read_text_file(manifest_path));
        if (number_field(manifest, "version") != 2.0) {
            throw std::runtime_error("runtime package manifest requires version 2");
        }

        const nos::trent* resources = dict_get(manifest, "resources");
        if (!resources || !resources->is_list()) {
            throw std::runtime_error("manifest resources must be a list");
        }
        if (!resources->as_list().empty()) {
            const std::string type =
                string_field(resources->as_list().front(), "type", "<missing>");
            throw std::runtime_error(
                "minimal runtime profile does not register resource type '" + type + "'"
            );
        }

        result.entry_scene_identity = string_field(manifest, "entry_scene");
        if (result.entry_scene_identity.empty()) {
            throw std::runtime_error("manifest entry_scene identity is missing");
        }
        const nos::trent* scenes = dict_get(manifest, "scenes");
        if (!scenes || !scenes->is_list() || scenes->as_list().empty()) {
            throw std::runtime_error("manifest scenes must be a non-empty list");
        }

        std::unordered_set<std::string> identities;
        std::unordered_set<std::string> paths;
        for (const nos::trent& entry : scenes->as_list()) {
            const std::string identity = string_field(entry, "identity");
            const std::string path = string_field(entry, "path");
            if (identity.empty() || path.empty()) {
                throw std::runtime_error(
                    "runtime scene entries require non-empty identity and path"
                );
            }
            validate_scene_identity(identity);
            if (!identities.insert(identity).second) {
                throw std::runtime_error("duplicate runtime scene identity '" + identity + "'");
            }
            if (!paths.insert(path).second) {
                throw std::runtime_error("duplicate runtime scene path '" + path + "'");
            }
            result.scenes.push_back({identity, path, load_scene(root, path, options)});
        }
        result.scene = result.find_scene(result.entry_scene_identity);
        if (!result.scene.valid()) {
            throw std::runtime_error(
                "entry scene '" + result.entry_scene_identity +
                "' is absent from manifest scenes"
            );
        }
        result.resources = std::make_shared<RuntimePackageResourceKeepalive>();
        result.ok = true;
        result.message = "ok";
        tc_log_info(
            "RuntimePackageLoader(minimal): loaded package '%s' entities=%zu",
            root.string().c_str(),
            result.scene.entity_count()
        );
    } catch (const std::exception& exception) {
        destroy_loaded_scenes(result);
        result.resources.reset();
        result.ok = false;
        result.message = exception.what();
        tc_log_error("RuntimePackageLoader(minimal): %s", result.message.c_str());
    }
    return result;
}

RuntimePackageLoadResult load_runtime_package(
    const std::string& root_path,
    const RuntimePackageLoadOptions& options
) {
    RuntimePackageLoader loader;
    return loader.load(root_path, options);
}

} // namespace termin::runtime
