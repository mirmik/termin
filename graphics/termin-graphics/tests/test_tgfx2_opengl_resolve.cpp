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
    constexpr int destination_width = 11;
    constexpr int destination_height = 8;

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

    struct BlitState {
        GLint read_framebuffer = 0;
        GLint draw_framebuffer = 0;
        std::array<GLint, 4> scissor{};
        GLboolean scissor_enabled = GL_FALSE;
        bool operator==(const BlitState&) const = default;
    };

    BlitState blit_state() {
        BlitState result;
        glGetIntegerv(GL_READ_FRAMEBUFFER_BINDING, &result.read_framebuffer);
        glGetIntegerv(GL_DRAW_FRAMEBUFFER_BINDING, &result.draw_framebuffer);
        glGetIntegerv(GL_SCISSOR_BOX, result.scissor.data());
        result.scissor_enabled = glIsEnabled(GL_SCISSOR_TEST);
        return result;
    }

    bool matches(const float pixel[4], termin::LinearColor expected) {
        return std::abs(pixel[0] - expected.r) < 0.01f && std::abs(pixel[1] - expected.g) < 0.01f &&
               std::abs(pixel[2] - expected.b) < 0.01f && std::abs(pixel[3] - expected.a) < 0.01f;
    }

    void expect_rect(tgfx::OpenGLRenderDevice& device,
                     tgfx::TextureHandle texture,
                     termin::Bounds2i rect,
                     termin::LinearColor inside,
                     termin::LinearColor outside,
                     const char* message) {
        for (int y = 0; y < destination_height; ++y) {
            for (int x = 0; x < destination_width; ++x) {
                float pixel[4] = {};
                require(device.read_pixel_rgba8(texture, x, y, pixel), "blit destination readback failed");
                const bool is_inside = x >= rect.x0 && x < rect.x1 && y >= rect.y0 && y < rect.y1;
                const auto expected = is_inside ? inside : outside;
                if (!matches(pixel, expected)) {
                    std::fprintf(stderr,
                                 "%s at (%d, %d): got %.3f %.3f %.3f %.3f, expected %.3f %.3f %.3f %.3f\n",
                                 message,
                                 x,
                                 y,
                                 pixel[0],
                                 pixel[1],
                                 pixel[2],
                                 pixel[3],
                                 expected.r,
                                 expected.g,
                                 expected.b,
                                 expected.a);
                    throw std::runtime_error(message);
                }
            }
        }
    }

    tgfx::TextureHandle make_texture(tgfx::OpenGLRenderDevice& device,
                                     int texture_width,
                                     int texture_height,
                                     uint32_t samples = 1) {
        tgfx::TextureDesc desc;
        desc.width = static_cast<uint32_t>(texture_width);
        desc.height = static_cast<uint32_t>(texture_height);
        desc.sample_count = samples;
        desc.format = tgfx::PixelFormat::RGBA8_UNorm;
        desc.usage = tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::CopySrc |
                     tgfx::TextureUsage::CopyDst;
        const auto texture = device.create_texture(desc);
        require(bool(texture), "blit texture creation failed");
        return texture;
    }

    void test_blit_to_texture(tgfx::OpenGLRenderDevice& device) {
        const termin::LinearColor black{0, 0, 0, 1};
        const termin::LinearColor red{1, 0, 0, 1};
        const termin::LinearColor green{0, 1, 0, 1};
        const termin::LinearColor blue{0, 0, 1, 1};
        const termin::LinearColor yellow{1, 1, 0, 1};
        const termin::Bounds2i source_top_rect{1, 0, 5, 2};

        const auto source = make_texture(device, width, height);
        const auto second_source = make_texture(device, width, height);
        const auto destination = make_texture(device, destination_width, destination_height);
        device.clear_texture(source, blue, {0, 0, width, height});
        // Leave a one-pixel red guard around the selected source region so
        // linear filtering at the scaled rectangle edge cannot sample blue.
        device.clear_texture(source, red, {0, 0, width, 3});
        device.clear_texture(second_source, green, {0, 0, width, height});
        device.clear_texture(destination, black, {0, 0, destination_width, destination_height});

        GLuint sentinel_framebuffers[2] = {};
        glGenFramebuffers(2, sentinel_framebuffers);
        glBindFramebuffer(GL_READ_FRAMEBUFFER, sentinel_framebuffers[0]);
        glBindFramebuffer(GL_DRAW_FRAMEBUFFER, sentinel_framebuffers[1]);
        glEnable(GL_SCISSOR_TEST);
        glScissor(1, 2, 1, 1);
        const BlitState before = blit_state();

        // This simultaneously exercises top-left source and destination
        // conversion, partial rectangles, asymmetric extents and linear scaling.
        const termin::Bounds2i scaled_destination{2, 3, 8, 7};
        device.blit_to_texture(destination, source, source_top_rect, scaled_destination);
        require(blit_state() == before, "blit_to_texture changed caller framebuffer or scissor state");
        expect_rect(device,
                    destination,
                    scaled_destination,
                    red,
                    black,
                    "scaled partial blit produced unexpected top-left pixels");

        // Model the display presenter's asymmetric multi-viewport composition.
        device.clear_texture(destination, black, {0, 0, destination_width, destination_height});
        const termin::Bounds2i top_left_viewport{0, 0, 3, 2};
        const termin::Bounds2i bottom_right_viewport{6, 5, 11, 8};
        device.blit_to_texture(destination, second_source, {0, 0, width, height}, top_left_viewport);
        device.blit_to_texture(destination, source, source_top_rect, bottom_right_viewport);
        for (int y = 0; y < destination_height; ++y) {
            for (int x = 0; x < destination_width; ++x) {
                float pixel[4] = {};
                require(device.read_pixel_rgba8(destination, x, y, pixel), "viewport composite readback failed");
                const bool in_top_left = x < 3 && y < 2;
                const bool in_bottom_right = x >= 6 && y >= 5;
                const auto expected = in_top_left ? green : (in_bottom_right ? red : black);
                require(matches(pixel, expected), "asymmetric viewport composite produced unexpected pixels");
            }
        }

        // MSAA resolves cannot scale. An equal-size partial resolve remains a
        // valid blit and must use the same public top-left rectangle contract.
        const auto multisample_source = make_texture(device, width, height, 4);
        device.clear_texture(multisample_source, blue, {0, 0, width, height});
        device.clear_texture(multisample_source, yellow, {0, 0, width, 3});
        device.clear_texture(destination, black, {0, 0, destination_width, destination_height});
        const termin::Bounds2i resolve_destination{3, 4, 7, 6};
        device.blit_to_texture(destination, multisample_source, source_top_rect, resolve_destination);
        require(blit_state() == before, "MSAA blit changed caller framebuffer or scissor state");
        expect_rect(device,
                    destination,
                    resolve_destination,
                    yellow,
                    black,
                    "partial MSAA resolve produced unexpected top-left pixels");

        require(glGetError() == GL_NO_ERROR, "blit_to_texture generated a GL error");
        glBindFramebuffer(GL_FRAMEBUFFER, 0);
        glDisable(GL_SCISSOR_TEST);
        glDeleteFramebuffers(2, sentinel_framebuffers);
        device.destroy(multisample_source);
        device.destroy(destination);
        device.destroy(second_source);
        device.destroy(source);
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
        test_blit_to_texture(device);
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
    std::puts("OpenGL MRT resolve and top-left partial blit regressions passed");
    return 0;
}
