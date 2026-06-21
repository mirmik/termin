#pragma once

#include "termin_modules/termin_modules_api.hpp"

#include <string>

namespace termin_modules {

TERMIN_MODULES_API bool is_valid_utf8(const std::string& text);
TERMIN_MODULES_API std::string sanitize_external_text(const std::string& text);

} // namespace termin_modules
