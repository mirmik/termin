#include <array>
#include <cmath>
#include <cstdio>
#include <stdexcept>

#define SDL_MAIN_HANDLED
#include <SDL.h>
#include "tgfx2/i_command_list.hpp"
#include "tgfx2/opengl/opengl_render_device.hpp"

namespace {
    constexpr int width = 7;
    constexpr int height = 5;

    void require(bool ok, const char* message) {
        if (!ok)
            throw std::runtime_error(message);
    }

    struct Context {
        SDL_Window* window = nullptr;
        SDL_GLContext context = nullptr;
        ~Context() {
            if (context)
                SDL_GL_DeleteContext(context);
            if (window)
                SDL_DestroyWindow(window);
            SDL_Quit();
        }
    };

    struct FramebufferState {
        GLint read = 0;
        GLint draw = 0;
        GLint read_buffer = 0;
        std::array<GLint, 2> draw_buffers{};
        bool operator==(const FramebufferState&) const = default;
    };

    FramebufferState framebuffer_state() {
        FramebufferState state;
        glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &state.read);
        glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &state.draw);
        glGetIntegerv(GL_READ_BUFFER, &state.read_buffer);
        glGetIntegerv(GL_DRAW_BUFFER0, &state.draw_buffers[0]);
        glGetIntegerv(GL_DRAW_BUFFER1, &state.draw_buffers[1]);
        return state;
    }

    GLuint shader(GLenum stage, const char* source) {
        GLuint result = glCreateShader(stage);
        glShaderSource(result, 1, &source, nullptr);
        glCompileShader(result);
        GLint compiled = 0;
        glGetShaderiv(result, GL_COMPILE_STATUS, &compiled);
        require(compiled == GL_TRUE, "depth-state regression shader compilation failed");
        return result;
    }

    void run(tgfx::GlFeatureTier tier) {
        tgfx::OpenGLRenderDevice device({tier});
        tgfx::TextureDesc desc;
        desc.width = width;
        desc.height = height;
        desc.format = tgfx::PixelFormat::D32F;
        desc.usage = tgfx::TextureUsage::DepthStencilAttachment | tgfx::TextureUsage::CopySrc;
        auto depth = device.create_texture(desc);
        require(bool(depth), "depth texture creation failed");
        auto commands = device.create_command_list();
        tgfx::RenderPassDesc pass;
        pass.has_depth = true;
        pass.depth.texture = depth;
        pass.depth.clear_depth = 0.375f;
        commands->begin();
        commands->begin_render_pass(pass);
        commands->end_render_pass();
        commands->end();
        device.submit(*commands);

        std::array<GLuint, 2> colors{};
        std::array<GLuint, 2> fbos{};
        glGenTextures(2, colors.data());
        glGenFramebuffers(2, fbos.data());
        glBindFramebuffer(GL_FRAMEBUFFER, fbos[0]);
        for (size_t i = 0; i < colors.size(); ++i) {
            glBindTexture(GL_TEXTURE_2D, colors[i]);
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, width, height, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
            glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0 + i, GL_TEXTURE_2D, colors[i], 0);
        }
        // Non-default mapping catches damage to either draw-buffer slot.
        const GLenum targets[] = {GL_COLOR_ATTACHMENT1, GL_COLOR_ATTACHMENT0};
        glDrawBuffers(2, targets);
        require(glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE, "MRT incomplete");
        glBindFramebuffer(GL_READ_FRAMEBUFFER, fbos[1]);
        glFramebufferTexture2D(GL_READ_FRAMEBUFFER, GL_COLOR_ATTACHMENT1, GL_TEXTURE_2D, colors[1], 0);
        glReadBuffer(GL_COLOR_ATTACHMENT1);

        const GLuint vertex = shader(GL_VERTEX_SHADER, R"(#version 330 core
void main() {
    vec2 p = vec2((gl_VertexID << 1) & 2, gl_VertexID & 2);
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
})");
        const GLuint fragment = shader(GL_FRAGMENT_SHADER, R"(#version 330 core
layout(location = 0) out vec4 first;
layout(location = 1) out vec4 second;
void main() { first = vec4(1, 0, 0, 1); second = vec4(0, 1, 0, 1); }
)");
        const GLuint program = glCreateProgram();
        glAttachShader(program, vertex);
        glAttachShader(program, fragment);
        glLinkProgram(program);
        GLint linked = 0;
        glGetProgramiv(program, GL_LINK_STATUS, &linked);
        require(linked == GL_TRUE, "depth-state regression program link failed");
        glUseProgram(program);
        GLuint vao = 0;
        glGenVertexArrays(1, &vao);
        glBindVertexArray(vao);
        glViewport(0, 0, width, height);
        glDisable(GL_DEPTH_TEST);
        glDisable(GL_CULL_FACE);
        glDisable(GL_SCISSOR_TEST);
        glDisable(GL_BLEND);
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);

        for (int scenario = 0; scenario < 3; ++scenario) {
            glBindFramebuffer(GL_READ_FRAMEBUFFER, fbos[1]);
            glReadBuffer(GL_COLOR_ATTACHMENT1);
            const GLfloat black[] = {0, 0, 0, 1};
            glClearBufferfv(GL_COLOR, 0, black);
            glClearBufferfv(GL_COLOR, 1, black);
            const auto before = framebuffer_state();
            float value = 0;
            if (scenario == 0) {
                std::array<float, width * height> values{};
                require(device.read_texture_depth_float(depth, values.data()), "full depth read failed");
                for (float sample : values)
                    require(std::abs(sample - 0.375f) < 0.001f, "full depth read returned wrong values");
                value = values[0];
            } else if (scenario == 1) {
                require(device.read_pixel_depth_float(depth, 2, 3, &value), "single depth read failed");
            } else {
                const uint64_t request = device.request_pixel_depth_float(depth, 2, 3);
                require(request != 0, "async depth request failed");
                require(framebuffer_state() == before, "async depth request damaged FBO state");
                glFinish();
                require(device.poll_pixel_depth_float(request, &value), "async depth poll failed");
            }
            require(std::abs(value - 0.375f) < 0.001f, "depth read returned wrong value");
            require(framebuffer_state() == before, "depth read damaged FBO bindings or buffer selection");
            // No render-pass restart or draw-FBO rebinding may hide the mutation.
            glDrawArrays(GL_TRIANGLES, 0, 3);
            glBindFramebuffer(GL_READ_FRAMEBUFFER, fbos[0]);
            for (size_t attachment = 0; attachment < colors.size(); ++attachment) {
                glReadBuffer(GL_COLOR_ATTACHMENT0 + attachment);
                std::array<unsigned char, width * height * 4> pixels{};
                glReadPixels(0, 0, width, height, GL_RGBA, GL_UNSIGNED_BYTE, pixels.data());
                for (size_t i = 0; i < pixels.size(); i += 4) {
                    require(pixels[i] == (attachment == 1 ? 255 : 0) &&
                                pixels[i + 1] == (attachment == 0 ? 255 : 0) &&
                                pixels[i + 2] == 0 && pixels[i + 3] == 255,
                            "draw after depth read lost an MRT output");
                }
            }
            require(glGetError() == GL_NO_ERROR, "depth read state regression generated a GL error");
        }
        glBindFramebuffer(GL_FRAMEBUFFER, 0);
        glUseProgram(0);
        glBindVertexArray(0);
        glDeleteVertexArrays(1, &vao);
        glDeleteProgram(program);
        glDeleteShader(vertex);
        glDeleteShader(fragment);
        glDeleteFramebuffers(2, fbos.data());
        glDeleteTextures(2, colors.data());
        commands.reset();
        device.destroy(depth);
    }
} // namespace

int main() {
    Context context;
    SDL_SetMainReady();
    if (SDL_Init(SDL_INIT_VIDEO) != 0) {
        std::fprintf(stderr, "Window creation failed: %s\n", SDL_GetError());
        return 1;
    }
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MAJOR_VERSION, 4);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_MINOR_VERSION, 5);
    SDL_GL_SetAttribute(SDL_GL_CONTEXT_PROFILE_MASK, SDL_GL_CONTEXT_PROFILE_CORE);
    context.window = SDL_CreateWindow("OpenGL depth read state", 0, 0, width, height,
                                      SDL_WINDOW_OPENGL | SDL_WINDOW_HIDDEN);
    if (context.window)
        context.context = SDL_GL_CreateContext(context.window);
    if (!context.context) {
        std::fprintf(stderr, "Window creation failed: %s\n", SDL_GetError());
        return 1;
    }
    try {
        run(tgfx::GlFeatureTier::Modern);
        run(tgfx::GlFeatureTier::Constrained33);
    } catch (const std::exception& error) {
        std::fprintf(stderr, "OpenGL depth read state: %s\n", error.what());
        return 1;
    }
    std::puts("OpenGL depth read FBO state and MRT regressions passed");
    return 0;
}
