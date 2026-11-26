#include "d3d11_reflection.hpp"

#include "backend_patchers.hpp"
#include "compiler_support.hpp"

#include <tcbase/trent/json.h>
#include <tgfx/resources/tc_shader_abi.h>

#include <algorithm>
#include <iostream>
#include <limits>

namespace termin_shaderc::internal {

    static bool read_array_counts(const std::filesystem::path& path,
                                  std::unordered_map<std::string, uint32_t>& counts) {
        std::string json;
        if (!read_file(path.string(), json)) {
            return false;
        }
        try {
            const nos::trent layout = nos::json::parse(json);
            const nos::trent& parameters = layout["parameters"];
            if (!parameters.is_list()) {
                std::cerr << "termin_shaderc: Slang reflection lacks parameters in " << path << "\n";
                return false;
            }
            for (const nos::trent& parameter : parameters.as_list()) {
                if (!parameter["name"].is_string()) {
                    continue;
                }
                const std::string& name = parameter["name"].as_string();
                const auto* abi = tc_shader_abi_find_resource(name.c_str());
                auto requested = counts.find(abi ? abi->canonical_name : name);
                if (requested == counts.end() || requested->second != 0) {
                    continue;
                }
                const nos::trent* type = &parameter["type"];
                if (!(*type)["kind"].is_string() || (*type)["kind"].as_string() != "array") {
                    continue;
                }
                uint32_t extent = 1;
                do {
                    const nos::trent& size = (*type)["elementCount"];
                    const auto count = size.is_numer() ? size.as_integer() : 0;
                    if (count <= 0 || count > std::numeric_limits<uint32_t>::max() / extent) {
                        std::cerr << "termin_shaderc: invalid D3D11 register array size for '" << name
                                  << "' in " << path << "\n";
                        return false;
                    }
                    extent *= static_cast<uint32_t>(count);
                    type = &(*type)["elementType"];
                } while ((*type)["kind"].is_string() && (*type)["kind"].as_string() == "array");
                requested->second = extent;
            }
        } catch (const std::exception& error) {
            std::cerr << "termin_shaderc: failed to read Slang reflection in " << path << ": " << error.what() << "\n";
            return false;
        }
        return true;
    }

    bool collect_d3d11_program_array_counts(const CompileOptions& options,
                                            const std::vector<std::string>& common_slang_args,
                                            const std::filesystem::path& stage_reflection_path,
                                            const std::string& slangc,
                                            std::unordered_map<std::string, uint32_t>& counts) {
        auto all_resolved = [&]() {
            return std::all_of(counts.begin(), counts.end(), [](const auto& item) { return item.second != 0; });
        };
        if (all_resolved()) {
            return true;
        }
        if (!read_array_counts(stage_reflection_path, counts)) {
            return false;
        }
        for (const std::string& source : options.program_sources) {
            if (all_resolved()) {
                return true;
            }
            std::error_code ec;
            if (std::filesystem::equivalent(source, options.input, ec)) {
                continue;
            }
            const std::string path = options.output + ".program.reflection.json";
            std::vector<std::string> args{slangc, source, "-no-codegen", "-reflection-json", path};
            args.insert(args.end(), common_slang_args.begin(), common_slang_args.end());
            const int rc = run_command(args);
            const bool ok = rc == 0 && read_array_counts(path, counts);
            std::filesystem::remove(path, ec);
            if (ec) {
                std::cerr << "termin_shaderc: failed to remove " << path << ": " << ec.message() << "\n";
                return false;
            }
            if (rc != 0) {
                std::cerr << "termin_shaderc: Slang reflection for " << source << " failed with exit code " << rc << "\n";
            }
            if (!ok) {
                return false;
            }
        }
        for (const auto& [name, count] : counts) {
            if (!count) {
                std::cerr << "termin_shaderc: could not resolve D3D11 register array extent for '" << name << "'\n";
                return false;
            }
        }
        return true;
    }

} // namespace termin_shaderc::internal
