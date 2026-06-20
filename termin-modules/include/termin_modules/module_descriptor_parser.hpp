#pragma once

#include <optional>
#include <string>

#include "termin_modules/module_types.hpp"
#include "termin_modules/termin_modules_api.hpp"

namespace termin_modules {

class TERMIN_MODULES_API ModuleDescriptorParser {
public:
    std::optional<ModuleSpec> parse(const std::filesystem::path& path, std::string& error) const;
};

} // namespace termin_modules
