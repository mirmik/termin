#pragma once

#include <filesystem>
#include <string>

#include <termin/foliage/foliage_data.hpp>

namespace termin {

struct ENTITY_API FoliageFileResult {
public:
    bool ok = false;
    std::string message;
};

ENTITY_API FoliageFileResult load_foliage_file(const std::filesystem::path& path, FoliageData& out);
ENTITY_API FoliageFileResult save_foliage_file(const std::filesystem::path& path, const FoliageData& data);

} // namespace termin

