#pragma once

#include <memory>
#include <string>
#include <vector>

#include <termin/runtime/termin_runtime_api.h>
#include <termin/bootstrap/bootstrap.hpp>
#include <termin/tc_scene.hpp>

extern "C" {
#include <core/tc_scene_extension.h>
}

namespace termin::runtime {

struct RuntimePackageResourceKeepalive;

struct RuntimePackageLoadOptions {
    // Extensions required by the runtime host. They are attached to every
    // packaged scene before components are deserialized.
    std::vector<tc_scene_ext_type_id> scene_extensions;
    // Full remains the native-compatible default. Minimal registers only the
    // core scene domain and rejects package content that needs omitted types.
    bootstrap::RuntimeBootstrapProfile bootstrap_profile =
        bootstrap::RuntimeBootstrapProfile::Full;
};

struct ShaderRuntimeConfiguration {
    std::string artifact_root;
    std::string builtin_shader_root;
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
    // Destroy every scene loaded by this package, then release its canonical
    // resources. Runtime hosts must first destroy execution objects (for
    // example RenderPipeline instances) that retain package resources.
    TERMIN_RUNTIME_API void destroy();
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
