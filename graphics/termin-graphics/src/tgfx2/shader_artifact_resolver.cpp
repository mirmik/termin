// shader_artifact_resolver.cpp - shader artifact configuration and discovery.
#include "tgfx2/shader_artifact_resolver.hpp"

#include "tgfx2/builtin_shader_sources.hpp"

#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <utility>

namespace termin {

    namespace {

        std::string discover_installed_shader_artifact_root() {
            for (const std::filesystem::path& builtin_root : tgfx::builtin_shader_roots()) {
                const std::filesystem::path candidate = builtin_root.parent_path();
                std::error_code directory_error;
                if (!std::filesystem::is_directory(candidate / "shaders", directory_error)) {
                    continue;
                }

                std::error_code canonical_error;
                const std::filesystem::path canonical = std::filesystem::weakly_canonical(candidate, canonical_error);
                return (canonical_error ? candidate.lexically_normal() : canonical).string();
            }
            return {};
        }

    } // anonymous namespace

    ShaderArtifactResolver::ShaderArtifactResolver(std::string artifact_root,
                                                   std::string cache_root,
                                                   std::string compiler_path,
                                                   bool dev_compile_enabled,
                                                   bool environment_fallback,
                                                   ReadCallback read_callback)
        : ShaderArtifactResolver(std::move(artifact_root),
                                 std::move(cache_root),
                                 std::move(compiler_path),
                                 dev_compile_enabled,
                                 environment_fallback,
                                 std::move(read_callback),
                                 {}) {}

    ShaderArtifactResolver::ShaderArtifactResolver(std::string artifact_root,
                                                   std::string cache_root,
                                                   std::string compiler_path,
                                                   bool dev_compile_enabled,
                                                   bool environment_fallback,
                                                   ReadCallback read_callback,
                                                   std::vector<std::string> fallback_artifact_roots)
        : artifact_root_(std::move(artifact_root)),
          cache_root_(std::move(cache_root)),
          compiler_path_(std::move(compiler_path)),
          dev_compile_enabled_(dev_compile_enabled),
          environment_fallback_(environment_fallback),
          read_callback_(std::move(read_callback)),
          fallback_artifact_roots_(std::move(fallback_artifact_roots)) {}

    const std::string& ShaderArtifactResolver::artifact_root() const {
        if (!artifact_root_.empty() || !environment_fallback_)
            return artifact_root_;
        const char* value = std::getenv("TERMIN_SHADER_ARTIFACT_ROOT");
        if (value && value[0] != '\0') {
            environment_artifact_root_ = value;
            return environment_artifact_root_;
        }
        environment_artifact_root_ = discover_installed_shader_artifact_root();
        return environment_artifact_root_;
    }

    const std::string& ShaderArtifactResolver::cache_root() const {
        if (!cache_root_.empty() || !environment_fallback_)
            return cache_root_;
        const char* value = std::getenv("TERMIN_SHADER_CACHE_ROOT");
        environment_cache_root_ = value ? value : "";
        return environment_cache_root_;
    }

    const std::string& ShaderArtifactResolver::compiler_path() const {
        if (!compiler_path_.empty() || !environment_fallback_)
            return compiler_path_;
        const char* value = std::getenv("TERMIN_SHADERC");
        environment_compiler_path_ = value ? value : "";
        return environment_compiler_path_;
    }

    const std::vector<std::string>& ShaderArtifactResolver::fallback_artifact_roots() const {
        return fallback_artifact_roots_;
    }

    bool ShaderArtifactResolver::dev_compile_enabled() const {
        if (dev_compile_enabled_)
            return true;
        if (!environment_fallback_)
            return false;
        const char* value = std::getenv("TERMIN_SHADER_DEV_COMPILE");
        return value && value[0] == '1';
    }

    bool ShaderArtifactResolver::read_artifact(std::string_view path, std::vector<std::uint8_t>& out) const {
        if (read_callback_)
            return read_callback_(path, out);
        std::ifstream input(std::filesystem::path(path), std::ios::binary);
        if (!input)
            return false;
        out.assign(std::istreambuf_iterator<char>(input), std::istreambuf_iterator<char>());
        return !out.empty();
    }

    void ShaderArtifactResolver::configure(std::string artifact_root,
                                           std::string cache_root,
                                           std::string compiler_path,
                                           bool dev_compile_enabled,
                                           ReadCallback read_callback) {
        configure(std::move(artifact_root),
                  std::move(cache_root),
                  std::move(compiler_path),
                  dev_compile_enabled,
                  std::move(read_callback),
                  {});
    }

    void ShaderArtifactResolver::configure(std::string artifact_root,
                                           std::string cache_root,
                                           std::string compiler_path,
                                           bool dev_compile_enabled,
                                           ReadCallback read_callback,
                                           std::vector<std::string> fallback_artifact_roots) {
        artifact_root_ = std::move(artifact_root);
        cache_root_ = std::move(cache_root);
        compiler_path_ = std::move(compiler_path);
        dev_compile_enabled_ = dev_compile_enabled;
        read_callback_ = std::move(read_callback);
        fallback_artifact_roots_ = std::move(fallback_artifact_roots);
        ++revision_;
    }

    void ShaderArtifactResolver::set_artifact_root(std::string value) {
        if (artifact_root_ == value)
            return;
        artifact_root_ = std::move(value);
        ++revision_;
    }

    void ShaderArtifactResolver::set_fallback_artifact_roots(std::vector<std::string> values) {
        if (fallback_artifact_roots_ == values)
            return;
        fallback_artifact_roots_ = std::move(values);
        ++revision_;
    }

    void ShaderArtifactResolver::set_cache_root(std::string value) {
        if (cache_root_ == value)
            return;
        cache_root_ = std::move(value);
        ++revision_;
    }

    void ShaderArtifactResolver::set_compiler_path(std::string value) {
        if (compiler_path_ == value)
            return;
        compiler_path_ = std::move(value);
        ++revision_;
    }

    void ShaderArtifactResolver::set_dev_compile_enabled(bool value) {
        if (dev_compile_enabled_ == value)
            return;
        dev_compile_enabled_ = value;
        ++revision_;
    }

    ShaderArtifactResolver& tgfx2_legacy_shader_artifact_resolver() {
        static ShaderArtifactResolver resolver("", "", "", false, true);
        return resolver;
    }

} // namespace termin
