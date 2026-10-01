#pragma once

#include <cstdint>
#include <functional>
#include <map>
#include <mutex>
#include <string>
#include <string_view>
#include <tuple>
#include <vector>

#include "tgfx2/tgfx2_api.h"

namespace termin {

    class TGFX2_TYPE_API ShaderArtifactResolver {
    public:
        using ReadCallback = std::function<bool(std::string_view, std::vector<std::uint8_t>&)>;

        ShaderArtifactResolver() = default;
        // Configuration copies start with independent, empty compile caches.
        ShaderArtifactResolver(const ShaderArtifactResolver& other);
        ShaderArtifactResolver& operator=(const ShaderArtifactResolver& other);
        ShaderArtifactResolver(std::string artifact_root,
                               std::string cache_root,
                               std::string compiler_path,
                               bool dev_compile_enabled,
                               bool environment_fallback = false,
                               ReadCallback read_callback = {});
        ShaderArtifactResolver(std::string artifact_root,
                               std::string cache_root,
                               std::string compiler_path,
                               bool dev_compile_enabled,
                               bool environment_fallback,
                               ReadCallback read_callback,
                               std::vector<std::string> fallback_artifact_roots);

        const std::string& artifact_root() const;
        const std::string& cache_root() const;
        const std::string& compiler_path() const;
        const std::vector<std::string>& fallback_artifact_roots() const;
        bool dev_compile_enabled() const;
        bool read_artifact(std::string_view path, std::vector<std::uint8_t>& out) const;
        bool has_read_callback() const {
            return static_cast<bool>(read_callback_);
        }
        uint64_t revision() const {
            return revision_;
        }

        void configure(std::string artifact_root,
                       std::string cache_root,
                       std::string compiler_path,
                       bool dev_compile_enabled,
                       ReadCallback read_callback = {});
        void configure(std::string artifact_root,
                       std::string cache_root,
                       std::string compiler_path,
                       bool dev_compile_enabled,
                       ReadCallback read_callback,
                       std::vector<std::string> fallback_artifact_roots);
        // Reapplying the same setting preserves the revision and live shader
        // handles. configure() explicitly replaces the configuration (including
        // its read callback) and always starts a new revision.
        void set_artifact_root(std::string value);
        void set_fallback_artifact_roots(std::vector<std::string> values);
        void set_cache_root(std::string value);
        void set_compiler_path(std::string value);
        void set_dev_compile_enabled(bool value);

        // Retry unchanged inputs without invalidating successful GPU handles.
        // Read/log callbacks may call these methods: callbacks never run under
        // the compile-cache mutex. Configuration and shader source mutation
        // must remain serialized with artifact loading by the owning runtime.
        void clear_failed_compilations() const;
        void clear_failed_tc_shader_compilations(uint32_t pool_index) const;

    private:
        friend struct ShaderArtifactResolverAccess;
        // One latest failure per source kind/UUID/exact target/stage, rather
        // than retaining the history of failed source versions.
        using FailureSlot = std::tuple<bool, std::string, uint8_t, uint8_t>;
        struct FailedCompilation {
            std::string fingerprint;
            uint32_t tc_pool_index = 0;
        };
        mutable std::mutex compile_mutex_;
        mutable std::map<FailureSlot, FailedCompilation> failed_compilations_;
        std::string artifact_root_;
        std::string cache_root_;
        std::string compiler_path_;
        bool dev_compile_enabled_ = false;
        bool environment_fallback_ = false;
        uint64_t revision_ = 1;
        mutable std::string environment_artifact_root_;
        mutable std::string environment_cache_root_;
        mutable std::string environment_compiler_path_;
        ReadCallback read_callback_;
        std::vector<std::string> fallback_artifact_roots_;
    };

    // Compatibility resolver for legacy standalone tgfx users. Engine/runtime
    // composition roots should configure their own resolver instead.
    TGFX2_API ShaderArtifactResolver& tgfx2_legacy_shader_artifact_resolver();

} // namespace termin
