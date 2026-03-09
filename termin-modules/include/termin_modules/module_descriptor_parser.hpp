#pragma once

#include <optional>
#include <string>

#include "termin_modules/module_types.hpp"

namespace termin_modules {

class ModuleDescriptorParser {
public:
    std::optional<ModuleSpec> parse(const std::filesystem::path& path, std::string& error) const;
};

} // namespace termin_modules
