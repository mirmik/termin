#include "web_graphics_assets.hpp"

#include <stdexcept>
#include <utility>

#include <tcbase/tc_log.h>
#include <termin/bootstrap/bootstrap.hpp>
#include <termin/runtime/runtime_package.hpp>
#include <tgfx2/builtin_shader_sources.hpp>
#include <tgfx2/graphics_host.hpp>

namespace termin::web {
    namespace {
        runtime::RuntimePackageBytes read_shader_file(const runtime::RuntimePackageReader& reader,
                                                      std::string_view path) {
            try {
                if (reader.contains(path))
                    return reader.read(path);
            } catch (const std::exception& e) {
                tc_log_error("Termin Web: failed to read shader '%.*s': %s",
                             static_cast<int>(path.size()),
                             path.data(),
                             e.what());
            }
            return {};
        }
    } // namespace

    ShaderArtifactResolver::ReadCallback
    bind_package_shader_sources(std::shared_ptr<runtime::RuntimePackageReader> reader, const char* builtin_root) {
        tgfx::set_builtin_shader_root(builtin_root);
        tgfx::set_builtin_shader_read_callback([reader](std::string_view path, std::string& output) {
            const auto bytes = read_shader_file(*reader, path);
            if (!bytes)
                return false;
            output.assign(bytes.view().begin(), bytes.view().end());
            return true;
        });
        return [reader = std::move(reader)](std::string_view path, std::vector<std::uint8_t>& output) {
            const auto bytes = read_shader_file(*reader, path);
            if (!bytes)
                return false;
            output.assign(bytes.view().begin(), bytes.view().end());
            return true;
        };
    }

    void configure_graphics_assets(tgfx::GraphicsHost& host, std::shared_ptr<runtime::RuntimePackageReader> reader) {
        if (!reader || !reader->contains("builtin_shaders/engine-shader-catalog.json"))
            throw std::invalid_argument("Web graphics asset pack requires builtin_shaders/engine-shader-catalog.json");
        bootstrap::bootstrap_runtime(bootstrap::RuntimeBootstrapProfile::Render);
        auto read = bind_package_shader_sources(std::move(reader), "builtin_shaders");
        host.configure_shader_artifacts(ShaderArtifactResolver("", "", "", false, false, std::move(read)));
    }
} // namespace termin::web
