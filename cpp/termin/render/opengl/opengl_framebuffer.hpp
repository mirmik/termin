#pragma once

#include <glad/glad.h>
#include <stdexcept>
#include <string>

#include "termin/render/handles.hpp"
#include "termin/render/opengl/opengl_texture.hpp"

namespace termin {

/**
 * Standard framebuffer with color and depth attachments.
 * Supports MSAA (samples > 1).
 */
class OpenGLFramebufferHandle : public FramebufferHandle {
public:
    OpenGLFramebufferHandle(int width, int height, int samples = 1)
        : fbo_(0), color_tex_(0), depth_rb_(0),
          width_(width), height_(height), samples_(samples),
          owns_attachments_(true), color_ref_(0) {
        create();
    }

    /**
     * Create a handle that wraps an external FBO (e.g., window default FBO).
     * Does not allocate any resources.
     */
    static std::unique_ptr<OpenGLFramebufferHandle> create_external(
        uint32_t fbo_id, int width, int height
    ) {
        auto handle = std::unique_ptr<OpenGLFramebufferHandle>(
            new OpenGLFramebufferHandle(fbo_id, width, height, /*external=*/true)
        );
        return handle;
    }

private:
    // Private constructor for external FBOs
    OpenGLFramebufferHandle(uint32_t fbo_id, int width, int height, bool /*external*/)
        : fbo_(fbo_id), color_tex_(0), depth_rb_(0),
          width_(width), height_(height), samples_(1),
          owns_attachments_(false), color_ref_(0) {
        // No create() - external FBO
    }

public:

    ~OpenGLFramebufferHandle() override {
        release();
    }

    void resize(int width, int height) override {
        if (width == width_ && height == height_ && fbo_ != 0) {
            return;
        }
        if (!owns_attachments_) {
            // External target - just update size
            width_ = width;
            height_ = height;
            return;
        }
        release();
        width_ = width;
        height_ = height;
        create();
    }

    void release() override {
        if (!owns_attachments_) {
            fbo_ = 0;
            return;
        }
        if (fbo_ != 0) {
            glDeleteFramebuffers(1, &fbo_);
            fbo_ = 0;
        }
        if (color_tex_ != 0) {
            glDeleteTextures(1, &color_tex_);
            color_tex_ = 0;
        }
        if (depth_rb_ != 0) {
            glDeleteRenderbuffers(1, &depth_rb_);
            depth_rb_ = 0;
        }
    }

    void set_external_target(uint32_t fbo_id, int width, int height) override {
        release();
        owns_attachments_ = false;
        fbo_ = fbo_id;
        width_ = width;
        height_ = height;
        color_tex_ = 0;
        depth_rb_ = 0;
    }

    uint32_t get_fbo_id() const override { return fbo_; }
    int get_width() const override { return width_; }
    int get_height() const override { return height_; }
    int get_samples() const override { return samples_; }
    bool is_msaa() const override { return samples_ > 1; }

    GPUTextureHandle* color_texture() override {
        color_ref_.set_tex_id(color_tex_);
        color_ref_.set_target(samples_ > 1 ? GL_TEXTURE_2D_MULTISAMPLE : GL_TEXTURE_2D);
        return &color_ref_;
    }

    GPUTextureHandle* depth_texture() override {
        return nullptr;  // Depth is renderbuffer, not texture
    }

private:
    void create() {
        glGenFramebuffers(1, &fbo_);
        glBindFramebuffer(GL_FRAMEBUFFER, fbo_);

        if (samples_ > 1) {
            // MSAA
            glGenTextures(1, &color_tex_);
            glBindTexture(GL_TEXTURE_2D_MULTISAMPLE, color_tex_);
            glTexImage2DMultisample(GL_TEXTURE_2D_MULTISAMPLE, samples_, GL_RGBA8, width_, height_, GL_TRUE);
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D_MULTISAMPLE, color_tex_, 0);

            glGenRenderbuffers(1, &depth_rb_);
            glBindRenderbuffer(GL_RENDERBUFFER, depth_rb_);
            glRenderbufferStorageMultisample(GL_RENDERBUFFER, samples_, GL_DEPTH_COMPONENT24, width_, height_);
            glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, depth_rb_);
        } else {
            // No MSAA
            glGenTextures(1, &color_tex_);
            glBindTexture(GL_TEXTURE_2D, color_tex_);
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, width_, height_, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE);
            glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE);
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, color_tex_, 0);

            glGenRenderbuffers(1, &depth_rb_);
            glBindRenderbuffer(GL_RENDERBUFFER, depth_rb_);
            glRenderbufferStorage(GL_RENDERBUFFER, GL_DEPTH_COMPONENT24, width_, height_);
            glFramebufferRenderbuffer(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_RENDERBUFFER, depth_rb_);
        }

        GLenum status = glCheckFramebufferStatus(GL_FRAMEBUFFER);
        if (status != GL_FRAMEBUFFER_COMPLETE) {
            glBindFramebuffer(GL_FRAMEBUFFER, 0);
            throw std::runtime_error("Framebuffer incomplete: 0x" + std::to_string(status));
        }

        glBindFramebuffer(GL_FRAMEBUFFER, 0);
    }

    GLuint fbo_;
    GLuint color_tex_;
    GLuint depth_rb_;
    int width_;
    int height_;
    int samples_;
    bool owns_attachments_;
    OpenGLTextureRef color_ref_;
};

/**
 * Shadow framebuffer with depth texture for shadow mapping.
 * Uses hardware PCF (sampler2DShadow).
 */
class OpenGLShadowFramebufferHandle : public FramebufferHandle {
public:
    OpenGLShadowFramebufferHandle(int width, int height)
        : fbo_(0), depth_tex_(0), width_(width), height_(height),
          owns_attachments_(true), depth_ref_(0) {
        create();
    }

    ~OpenGLShadowFramebufferHandle() override {
        release();
    }

    void resize(int width, int height) override {
        if (width == width_ && height == height_ && fbo_ != 0) {
            return;
        }
        if (!owns_attachments_) {
            width_ = width;
            height_ = height;
            return;
        }
        release();
        width_ = width;
        height_ = height;
        create();
    }

    void release() override {
        if (!owns_attachments_) {
            fbo_ = 0;
            return;
        }
        if (fbo_ != 0) {
            glDeleteFramebuffers(1, &fbo_);
            fbo_ = 0;
        }
        if (depth_tex_ != 0) {
            glDeleteTextures(1, &depth_tex_);
            depth_tex_ = 0;
        }
    }

    void set_external_target(uint32_t fbo_id, int width, int height) override {
        release();
        owns_attachments_ = false;
        fbo_ = fbo_id;
        width_ = width;
        height_ = height;
        depth_tex_ = 0;
    }

    uint32_t get_fbo_id() const override { return fbo_; }
    int get_width() const override { return width_; }
    int get_height() const override { return height_; }
    int get_samples() const override { return 1; }
    bool is_msaa() const override { return false; }

    GPUTextureHandle* color_texture() override {
        // Shadow FBO has no color, return depth texture
        return depth_texture();
    }

    GPUTextureHandle* depth_texture() override {
        depth_ref_.set_tex_id(depth_tex_);
        return &depth_ref_;
    }

private:
    void create() {
        glGenFramebuffers(1, &fbo_);
        glBindFramebuffer(GL_FRAMEBUFFER, fbo_);

        // Depth texture
        glGenTextures(1, &depth_tex_);
        glBindTexture(GL_TEXTURE_2D, depth_tex_);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_DEPTH_COMPONENT24, width_, height_, 0, GL_DEPTH_COMPONENT, GL_FLOAT, nullptr);

        // PCF filtering
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_BORDER);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_BORDER);

        // Border = 1.0 (max depth = no shadow)
        float border[] = {1.0f, 1.0f, 1.0f, 1.0f};
        glTexParameterfv(GL_TEXTURE_2D, GL_TEXTURE_BORDER_COLOR, border);

        // Hardware depth comparison for sampler2DShadow
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_COMPARE_MODE, GL_COMPARE_REF_TO_TEXTURE);
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_COMPARE_FUNC, GL_LEQUAL);

        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_DEPTH_ATTACHMENT, GL_TEXTURE_2D, depth_tex_, 0);

        // No color attachment
        glDrawBuffer(GL_NONE);
        glReadBuffer(GL_NONE);

        GLenum status = glCheckFramebufferStatus(GL_FRAMEBUFFER);
        if (status != GL_FRAMEBUFFER_COMPLETE) {
            glBindFramebuffer(GL_FRAMEBUFFER, 0);
            throw std::runtime_error("Shadow framebuffer incomplete: 0x" + std::to_string(status));
        }

        glBindFramebuffer(GL_FRAMEBUFFER, 0);
    }

    GLuint fbo_;
    GLuint depth_tex_;
    int width_;
    int height_;
    bool owns_attachments_;
    OpenGLTextureRef depth_ref_;
};

} // namespace termin
