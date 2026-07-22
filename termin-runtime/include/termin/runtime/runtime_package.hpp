#pragma once

#include <memory>
#include <string>
#include <vector>

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

struct RuntimePackageScene {
    std::string identity;
    std::string package_path;
    TcSceneRef scene;
};

struct RuntimePackageLoadResult {
    bool ok = false;
    std::string message;
    std::string entry_scene_identity;
    std::vector<RuntimePackageScene> scenes;
    // Convenience alias for the entry in ``scenes``.
    TcSceneRef scene;
    std::shared_ptr<RuntimePackageResourceKeepalive> resources;
    ShaderRuntimeConfiguration shader_runtime;

    TERMIN_RUNTIME_API TcSceneRef find_scene(const std::string& identity) const;
};

class TERMIN_RUNTIME_API RuntimePackageLoader {
public:
    RuntimePackageLoadResult load(const std::string& root_path);
};

TERMIN_RUNTIME_API RuntimePackageLoadResult load_runtime_package(
    const std::string& root_path
);

} // namespace termin::runtime
