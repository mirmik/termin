#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

#include <termin/bootstrap/bootstrap.hpp>
#include <termin/runtime/termin_runtime_api.h>
#include <termin/tc_scene.hpp>

extern "C" {
#include <core/tc_scene_extension.h>
}

namespace termin::runtime {

    inline constexpr std::uint32_t RUNTIME_PACKAGE_SCHEMA_VERSION = 3;

    struct RuntimePackageResourceKeepalive;

    struct RuntimePackageBytes {
        std::shared_ptr<const void> owner;
        const std::uint8_t* data = nullptr;
        std::size_t size = 0;

        std::span<const std::uint8_t> view() const {
            return {data, size};
        }
        explicit operator bool() const {
            return static_cast<bool>(owner);
        }
    };

    // Read-only package boundary used by RuntimePackageLoader. Paths are always
    // portable, package-relative paths; implementations own containment and
    // integrity validation.
    class TERMIN_RUNTIME_API RuntimePackageReader {
    public:
        virtual ~RuntimePackageReader() = default;
        virtual RuntimePackageBytes read(std::string_view path) const = 0;
        virtual bool contains(std::string_view path) const = 0;
        virtual std::string describe(std::string_view path) const = 0;
        virtual std::string materialized_path(std::string_view path) const = 0;
    };

    TERMIN_RUNTIME_API std::shared_ptr<RuntimePackageReader>
    open_runtime_package_directory(const std::string& root_path);

    TERMIN_RUNTIME_API std::shared_ptr<RuntimePackageReader>
    open_runtime_package_blob(std::shared_ptr<const std::vector<std::uint8_t>> blob,
                              std::string label = "runtime-package.blob");

    struct RuntimePackageLoadOptions {
        // Extensions required by the runtime host. They are attached to every
        // packaged scene before components are deserialized.
        std::vector<tc_scene_ext_type_id> scene_extensions;
        // Full remains the native-compatible default. Minimal registers only the
        // core scene domain and rejects package content that needs omitted types.
        bootstrap::RuntimeBootstrapProfile bootstrap_profile = bootstrap::RuntimeBootstrapProfile::Full;
    };

    struct ShaderRuntimeConfiguration {
        std::string artifact_root;
        std::string builtin_shader_root;
        std::string cache_root;
        std::string compiler_path;
        bool dev_compile_enabled = false;
        std::shared_ptr<RuntimePackageReader> resource_provider;
    };

    struct RuntimePackageScene {
        std::string identity;
        std::string package_path;
        TcSceneRef scene;
    };

    struct RuntimePackageWorldControllerSelection {
        std::string module;
        std::string type;

        bool operator==(const RuntimePackageWorldControllerSelection& other) const noexcept {
            return module == other.module && type == other.type;
        }
    };

    struct RuntimePackageLoadResult {
        bool ok = false;
        std::string message;
        std::string entry_scene_identity;
        std::optional<RuntimePackageWorldControllerSelection> world_controller;
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
        RuntimePackageLoadResult load(std::shared_ptr<RuntimePackageReader> reader,
                                      const RuntimePackageLoadOptions& options = {});
        RuntimePackageLoadResult load(const std::string& root_path, const RuntimePackageLoadOptions& options = {});
    };

    TERMIN_RUNTIME_API RuntimePackageLoadResult load_runtime_package(const std::string& root_path,
                                                                     const RuntimePackageLoadOptions& options = {});

} // namespace termin::runtime
