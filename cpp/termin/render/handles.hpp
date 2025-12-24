#pragma once

#include <cstdint>
#include <array>
#include <memory>

#include "termin/render/types.hpp"

namespace termin {

/**
 * Abstract shader program handle.
 */
class ShaderHandle {
public:
    virtual ~ShaderHandle() = default;

    virtual void use() = 0;
    virtual void stop() = 0;
    virtual void release() = 0;

    virtual void set_uniform_int(const char* name, int value) = 0;
    virtual void set_uniform_float(const char* name, float value) = 0;
    virtual void set_uniform_vec2(const char* name, float x, float y) = 0;
    virtual void set_uniform_vec3(const char* name, float x, float y, float z) = 0;
    virtual void set_uniform_vec4(const char* name, float x, float y, float z, float w) = 0;
    virtual void set_uniform_matrix4(const char* name, const float* data, bool transpose = true) = 0;
    virtual void set_uniform_matrix4_array(const char* name, const float* data, int count, bool transpose = true) = 0;
};

/**
 * Abstract mesh buffer handle (VAO/VBO/EBO).
 */
class GPUMeshHandle {
public:
    virtual ~GPUMeshHandle() = default;

    virtual void draw() = 0;
    virtual void release() = 0;
};

/**
 * Abstract GPU texture handle.
 */
class GPUTextureHandle {
public:
    virtual ~GPUTextureHandle() = default;

    virtual void bind(int unit = 0) = 0;
    virtual void release() = 0;

    virtual uint32_t get_id() const = 0;
    virtual int get_width() const = 0;
    virtual int get_height() const = 0;
};

/**
 * Abstract framebuffer handle.
 */
class FramebufferHandle {
public:
    virtual ~FramebufferHandle() = default;

    virtual void resize(int width, int height) = 0;
    virtual void release() = 0;

    /**
     * Rebind to an externally managed FBO (e.g., Qt's default framebuffer).
     * The handle will not own or delete the FBO.
     */
    virtual void set_external_target(uint32_t fbo_id, int width, int height) = 0;

    virtual uint32_t get_fbo_id() const = 0;
    virtual int get_width() const = 0;
    virtual int get_height() const = 0;
    virtual int get_samples() const = 0;
    virtual bool is_msaa() const = 0;

    // Convenience methods
    Size2i get_size() const { return Size2i(get_width(), get_height()); }
    void resize(Size2i size) { resize(size.width, size.height); }
    void set_external_target(uint32_t fbo_id, Size2i size) {
        set_external_target(fbo_id, size.width, size.height);
    }

    virtual GPUTextureHandle* color_texture() = 0;
    virtual GPUTextureHandle* depth_texture() = 0;
};

/**
 * Unique pointer types for handles.
 */
using ShaderHandlePtr = std::unique_ptr<ShaderHandle>;
using GPUMeshHandlePtr = std::unique_ptr<GPUMeshHandle>;
using GPUTextureHandlePtr = std::unique_ptr<GPUTextureHandle>;
using FramebufferHandlePtr = std::unique_ptr<FramebufferHandle>;

} // namespace termin
