#include <array>
#include <cstdio>
#include <stdexcept>

#define SDL_MAIN_HANDLED
#include <SDL.h>
#include "tgfx2/opengl/opengl_render_device.hpp"

namespace {
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

    void run(tgfx::GlFeatureTier tier) {
        tgfx::BufferDesc buffer_desc;
        buffer_desc.size = 64;
        buffer_desc.usage = tgfx::BufferUsage::Vertex;
        tgfx::TextureDesc texture_desc;
        texture_desc.width = 4;
        texture_desc.height = 4;
        texture_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
        texture_desc.usage = tgfx::TextureUsage::Sampled;

        GLuint borrowed_buffer = 0;
        GLuint borrowed_texture = 0;
        GLuint owned_buffer = 0;
        GLuint owned_texture = 0;
        GLuint vertex_ring = 0;
        GLuint uniform_ring = 0;
        {
            tgfx::OpenGLRenderDevice device({tier});
            glGenBuffers(1, &borrowed_buffer);
            glBindBuffer(GL_ARRAY_BUFFER, borrowed_buffer);
            glBufferData(GL_ARRAY_BUFFER, 64, nullptr, GL_STATIC_DRAW);
            glBindBuffer(GL_ARRAY_BUFFER, 0);
            glGenTextures(1, &borrowed_texture);
            glBindTexture(GL_TEXTURE_2D, borrowed_texture);
            glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA8, 4, 4, 0, GL_RGBA, GL_UNSIGNED_BYTE, nullptr);
            glBindTexture(GL_TEXTURE_2D, 0);

            const auto buffer_wrapper = device.register_external_buffer(borrowed_buffer, buffer_desc);
            const auto texture_wrapper = device.register_external_texture(borrowed_texture, texture_desc);
            device.destroy(buffer_wrapper);
            device.destroy(texture_wrapper);
            require(glIsBuffer(borrowed_buffer), "explicit destroy deleted borrowed buffer");
            require(glIsTexture(borrowed_texture), "explicit destroy deleted borrowed texture");
            require(device.get_buffer(buffer_wrapper) == nullptr, "borrowed buffer wrapper survived destroy");
            require(device.get_texture(texture_wrapper) == nullptr, "borrowed texture wrapper survived destroy");
            device.register_external_buffer(borrowed_buffer, buffer_desc);
            device.register_external_texture(borrowed_texture, texture_desc);

            const auto buffer = device.create_buffer(buffer_desc);
            const auto texture = device.create_texture(texture_desc);
            require(bool(buffer) && bool(texture), "owned resource creation failed");
            owned_buffer = device.get_buffer(buffer)->gl_id;
            owned_texture = device.get_texture(texture)->gl_id;
            device.destroy(buffer);
            device.destroy(texture);
            require(!glIsBuffer(owned_buffer), "explicit destroy retained owned buffer");
            require(!glIsTexture(owned_texture), "explicit destroy retained owned texture");
            const auto final_buffer = device.create_buffer(buffer_desc);
            const auto final_texture = device.create_texture(texture_desc);
            require(bool(final_buffer) && bool(final_texture), "final owned resource creation failed");
            owned_buffer = device.get_buffer(final_buffer)->gl_id;
            owned_texture = device.get_texture(final_texture)->gl_id;

            // A borrowed alias must not delete a pool-owned ring or reset its
            // internal handle. Destroying the owning handle must allow reuse.
            const auto vertex_handle = device.transient_vertex_buffer();
            vertex_ring = device.get_buffer(vertex_handle)->gl_id;
            device.destroy(device.register_external_buffer(vertex_ring, buffer_desc));
            require(glIsBuffer(vertex_ring), "borrowed ring alias deleted its owner");
            require(device.transient_vertex_buffer().id == vertex_handle.id,
                    "borrowed ring alias reset owning handle");
            device.destroy(vertex_handle);
            require(!glIsBuffer(vertex_ring), "destroy retained vertex ring");
            std::array<float, 4> data = {1, 2, 3, 4};
            require(device.transient_vertex_write(data.data(), sizeof(data)) == 0,
                    "vertex ring failed to recreate after explicit destruction");
            vertex_ring = device.get_buffer(device.transient_vertex_buffer())->gl_id;

            const auto uniform_handle = device.ring_ubo_handle();
            require(bool(uniform_handle), "initial uniform ring missing");
            uniform_ring = device.get_buffer(uniform_handle)->gl_id;
            device.destroy(uniform_handle);
            require(!glIsBuffer(uniform_ring), "destroy retained uniform ring");
            uint32_t offset = 99;
            require(device.ring_ubo_write(data.data(), sizeof(data), offset) && offset == 0,
                    "uniform ring failed to recreate after explicit destruction");
            uniform_ring = device.get_buffer(device.ring_ubo_handle())->gl_id;
            require(glGetError() == GL_NO_ERROR, "resource lifecycle produced a GL error");
        }
        require(glIsBuffer(borrowed_buffer), "device shutdown deleted borrowed buffer");
        require(glIsTexture(borrowed_texture), "device shutdown deleted borrowed texture");
        require(!glIsBuffer(owned_buffer), "device shutdown retained owned buffer");
        require(!glIsTexture(owned_texture), "device shutdown retained owned texture");
        require(!glIsBuffer(vertex_ring), "device shutdown retained vertex ring");
        require(!glIsBuffer(uniform_ring), "device shutdown retained uniform ring");
        require(glGetError() == GL_NO_ERROR, "device shutdown produced a GL error");
        glDeleteBuffers(1, &borrowed_buffer);
        glDeleteTextures(1, &borrowed_texture);
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
    context.window = SDL_CreateWindow("OpenGL resource ownership", 0, 0, 16, 16,
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
        std::fprintf(stderr, "OpenGL resource ownership: %s\n", error.what());
        return 1;
    }
    std::puts("OpenGL borrowed and owned resource lifecycle regressions passed");
    return 0;
}
