#pragma once

#include <string>
#include <memory>
#include <stdexcept>

#include "termin/render/handles.hpp"
#include "termin/render/glsl_preprocessor.hpp"
#include "termin/render/tc_shader_handle.hpp"
#include "termin/geom/mat44.hpp"
#include "termin/geom/vec3.hpp"

namespace termin {

/**
 * Shader program that manages GLSL sources and compilation.
 *
 * Stores vertex/fragment/geometry sources and compiles lazily on first use.
 * Provides convenient uniform setters.
 *
 * Note: GLSL preprocessing (#include) should be done before passing
 * sources to this class.
 */
class ShaderProgram {
public:
    ShaderProgram() = default;

    ShaderProgram(
        std::string vertex_source,
        std::string fragment_source,
        std::string geometry_source = "",
        std::string source_path = "",
        std::string name = ""
    ) : vertex_source_(std::move(vertex_source)),
        fragment_source_(std::move(fragment_source)),
        geometry_source_(std::move(geometry_source)),
        source_path_(std::move(source_path)),
        name_(std::move(name)) {
        // Register in tc_shader registry
        register_in_registry();
    }

    // Construct from existing TcShader
    explicit ShaderProgram(const TcShader& shader)
        : tc_shader_(shader) {
        if (shader.is_valid()) {
            vertex_source_ = shader.vertex_source();
            fragment_source_ = shader.fragment_source();
            geometry_source_ = shader.geometry_source();
            source_path_ = shader.source_path();
            name_ = shader.name();
        }
    }

    // Getters for sources
    const std::string& vertex_source() const { return vertex_source_; }
    const std::string& fragment_source() const { return fragment_source_; }
    const std::string& geometry_source() const { return geometry_source_; }
    const std::string& source_path() const { return source_path_; }
    const std::string& name() const { return name_; }

    // Check if compiled
    bool is_compiled() const { return handle_ != nullptr; }

    // Get the tc_shader handle
    const TcShader& tc_shader() const { return tc_shader_; }

    // Get shader version (from registry)
    uint32_t version() const { return tc_shader_.version(); }

    // Check if shader needs recompilation (sources changed)
    bool needs_recompile() const {
        if (!handle_) return true;
        return compiled_version_ != tc_shader_.version();
    }

    // Check if this shader is a variant and is stale (original changed)
    bool variant_is_stale() const {
        return tc_shader_.variant_is_stale();
    }

    // Set variant info (mark this shader as variant of original)
    // Note: this modifies the shader in the registry, not the local object
    void set_variant_info(const ShaderProgram& original, tc_shader_variant_op op) {
        ::tc_shader* s = tc_shader_.get();
        if (s) {
            tc_shader_set_variant_info(s, original.tc_shader_.handle, op);
        }
    }

    /**
     * Compile shader if not already compiled.
     *
     * Uses the provided compile function to create the ShaderHandle.
     * This allows decoupling from specific graphics backend.
     * Automatically preprocesses GLSL sources (resolves #include).
     *
     * @param compile_fn Function that takes (vert, frag, geom) and returns ShaderHandlePtr
     * @param preprocess Whether to preprocess sources (default: true)
     */
    template<typename CompileFn>
    void ensure_ready(CompileFn compile_fn, bool preprocess = true) {
        // Check if recompilation needed
        if (handle_ && !needs_recompile()) return;

        std::string vs = vertex_source_;
        std::string fs = fragment_source_;
        std::string gs = geometry_source_;

        // Preprocess if needed
        if (preprocess) {
            const auto& pp = glsl_preprocessor();
            std::string name = source_path_.empty() ? "<inline>" : source_path_;

            if (GlslPreprocessor::has_includes(vs)) {
                vs = pp.preprocess(vs, name + ":vertex");
            }
            if (GlslPreprocessor::has_includes(fs)) {
                fs = pp.preprocess(fs, name + ":fragment");
            }
            if (!gs.empty() && GlslPreprocessor::has_includes(gs)) {
                gs = pp.preprocess(gs, name + ":geometry");
            }
        }

        const char* geom = gs.empty() ? nullptr : gs.c_str();
        handle_ = compile_fn(vs.c_str(), fs.c_str(), geom);

        if (!handle_) {
            throw std::runtime_error("Failed to compile shader: " + source_path_);
        }

        // Track compiled version
        compiled_version_ = tc_shader_.version();
    }

    /**
     * Set the compiled handle directly (for when compilation happens externally).
     */
    void set_handle(ShaderHandlePtr handle) {
        handle_ = std::move(handle);
    }

    /**
     * Get the underlying handle (may be null if not compiled).
     */
    ShaderHandle* handle() const { return handle_.get(); }

    /**
     * Use this shader program.
     */
    void use() {
        require_handle()->use();
    }

    /**
     * Stop using this shader program.
     */
    void stop() {
        if (handle_) handle_->stop();
    }

    /**
     * Release shader resources.
     */
    void release() {
        if (handle_) {
            handle_->release();
            handle_.reset();
        }
    }

    // ========== Uniform setters ==========

    void set_uniform_int(const char* name, int value) {
        require_handle()->set_uniform_int(name, value);
    }

    void set_uniform_float(const char* name, float value) {
        require_handle()->set_uniform_float(name, value);
    }

    void set_uniform_vec2(const char* name, float x, float y) {
        require_handle()->set_uniform_vec2(name, x, y);
    }

    void set_uniform_vec3(const char* name, float x, float y, float z) {
        require_handle()->set_uniform_vec3(name, x, y, z);
    }

    void set_uniform_vec3(const char* name, const Vec3& v) {
        require_handle()->set_uniform_vec3(name,
            static_cast<float>(v.x),
            static_cast<float>(v.y),
            static_cast<float>(v.z));
    }

    void set_uniform_vec4(const char* name, float x, float y, float z, float w) {
        require_handle()->set_uniform_vec4(name, x, y, z, w);
    }

    void set_uniform_matrix4(const char* name, const float* data, bool transpose = true) {
        require_handle()->set_uniform_matrix4(name, data, transpose);
    }

    void set_uniform_matrix4(const char* name, const Mat44f& m, bool transpose = true) {
        // Mat44f stores float directly, pass the data pointer
        require_handle()->set_uniform_matrix4(name, m.data, transpose);
    }

    void set_uniform_matrix4(const char* name, const Mat44& m, bool transpose = true) {
        // Mat44 stores double, convert to float
        require_handle()->set_uniform_matrix4(name, m.to_float().data, transpose);
    }

    void set_uniform_matrix4_array(const char* name, const float* data, int count, bool transpose = true) {
        require_handle()->set_uniform_matrix4_array(name, data, count, transpose);
    }

    // Convenience: set uniform with Vec3
    void set_uniform(const char* name, const Vec3& v) {
        set_uniform_vec3(name, v);
    }

    void set_uniform(const char* name, const Mat44& m) {
        set_uniform_matrix4(name, m);
    }

    void set_uniform(const char* name, float v) {
        set_uniform_float(name, v);
    }

    void set_uniform(const char* name, int v) {
        set_uniform_int(name, v);
    }

private:
    ShaderHandle* require_handle() {
        if (!handle_) {
            throw std::runtime_error("ShaderProgram not compiled. Call ensure_ready() first.");
        }
        return handle_.get();
    }

    void register_in_registry() {
        if (vertex_source_.empty() && fragment_source_.empty()) return;
        tc_shader_ = TcShader::from_sources(
            vertex_source_,
            fragment_source_,
            geometry_source_,
            name_,
            source_path_
        );
    }

    std::string vertex_source_;
    std::string fragment_source_;
    std::string geometry_source_;
    std::string source_path_;
    std::string name_;
    ShaderHandlePtr handle_;
    TcShader tc_shader_;
    uint32_t compiled_version_ = 0;
};

} // namespace termin
