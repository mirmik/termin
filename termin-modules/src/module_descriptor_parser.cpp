#include "termin_modules/module_descriptor_parser.hpp"

#include <tcbase/tc_trent.hpp>
#include <tcbase/tc_trent_json.hpp>
#include <tcbase/tc_trent_yaml.hpp>

#include <fstream>
#include <iterator>

namespace termin_modules {
namespace {

std::string read_text_file(const std::filesystem::path& path, std::string& error) {
    std::ifstream file(path);
    if (!file.is_open()) {
        error = "Cannot open descriptor: " + path.string();
        return {};
    }

    return std::string(std::istreambuf_iterator<char>(file), std::istreambuf_iterator<char>());
}

std::optional<std::string> get_optional_string(tc::trent_view node, const char* key) {
    if (!node.is_dict() || !node.contains(key) || !node[key].is_string()) {
        return std::nullopt;
    }

    return node[key].as_string();
}

std::string current_platform_key() {
#ifdef _WIN32
    return "windows";
#elif defined(__linux__)
    return "linux";
#else
    return "";
#endif
}

std::string resolve_template_vars(std::string value, const std::string& module_id) {
    const std::string name_placeholder = "${name}";
    size_t pos = value.find(name_placeholder);
    while (pos != std::string::npos) {
        value.replace(pos, name_placeholder.size(), module_id);
        pos = value.find(name_placeholder, pos + module_id.size());
    }

    return value;
}

std::optional<std::string> get_platform_string(
    tc::trent_view node,
    const char* key,
    const std::string& module_id,
    std::string& error
) {
    error.clear();

    if (!node.is_dict() || !node.contains(key)) {
        return std::nullopt;
    }

    tc::trent_view value_node = node[key];
    if (value_node.is_string()) {
        return resolve_template_vars(value_node.as_string(), module_id);
    }

    if (!value_node.is_dict()) {
        error = std::string("Field '") + key + "' must be a string or an object";
        return std::nullopt;
    }

    const std::string platform = current_platform_key();
    if (platform.empty()) {
        error = std::string("Current platform is not supported for field '") + key + "'";
        return std::nullopt;
    }

    if (!value_node.contains(platform) || !value_node[platform].is_string()) {
        error = std::string("Field '") + key + "." + platform + "' must be a string";
        return std::nullopt;
    }

    return resolve_template_vars(value_node[platform].as_string(), module_id);
}

std::vector<std::string> get_optional_string_list(tc::trent_view node, const char* key, std::string& error) {
    std::vector<std::string> result;
    if (!node.is_dict() || !node.contains(key)) {
        return result;
    }

    tc::trent_view list_node = node[key];
    if (!list_node.is_list()) {
        error = std::string("Field '") + key + "' must be a list";
        return {};
    }

    for (tc::trent_view item : list_node.as_list()) {
        if (!item.is_string()) {
            error = std::string("Field '") + key + "' must contain only strings";
            return {};
        }
        result.push_back(item.as_string());
    }

    return result;
}

bool get_optional_bool(tc::trent_view node, const char* key, bool def) {
    if (!node.is_dict() || !node.contains(key)) {
        return def;
    }

    tc::trent_view value = node[key];
    return value.is_bool() ? value.as_bool() : def;
}

std::optional<ModuleKind> parse_kind(tc::trent_view root, const std::filesystem::path& path, std::string& error) {
    const auto type_value = get_optional_string(root, "type");
    if (!type_value.has_value()) {
        if (path.extension() == ".module") {
            return ModuleKind::Cpp;
        }
        if (path.extension() == ".pymodule") {
            return ModuleKind::Python;
        }
        error = "Missing 'type' and cannot infer from extension: " + path.string();
        return std::nullopt;
    }

    if (*type_value == "cpp") {
        return ModuleKind::Cpp;
    }
    if (*type_value == "python") {
        return ModuleKind::Python;
    }

    error = "Unsupported module type '" + *type_value + "' in " + path.string();
    return std::nullopt;
}

} // namespace

std::optional<ModuleSpec> ModuleDescriptorParser::parse(const std::filesystem::path& path, std::string& error) const {
    error.clear();

    const std::string text = read_text_file(path, error);
    if (!error.empty()) {
        return std::nullopt;
    }

    tc::trent root;
    try {
        const size_t first_content = text.find_first_not_of(" \t\r\n");
        const bool is_json = first_content != std::string::npos &&
            (text[first_content] == '{' || text[first_content] == '[');
        root = is_json ? tc::json::parse(text) : tc::yaml::parse(text);
    } catch (const std::exception& e) {
        error = "Failed to parse descriptor " + path.string() + ": " + e.what();
        return std::nullopt;
    }

    if (!root.is_dict()) {
        error = "Descriptor root must be an object: " + path.string();
        return std::nullopt;
    }

    ModuleSpec spec;
    spec.descriptor_path = path;
    spec.id = get_optional_string(root, "name").value_or(path.stem().string());
    spec.dependencies = get_optional_string_list(root, "dependencies", error);
    if (!error.empty()) {
        error += " in " + path.string();
        return std::nullopt;
    }
    if (root.contains("components")) {
        error = "Field 'components' is no longer supported in module descriptors; "
                "component ownership is inferred from runtime registrations in " + path.string();
        return std::nullopt;
    }

    const auto kind = parse_kind(root, path, error);
    if (!kind.has_value()) {
        return std::nullopt;
    }

    spec.kind = *kind;

    if (spec.kind == ModuleKind::Cpp) {
        if (!root.contains("build") || !root["build"].is_dict()) {
            error = "Missing required object 'build' in " + path.string();
            return std::nullopt;
        }

        tc::trent_view build = root["build"];
        auto config = std::make_shared<CppModuleConfig>();
        const auto build_command = get_platform_string(build, "command", spec.id, error);
        if (!error.empty()) {
            error += " in " + path.string();
            return std::nullopt;
        }
        config->build_command = build_command.value_or("");

        const auto clean_command = get_platform_string(build, "clean_command", spec.id, error);
        if (!error.empty()) {
            error += " in " + path.string();
            return std::nullopt;
        }
        config->clean_command = clean_command.value_or("");

        const auto output = get_platform_string(build, "output", spec.id, error);
        if (!error.empty()) {
            error += " in " + path.string();
            return std::nullopt;
        }
        if (!output.has_value() || output->empty()) {
            error = "Missing required string 'build.output' in " + path.string();
            return std::nullopt;
        }

        config->artifact_path = std::filesystem::path(*output);
        if (config->artifact_path.is_relative()) {
            config->artifact_path = path.parent_path() / config->artifact_path;
        }
        config->ignored = get_optional_bool(root, "ignore", false);
        spec.config = config;
        return spec;
    }

    auto config = std::make_shared<PythonModuleConfig>();
    config->root = std::filesystem::path(get_optional_string(root, "root").value_or("."));
    if (config->root.is_relative()) {
        config->root = path.parent_path() / config->root;
    }
    config->packages = get_optional_string_list(root, "packages", error);
    if (!error.empty()) {
        error += " in " + path.string();
        return std::nullopt;
    }
    config->requirements = get_optional_string_list(root, "requirements", error);
    if (!error.empty()) {
        error += " in " + path.string();
        return std::nullopt;
    }
    config->ignored = get_optional_bool(root, "ignore", false);
    spec.config = config;
    return spec;
}

} // namespace termin_modules
