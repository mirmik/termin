#pragma once

#include <memory>
#include <string>

#include <termin/runtime/termin_runtime_api.h>
#include <termin/tc_scene.hpp>

namespace termin::runtime {

struct RuntimePackageResourceKeepalive;

struct ShaderRuntimeConfiguration {
    std::string artifact_root;
    std::string cache_root;
    std::string compiler_path;
    bool dev_compile_enabled = false;
};

struct RuntimePackageLoadOptions {
    bool allow_fallback_scene = false;
};

struct RuntimePackageLoadResult {
    bool ok = false;
    std::string message;
    TcSceneRef scene;
    std::shared_ptr<RuntimePackageResourceKeepalive> resources;
    ShaderRuntimeConfiguration shader_runtime;
};

class TERMIN_RUNTIME_API RuntimePackageLoader {
public:
    RuntimePackageLoadResult load(
        const std::string& root_path,
        const RuntimePackageLoadOptions& options = {}
    );
};

TERMIN_RUNTIME_API RuntimePackageLoadResult load_runtime_package(
    const std::string& root_path,
    const RuntimePackageLoadOptions& options = {}
);

} // namespace termin::runtime
