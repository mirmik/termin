#include <algorithm>
#include <array>
#include <cmath>
#include <cstdio>
#include <limits>
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
        GLint draw = 0;
        GLint read = 0;
        std::array<GLint, 4> viewport{};
        std::array<GLint, 4> scissor{};
        std::array<GLfloat, 4> clear{};
        std::array<GLboolean, 4> mask0{};
        std::array<GLboolean, 4> mask1{};
        GLboolean scissor_enabled = GL_FALSE;
        bool operator==(const State&) const = default;
    };

    State state() {
        State result;
        glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &result.draw);
        glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &result.read);
        glGetIntegerv(GL_VIEWPORT, result.viewport.data());
        glGetIntegerv(GL_SCISSOR_BOX, result.scissor.data());
        glGetFloatv(GL_COLOR_CLEAR_VALUE, result.clear.data());
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
        const auto texture = device.create_texture(desc);
        require(bool(texture), "texture creation failed");
        const std::array<termin::Bounds2i, 10> rectangles = {{
            {1, 0, 4, 2}, {0, 0, 1, 1}, {-3, 2, 3, 9},
            {-10, -10, 30, 30}, {2, 2, 2, 4}, {5, 4, 2, 1},
            {20, 20, 30, 30}, {-10, -10, -1, -1},
            {std::numeric_limits<int>::min(), std::numeric_limits<int>::min(),
             std::numeric_limits<int>::max(), std::numeric_limits<int>::max()},
            {std::numeric_limits<int>::max(), std::numeric_limits<int>::max(),
             std::numeric_limits<int>::min(), std::numeric_limits<int>::min()},
        }};
        GLuint fbos[2] = {};
        glGenFramebuffers(2, fbos);
        for (bool enabled : {false, true}) {
            for (const auto& rect : rectangles) {
                device.clear_texture(texture, {1, 0, 0, 1}, {0, 0, width, height});
                glBindFramebuffer(GL_DRAW_FRAMEBUFFER, fbos[0]);
                glBindFramebuffer(GL_READ_FRAMEBUFFER, fbos[1]);
                glViewport(2, 3, 11, 13);
                glScissor(4, 1, 1, 1);
                if (enabled)
                    glEnable(GL_SCISSOR_TEST);
                else
                    glDisable(GL_SCISSOR_TEST);
                glClearColor(0.25f, 0.5f, 0.75f, 0.125f);
                glColorMaski(0, GL_FALSE, GL_TRUE, GL_FALSE, GL_FALSE);
                glColorMaski(1, GL_TRUE, GL_FALSE, GL_TRUE, GL_FALSE);
                const State before = state();
                device.clear_texture(texture, {0, 1, 0, 1}, rect);
                require(state() == before, "clear_texture changed caller GL state");
                for (int y = 0; y < height; ++y) {
                    for (int x = 0; x < width; ++x) {
                        float pixel[4] = {};
                        require(device.read_pixel_rgba8(texture, x, y, pixel), "pixel read failed");
                        const bool inside = x >= rect.x0 && x < rect.x1 && y >= rect.y0 && y < rect.y1;
                        require(std::abs(pixel[0] - (inside ? 0.0f : 1.0f)) < 0.01f &&
                                    std::abs(pixel[1] - (inside ? 1.0f : 0.0f)) < 0.01f &&
                                    pixel[2] < 0.01f && pixel[3] > 0.99f,
                                "clear_texture rectangle pixels differ");
                    }
                }
                require(glGetError() == GL_NO_ERROR, "clear_texture generated a GL error");
            }
        }
        glBindFramebuffer(GL_FRAMEBUFFER, 0);
        glDeleteFramebuffers(2, fbos);
        glDisable(GL_SCISSOR_TEST);
        glColorMask(GL_TRUE, GL_TRUE, GL_TRUE, GL_TRUE);

        desc.sample_count = 4;
        const auto multisample = device.create_texture(desc);
        require(bool(multisample), "MSAA texture creation failed");
        device.clear_texture(multisample, {1, 0, 0, 1}, {0, 0, width, height});
        device.clear_texture(multisample, {0, 1, 0, 1}, {1, 0, 4, 2});
        auto commands = device.create_command_list();
        commands->begin();
        tgfx::RenderPassDesc pass;
        tgfx::ColorAttachmentDesc attachment;
        attachment.texture = multisample;
        attachment.resolve_texture = texture;
        attachment.load = tgfx::LoadOp::Load;
        pass.colors.push_back(attachment);
        commands->begin_render_pass(pass);
        commands->end_render_pass();
        commands->end();
        device.submit(*commands);
        for (int y = 0; y < height; ++y) {
            for (int x = 0; x < width; ++x) {
                float pixel[4] = {};
                require(device.read_pixel_rgba8(texture, x, y, pixel), "MSAA resolved pixel read failed");
                const bool inside = x >= 1 && x < 4 && y < 2;
                require(std::abs(pixel[0] - (inside ? 0.0f : 1.0f)) < 0.01f &&
                            std::abs(pixel[1] - (inside ? 1.0f : 0.0f)) < 0.01f &&
                            pixel[2] < 0.01f && pixel[3] > 0.99f,
                        "MSAA clear rectangle resolved pixels differ");
            }
        }
        require(glGetError() == GL_NO_ERROR, "MSAA clear generated a GL error");
        commands.reset();
        device.destroy(multisample);
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
    context.window = SDL_CreateWindow("OpenGL clear texture", 0, 0, width, height,
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
        std::fprintf(stderr, "OpenGL clear texture: %s\n", error.what());
        return 1;
    }
    std::puts("OpenGL clear texture rectangle and state regressions passed");
    return 0;
}
