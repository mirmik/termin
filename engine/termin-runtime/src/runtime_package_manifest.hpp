#pragma once

#include <cctype>
#include <optional>
#include <stdexcept>
#include <string>

#include <tcbase/trent/trent.h>

#include <termin/runtime/runtime_package.hpp>

namespace termin::runtime::detail {

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
