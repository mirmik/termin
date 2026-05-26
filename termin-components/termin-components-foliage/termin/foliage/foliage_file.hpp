#pragma once

#include <filesystem>
#include <string>

#include <termin/foliage/foliage_data.hpp>

namespace termin {

struct FoliageFileResult {
public:
    bool ok = false;
    std::string message;
};

FoliageFileResult load_foliage_file(const std::filesystem::path& path, FoliageData& out);
FoliageFileResult save_foliage_file(const std::filesystem::path& path, const FoliageData& data);

} // namespace termin

