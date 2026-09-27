#pragma once

#include <cctype>
#include <filesystem>
#include <optional>
#include <stdexcept>
#include <string>
#include <vector>

#include <tcbase/trent/trent.h>
#include <termin/entity/entity_classification_registry.hpp>

#include <termin/runtime/runtime_package.hpp>

namespace termin::runtime::detail {

    inline const nos::trent* dict_get(const nos::trent& t, const char* key) {
        return t.is_dict() ? t._get(key) : nullptr;
    }

    inline std::vector<std::string> classification_names(const nos::trent& classification,
                                                          const char* field_name) {
        const nos::trent* field = dict_get(classification, field_name);
        if (!field || !field->is_list() || field->as_list().size() != 64) {
            throw std::runtime_error(
                std::string("entity_classification.") + field_name +
                " must contain exactly 64 string entries");
        }
        std::vector<std::string> names;
        names.reserve(64);
        for (const nos::trent& value : field->as_list()) {
            if (!value.is_string()) {
                throw std::runtime_error(
                    std::string("entity_classification.") + field_name +
                    " must contain exactly 64 string entries");
            }
            names.push_back(value.as_string());
        }
        return names;
    }

    inline void parse_entity_classification(const nos::trent& manifest,
                                            RuntimePackageLoadResult& result) {
        const nos::trent* classification = dict_get(manifest, "entity_classification");
        if (!classification || !classification->is_dict()) {
            throw std::runtime_error("manifest entity_classification must be an object");
        }
        const std::vector<std::string> layer_names =
            classification_names(*classification, "layer_names");
        const std::vector<std::string> flag_names =
            classification_names(*classification, "flag_names");
        EntityClassificationRegistry registry;
        std::string error;
        if (!registry.configure(layer_names, flag_names, &error)) {
            throw std::runtime_error("invalid entity_classification: " + error);
        }
        result.layer_names.assign(registry.layer_names().begin(), registry.layer_names().end());
        result.flag_names.assign(registry.flag_names().begin(), registry.flag_names().end());
    }

    inline std::string lowercase_copy(std::string s) {
        for (char& ch : s) {
            ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
        }
        return s;
    }

    inline void validate_scene_identity(const std::string& identity) {
        if (identity.empty() || identity.front() == '/' || identity.back() == '/' ||
            identity.find('\\') != std::string::npos || identity.find(':') != std::string::npos ||
            !lowercase_copy(identity).ends_with(".scene")) {
            throw std::runtime_error("runtime scene identity must be a project-relative .scene path: " + identity);
        }
        const std::filesystem::path path(identity);
        for (const std::filesystem::path& component : path) {
            if (component == "." || component == "..") {
                throw std::runtime_error("runtime scene identity must not contain dot segments: " + identity);
            }
        }
    }

    inline bool is_trimmed_nonempty(const std::string& value) {
        return !value.empty() &&
               !std::isspace(static_cast<unsigned char>(value.front())) &&
               !std::isspace(static_cast<unsigned char>(value.back()));
    }

    inline std::optional<RuntimePackageWorldControllerSelection>
    parse_world_controller_selection(const nos::trent& manifest) {
        if (!manifest.is_dict()) {
            throw std::runtime_error("runtime package manifest must be an object");
        }
        const nos::trent* value = manifest._get("world_controller");
        if (!value) {
            throw std::runtime_error(
                "runtime package manifest must explicitly define world_controller");
        }
        if (value->is_nil()) {
            return std::nullopt;
        }
        if (!value->is_dict()) {
            throw std::runtime_error("manifest world_controller must be null or an object");
        }
        if (value->as_dict().size() != 2 || !value->_get("module") || !value->_get("type")) {
            throw std::runtime_error(
                "manifest world_controller requires exactly module and type");
        }
        const nos::trent* module = value->_get("module");
        const nos::trent* type = value->_get("type");
        if (!module->is_string() || !type->is_string() ||
            !is_trimmed_nonempty(module->as_string()) ||
            !is_trimmed_nonempty(type->as_string())) {
            throw std::runtime_error(
                "manifest world_controller module and type must be non-empty trimmed strings");
        }
        return RuntimePackageWorldControllerSelection{
            module->as_string(),
            type->as_string(),
        };
    }

} // namespace termin::runtime::detail
