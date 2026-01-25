#pragma once

#include <glad/glad.h>
#include "termin/render/handles.hpp"

namespace termin {

// 1x1 depth texture for sampler2DShadow placeholders.
// AMD drivers require sampler2DShadow to be bound to valid depth textures
// with GL_TEXTURE_COMPARE_MODE, even if not used in shader.
// Returns 1.0 (fully lit) when sampled.
class DummyShadowTexture : public GPUTextureHandle {
public:
    GLuint tex_id_ = 0;

    DummyShadowTexture() = default;
    ~DummyShadowTexture() override { release(); }

    void ensure_created() {
        if (tex_id_ != 0) {
            return;
        }

        glGenTextures(1, &tex_id_);
        glBindTexture(GL_TEXTURE_2D, tex_id_);

        // 1x1 depth texture with value 1.0 (max depth = no shadow)
        float depth_value = 1.0f;
        glTexImage2D(
            GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT24,
            1, 1, 0,
            GL_DEPTH_COMPONENT, GL_FLOAT,
            &depth_value
        );

        // Parameters for sampler2DShadow
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);

        // Hardware depth comparison for sampler2DShadow
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_COMPARE_MODE, GL_COMPARE_REF_TO_TEXTURE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_COMPARE_FUNC, GL_LEQUAL);

        glBindTexture(GL_TEXTURE_2D, 0);
    }

    void bind(int unit) override {
        ensure_created();
        glActiveTexture(GL_TEXTURE0 + unit);
        glBindTexture(GL_TEXTURE_2D, tex_id_);
    }

    void release() override {
        if (tex_id_ != 0) {
            glDeleteTextures(1, &tex_id_);
            tex_id_ = 0;
        }
    }

    uint32_t get_id() const override { return tex_id_; }
    int get_width() const override { return 1; }
    int get_height() const override { return 1; }
};

// Global singleton for dummy shadow texture
inline DummyShadowTexture& get_dummy_shadow_texture() {
    static DummyShadowTexture instance;
    return instance;
}

} // namespace termin
