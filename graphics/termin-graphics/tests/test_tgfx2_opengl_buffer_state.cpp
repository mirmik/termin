#include <algorithm>
#include <array>
#include <cstdio>
#include <limits>
#include <span>
#include <stdexcept>

#define SDL_MAIN_HANDLED
#include <SDL.h>
#include "tgfx2/opengl/opengl_render_device.hpp"

namespace {
    constexpr int extent = 8;

    void require(bool condition, const char* message) {
        if (!condition)
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

    struct Bindings {
        GLint vao = 0;
        GLint element = 0;
        GLint vertex = 0;
        GLint uniform = 0;
        GLint copy_read = 0;
        GLint copy_write = 0;
        bool operator==(const Bindings&) const = default;
    };

    Bindings bindings() {
        Bindings result;
        glGetIntegerv(GL_VERTEX_ARRAY_BINDING, &result.vao);
        glGetIntegerv(GL_ELEMENT_ARRAY_BUFFER_BINDING, &result.element);
        glGetIntegerv(GL_ARRAY_BUFFER_BINDING, &result.vertex);
        glGetIntegerv(GL_UNIFORM_BUFFER_BINDING, &result.uniform);
        glGetIntegerv(GL_COPY_READ_BUFFER, &result.copy_read);
        glGetIntegerv(GL_COPY_WRITE_BUFFER, &result.copy_write);
        return result;
    }

    GLuint shader(GLenum stage, const char* source) {
        const GLuint result = glCreateShader(stage);
        glShaderSource(result, 1, &source, nullptr);
        glCompileShader(result);
        GLint compiled = GL_FALSE;
        glGetShaderiv(result, GL_COMPILE_STATUS, &compiled);
        if (!compiled) {
            char log[2048] = {};
            glGetShaderInfoLog(result, sizeof(log), nullptr, log);
            std::fprintf(stderr, "Buffer state shader: %s\n", log);
            glDeleteShader(result);
            throw std::runtime_error("buffer state shader compilation failed");
        }
        return result;
    }

    void run(tgfx::GlFeatureTier tier) {
        tgfx::OpenGLRenderDevice device({tier});
        const GLuint vertex = shader(GL_VERTEX_SHADER, R"(
#version 330 core
void main() {
    vec2 positions[3] = vec2[3](vec2(-1.0, -1.0), vec2(3.0, -1.0), vec2(-1.0, 3.0));
    gl_Position = vec4(positions[gl_VertexID], 0.0, 1.0);
}
)");
        const GLuint fragment = shader(GL_FRAGMENT_SHADER, R"(
#version 330 core
out vec4 color;
void main() { color = vec4(0.0, 1.0, 0.0, 1.0); }
)");
        const GLuint program = glCreateProgram();
        glAttachShader(program, vertex);
        glAttachShader(program, fragment);
        glLinkProgram(program);
        GLint linked = GL_FALSE;
        glGetProgramiv(program, GL_LINK_STATUS, &linked);
        require(linked == GL_TRUE, "buffer state program link failed");
        glDeleteShader(vertex);
        glDeleteShader(fragment);

        GLuint texture = 0;
        GLuint framebuffer = 0;
        glGenTextures(1, &texture);
        glBindTexture(GL_TEXTURE_2D, texture);
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, extent, extent, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
        glGenFramebuffers(1, &framebuffer);
        glBindFramebuffer(GL_FRAMEBUFFER, framebuffer);
        glFramebufferTexture2D(GL_FRAMEBUFFER, GL_COLOR_ATTACHMENT0, GL_TEXTURE_2D, texture, 0);
        require(glCheckFramebufferStatus(GL_FRAMEBUFFER) == GL_FRAMEBUFFER_COMPLETE, "test FBO incomplete");
        glViewport(0, 0, extent, extent);
        glDisable(GL_SCISSOR_TEST);
        glDisable(GL_DEPTH_TEST);
        glDisable(GL_CULL_FACE);
        glDisable(GL_BLEND);
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
        glUseProgram(program);

        GLuint vao = 0;
        std::array<GLuint, 5> sentinels{};
        glGenVertexArrays(1, &vao);
        glBindVertexArray(vao);
        glGenBuffers(sentinels.size(), sentinels.data());
        const std::array<GLenum, 5> targets = {
            GL_ELEMENT_ARRAY_BUFFER, GL_ARRAY_BUFFER, GL_UNIFORM_BUFFER,
            GL_COPY_READ_BUFFER, GL_COPY_WRITE_BUFFER,
        };
        const std::array<uint32_t, 3> indices = {0, 1, 2};
        for (size_t i = 0; i < targets.size(); ++i) {
            glBindBuffer(targets[i], sentinels[i]);
            glBufferData(targets[i], sizeof(indices), indices.data(), GL_STATIC_DRAW);
        }
        const Bindings expected_bindings = bindings();

        for (const auto usage : {tgfx::BufferUsage::Index, tgfx::BufferUsage::Vertex, tgfx::BufferUsage::Uniform}) {
            tgfx::BufferDesc desc;
            desc.size = 32;
            desc.usage = usage;
            const auto buffer = device.create_buffer(desc);
            require(bool(buffer), "buffer creation failed");
            require(bindings() == expected_bindings, "create_buffer changed caller bindings");
            std::array<uint8_t, 32> expected{};
            for (size_t i = 0; i < expected.size(); ++i)
                expected[i] = static_cast<uint8_t>(i + 1);
            device.upload_buffer(buffer, expected);
            require(bindings() == expected_bindings, "full upload changed caller bindings");
            const std::array<uint8_t, 5> patch = {91, 92, 93, 94, 95};
            device.upload_buffer(buffer, patch, 7);
            std::copy(patch.begin(), patch.end(), expected.begin() + 7);
            require(bindings() == expected_bindings, "partial upload changed caller bindings");
            std::array<uint8_t, 32> actual{};
            device.read_buffer(buffer, actual);
            require(actual == expected, "partial upload modified untouched bytes or lost payload");
            require(bindings() == expected_bindings, "full read changed caller bindings");
            std::array<uint8_t, 5> partial{};
            device.read_buffer(buffer, partial, 7);
            require(partial == patch, "partial read used wrong offset");
            require(bindings() == expected_bindings, "partial read changed caller bindings");

            for (const uint64_t offset : {uint64_t{30}, std::numeric_limits<uint64_t>::max()}) {
                device.upload_buffer(buffer, patch, offset);
                partial.fill(0xab);
                device.read_buffer(buffer, partial, offset);
                require(std::all_of(partial.begin(), partial.end(), [](uint8_t value) { return value == 0xab; }),
                        "invalid read modified destination");
                require(bindings() == expected_bindings, "invalid transfer changed caller bindings");
            }
            device.upload_buffer(buffer, std::span<const uint8_t>{}, desc.size);
            device.read_buffer(buffer, std::span<uint8_t>{}, desc.size);
            require(bindings() == expected_bindings, "empty transfer changed caller bindings");
            device.read_buffer(buffer, actual);
            require(actual == expected, "invalid or empty upload modified buffer");

            // No VAO or EBO rebind here: the original index stream must still drive this draw.
            glClearColor(1.0f, 0.0f, 0.0f, 1.0f);
            glClear(GL_COLOR_BUFFER_BIT);
            glDrawElements(GL_TRIANGLES, 3, GL_UNSIGNED_INT, nullptr);
            std::array<uint8_t, 4> pixel{};
            glReadPixels(extent / 2, extent / 2, 1, 1, GL_RGBA, GL_UNSIGNED_BYTE, pixel.data());
            require(pixel == std::array<uint8_t, 4>{0, 255, 0, 255}, "indexed draw lost original VAO index stream");
            require(glGetError() == GL_NO_ERROR, "buffer operations or indexed draw generated GL error");
            device.destroy(buffer);
            require(bindings() == expected_bindings, "destroying unrelated buffer changed caller bindings");
        }

        glBindVertexArray(0);
        glDeleteVertexArrays(1, &vao);
        glDeleteBuffers(sentinels.size(), sentinels.data());
        glUseProgram(0);
        glDeleteProgram(program);
        glBindFramebuffer(GL_FRAMEBUFFER, 0);
        glDeleteFramebuffers(1, &framebuffer);
        glDeleteTextures(1, &texture);
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
    context.window = SDL_CreateWindow("OpenGL buffer state", 0, 0, extent, extent,
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
        std::fprintf(stderr, "OpenGL buffer state: %s\n", error.what());
        return 1;
    }
    std::puts("OpenGL buffer state and indexed draw regressions passed");
    return 0;
}
