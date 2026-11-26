#pragma once

#include "cli.hpp"

#include <cstdint>
#include <filesystem>
#include <string>
#include <unordered_map>
#include <vector>

namespace termin_shaderc::internal {

    // Zero counts are array extents that the declaring stage must resolve.
    bool collect_d3d11_program_array_counts(const CompileOptions& options,
                                            const std::vector<std::string>& common_slang_args,
                                            const std::filesystem::path& stage_reflection_path,
                                            const std::string& slangc,
                                            std::unordered_map<std::string, uint32_t>& counts);

} // namespace termin_shaderc::internal
