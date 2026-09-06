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

    struct State {
        std::array<GLint, 4> viewport{};
        std::array<GLint, 4> scissor{};
        std::array<GLboolean, 4> mask0{};
        std::array<GLboolean, 4> mask1{};
        GLboolean scissor_enabled = GL_FALSE;
        bool operator==(const State&) const = default;
    };

    State state() {
        State result;
        glGetIntegerv(GL_VIEWPORT, result.viewport.data());
        glGetIntegerv(GL_SCISSOR_BOX, result.scissor.data());
        glGetBooleani_v(GL_COLOR_WRITEMASK, 0, result.mask0.data());
        glGetBooleani_v(GL_COLOR_WRITEMASK, 1, result.mask1.data());
        result.scissor_enabled = glIsEnabled(GL_SCISSOR_TEST);
        return result;
    }

    void run(tgfx::GlFeatureTier tier) {
        tgfx::OpenGLRenderDevice device({tier});
        tgfx::TextureDesc desc;
        desc.width = width;
        desc.height = height;
        desc.format = tgfx::PixelFormat::RGBA8_UNorm;
        desc.usage = tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::CopySrc;
        std::array<tgfx::TextureHandle, 2> destinations;
        std::array<tgfx::TextureHandle, 2> sources;
        for (size_t i = 0; i < sources.size(); ++i) {
            desc.sample_count = 1;
            destinations[i] = device.create_texture(desc);
            desc.sample_count = 4;
            sources[i] = device.create_texture(desc);
            require(bool(sources[i]) && bool(destinations[i]), "resolve texture creation failed");
        }

        const std::array<termin::LinearColor, 2> colors = {{{1, 0, 0, 1}, {0, 1, 0, 1}}};
        auto commands = device.create_command_list();
        // A disabled scissor must remain disabled; both tiny and entirely
        // offscreen enabled scissors must leave every resolved pixel intact.
        for (int scenario = 0; scenario < 3; ++scenario) {
            tgfx::RenderPassDesc pass;
            for (size_t i = 0; i < sources.size(); ++i) {
                device.clear_texture(destinations[i], {0, 0, 1, 1}, {0, 0, width, height});
                tgfx::ColorAttachmentDesc attachment;
                attachment.texture = sources[i];
                attachment.resolve_texture = destinations[i];
                attachment.load = tgfx::LoadOp::Clear;
                attachment.clear_color = colors[i];
                pass.colors.push_back(attachment);
            }
            commands->begin();
            commands->begin_render_pass(pass);
            commands->set_viewport(1, 1, 2, 3);
            if (scenario == 2)
                commands->set_scissor(width + 2, height + 3, 1, 1);
            else
                commands->set_scissor(2, 1, 1, 1);
            if (scenario == 0)
                glDisable(GL_SCISSOR_TEST);
            glColorMaski(0, GL_FALSE, GL_TRUE, GL_FALSE, GL_FALSE);
            glColorMaski(1, GL_TRUE, GL_FALSE, GL_TRUE, GL_FALSE);
            const State before = state();
            commands->end_render_pass();
            require(state() == before, "resolve changed viewport, scissor or color masks");
            commands->end();
            device.submit(*commands);

            for (size_t i = 0; i < destinations.size(); ++i) {
                for (int y = 0; y < height; ++y) {
                    for (int x = 0; x < width; ++x) {
                        float pixel[4] = {};
                        require(device.read_pixel_rgba8(destinations[i], x, y, pixel), "resolved pixel read failed");
                        require(std::abs(pixel[0] - colors[i].r) < 0.01f &&
                                    std::abs(pixel[1] - colors[i].g) < 0.01f &&
                                    pixel[2] < 0.01f && pixel[3] > 0.99f,
                                "MRT resolve did not cover the entire destination with the correct source");
                    }
                }
            }
            require(glGetError() == GL_NO_ERROR, "MRT resolve generated a GL error");
        }
        glDisable(GL_SCISSOR_TEST);
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);
        commands.reset();
        for (auto texture : sources)
            device.destroy(texture);
        for (auto texture : destinations)
            device.destroy(texture);
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
    context.window = SDL_CreateWindow("OpenGL MRT resolve", 0, 0, width, height,
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
        std::fprintf(stderr, "OpenGL MRT resolve: %s\n", error.what());
        return 1;
    }
    std::puts("OpenGL MRT resolve scissor and state regressions passed");
    return 0;
}
