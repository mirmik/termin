#pragma once

#include <memory>
#include <tgfx2/shader_artifact_resolver.hpp>

namespace tgfx {
    class GraphicsHost;
}

namespace termin::runtime {
    class RuntimePackageReader;
}

namespace termin::web {

    inline constexpr char default_font_path[] = "/fonts/DroidSans.ttf";

    ShaderArtifactResolver::ReadCallback
    bind_package_shader_sources(std::shared_ptr<runtime::RuntimePackageReader> reader, const char* builtin_root);

    void configure_graphics_assets(tgfx::GraphicsHost& host, std::shared_ptr<runtime::RuntimePackageReader> reader);

} // namespace termin::web
