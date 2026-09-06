#include <array>
#include <cstdio>
#include <cstring>
#include <limits>
#include <stdexcept>
#include <vector>

#define SDL_MAIN_HANDLED
#include <SDL.h>
#include "tgfx2/i_command_list.hpp"
#include "tgfx2/opengl/opengl_render_device.hpp"

namespace {
    constexpr uint32_t width = 7;
    constexpr uint32_t height = 5;
    constexpr std::array<GLenum, 10> state_names = {
        GL_UNPACK_ALIGNMENT, GL_UNPACK_ROW_LENGTH, GL_UNPACK_IMAGE_HEIGHT,
        GL_UNPACK_SKIP_ROWS, GL_UNPACK_SKIP_PIXELS, GL_UNPACK_SKIP_IMAGES,
        GL_UNPACK_SWAP_BYTES, GL_UNPACK_LSB_FIRST, GL_PIXEL_UNPACK_BUFFER_BINDING,
        GL_TEXTURE_BINDING_2D,
    };
    using State = std::array<GLint, state_names.size()>;

    void require(bool ok, const char* message) {
        if (!ok)
            throw std::runtime_error(message);
    }

    State state() {
        State result{};
        for (size_t i = 0; i < state_names.size(); ++i)
            glGetIntegerv(state_names[i], &result[i]);
        return result;
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

    struct Format {
        tgfx::PixelFormat format;
        GLenum channels;
        GLenum type;
        uint32_t bytes;
    };

    std::vector<uint8_t> payload(size_t pixels, const Format& format, unsigned seed) {
        std::vector<uint8_t> bytes(pixels * format.bytes);
        if (format.type == GL_HALF_FLOAT) {
            // Exactly representable, finite half values: byte swapping changes them.
            for (size_t i = 0; i < pixels; ++i) {
                const uint16_t value = static_cast<uint16_t>(0x3000 + ((i + seed) % 31) * 17);
                std::memcpy(bytes.data() + i * 2, &value, sizeof(value));
            }
        } else {
            for (size_t i = 0; i < bytes.size(); ++i)
                bytes[i] = static_cast<uint8_t>(1 + (i * 37 + seed) % 253);
        }
        return bytes;
    }

    void check_pixels(tgfx::OpenGLRenderDevice& device, tgfx::TextureHandle texture,
                      const Format& format, const std::vector<uint8_t>& expected) {
        const State before = state();
        glBindBuffer(GL_PIXEL_PACK_BUFFER, 0);
        glPixelStorei(GL_PACK_ALIGNMENT, 1);
        glPixelStorei(GL_PACK_ROW_LENGTH, 0);
        glPixelStorei(GL_PACK_IMAGE_HEIGHT, 0);
        glPixelStorei(GL_PACK_SKIP_ROWS, 0);
        glPixelStorei(GL_PACK_SKIP_PIXELS, 0);
        glPixelStorei(GL_PACK_SKIP_IMAGES, 0);
        glPixelStorei(GL_PACK_SWAP_BYTES, GL_FALSE);
        glPixelStorei(GL_PACK_LSB_FIRST, GL_FALSE);
        glBindTexture(GL_TEXTURE_2D, device.get_texture(texture)->gl_id);
        std::vector<uint8_t> actual(expected.size());
        glGetTexImage(GL_TEXTURE_2D, 0, format.channels, format.type, actual.data());
        glBindTexture(GL_TEXTURE_2D, static_cast<GLuint>(before.back()));
        require(glGetError() == GL_NO_ERROR, "native upload readback generated GL error");
        const size_t row_bytes = width * format.bytes;
        for (uint32_t y = 0; y < height; ++y)
            require(std::memcmp(actual.data() + (height - 1 - y) * row_bytes,
                                expected.data() + y * row_bytes, row_bytes) == 0,
                    "uploaded native pixels differ from top-left tightly packed payload");
        require(state() == before, "pixel verification changed upload state");
    }

    template <class Upload>
    void invalid_upload(Upload upload, const State& expected_state) {
        try {
            upload();
        } catch (const std::exception&) {
            // Both explicit rejection forms are permitted by the void upload API.
        }
        require(state() == expected_state, "rejected upload changed caller GL state");
        require(glGetError() == GL_NO_ERROR, "rejected upload reached GL with invalid parameters");
    }

    void run(tgfx::GlFeatureTier tier) {
        tgfx::OpenGLRenderDevice device({tier});
        const std::array<Format, 4> formats = {{
            {tgfx::PixelFormat::R8_UNorm, GL_RED, GL_UNSIGNED_BYTE, 1},
            {tgfx::PixelFormat::RG8_UNorm, GL_RG, GL_UNSIGNED_BYTE, 2},
            {tgfx::PixelFormat::RGB8_UNorm, GL_RGB, GL_UNSIGNED_BYTE, 3},
            {tgfx::PixelFormat::R16F, GL_RED, GL_HALF_FLOAT, 2},
        }};
        GLuint sentinel_texture = 0;
        GLuint sentinel_buffer = 0;
        glGenTextures(1, &sentinel_texture);
        glGenBuffers(1, &sentinel_buffer);
        for (const auto& format : formats) {
            tgfx::TextureDesc desc;
            desc.width = width;
            desc.height = height;
            desc.format = format.format;
            desc.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::CopyDst;
            const auto texture = device.create_texture(desc);
            require(bool(texture), "upload texture creation failed");
            glBindTexture(GL_TEXTURE_2D, sentinel_texture);
            glBindBuffer(GL_PIXEL_UNPACK_BUFFER, sentinel_buffer);
            glBufferData(GL_PIXEL_UNPACK_BUFFER, 4096, nullptr, GL_STATIC_DRAW);
            glPixelStorei(GL_UNPACK_ALIGNMENT, 8);
            glPixelStorei(GL_UNPACK_ROW_LENGTH, 13);
            glPixelStorei(GL_UNPACK_IMAGE_HEIGHT, 17);
            glPixelStorei(GL_UNPACK_SKIP_ROWS, 2);
            glPixelStorei(GL_UNPACK_SKIP_PIXELS, 3);
            glPixelStorei(GL_UNPACK_SKIP_IMAGES, 1);
            glPixelStorei(GL_UNPACK_SWAP_BYTES, GL_TRUE);
            glPixelStorei(GL_UNPACK_LSB_FIRST, GL_TRUE);
            const State before = state();
            require(glGetError() == GL_NO_ERROR, "upload state setup generated GL error");
            auto expected = payload(width * height, format, 9);
            device.upload_texture(texture, expected);
            require(state() == before, "full upload failed to restore caller GL state");
            require(glGetError() == GL_NO_ERROR, "full upload generated GL error");
            check_pixels(device, texture, format, expected);

            constexpr uint32_t x = 2, y = 1, w = 3, h = 2;
            const auto region = payload(w * h, format, 119);
            device.upload_texture_region(texture, x, y, w, h, region);
            require(state() == before, "region upload failed to restore caller GL state");
            require(glGetError() == GL_NO_ERROR, "region upload generated GL error");
            for (uint32_t row = 0; row < h; ++row)
                std::memcpy(expected.data() + ((y + row) * width + x) * format.bytes,
                            region.data() + row * w * format.bytes, w * format.bytes);
            check_pixels(device, texture, format, expected);

            const std::span<const uint8_t> short_full(expected.data(), expected.size() - 1);
            const std::span<const uint8_t> short_region(region.data(), region.size() - 1);
            invalid_upload([&] { device.upload_texture(texture, short_full); }, before);
            check_pixels(device, texture, format, expected);
            invalid_upload([&] { device.upload_texture_region(texture, x, y, w, h, short_region); }, before);
            check_pixels(device, texture, format, expected);
            for (uint32_t mip : {1u, 32u, std::numeric_limits<uint32_t>::max()}) {
                invalid_upload([&] { device.upload_texture(texture, expected, mip); }, before);
                invalid_upload([&] { device.upload_texture_region(texture, 0, 0, 1, 1, region, mip); }, before);
            }
            const uint32_t extreme = std::numeric_limits<uint32_t>::max();
            for (const auto& rect : std::array<std::array<uint32_t, 4>, 5>{{
                     {6, 0, 3, 2}, {0, 4, 3, 2}, {extreme, 0, 3, 2},
                     {0, extreme, 3, 2}, {1, 1, extreme, extreme}}}) {
                invalid_upload([&] {
                    device.upload_texture_region(texture, rect[0], rect[1], rect[2], rect[3], region);
                }, before);
            }
            check_pixels(device, texture, format, expected);
            glBindBuffer(GL_PIXEL_UNPACK_BUFFER, 0);
            device.destroy(texture);
        }

        tgfx::TextureDesc msaa_desc;
        msaa_desc.width = width;
        msaa_desc.height = height;
        msaa_desc.sample_count = 4;
        msaa_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
        msaa_desc.usage = tgfx::TextureUsage::ColorAttachment;
        const auto msaa = device.create_texture(msaa_desc);
        require(bool(msaa), "MSAA upload rejection texture creation failed");
        device.clear_texture(msaa, {0, 1, 0, 1}, {0, 0, width, height});
        const auto bytes = payload(width * height, {tgfx::PixelFormat::RGBA8_UNorm, GL_RGBA, GL_UNSIGNED_BYTE, 4}, 7);
        const State before = state();
        invalid_upload([&] { device.upload_texture(msaa, bytes); }, before);
        invalid_upload([&] { device.upload_texture_region(msaa, 0, 0, width, height, bytes); }, before);
        msaa_desc.sample_count = 1;
        msaa_desc.usage = tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::CopySrc;
        const auto resolved = device.create_texture(msaa_desc);
        require(bool(resolved), "MSAA upload rejection resolve texture creation failed");
        auto commands = device.create_command_list();
        commands->begin();
        tgfx::RenderPassDesc pass;
        tgfx::ColorAttachmentDesc attachment;
        attachment.texture = msaa;
        attachment.resolve_texture = resolved;
        attachment.load = tgfx::LoadOp::Load;
        pass.colors.push_back(attachment);
        commands->begin_render_pass(pass);
        commands->end_render_pass();
        commands->end();
        device.submit(*commands);
        for (uint32_t y = 0; y < height; ++y) {
            for (uint32_t x = 0; x < width; ++x) {
                float pixel[4] = {};
                require(device.read_pixel_rgba8(resolved, x, y, pixel), "MSAA upload rejection readback failed");
                require(pixel[0] == 0 && pixel[1] == 1 && pixel[2] == 0 && pixel[3] == 1,
                        "rejected MSAA upload changed texture pixels");
            }
        }
        require(glGetError() == GL_NO_ERROR, "MSAA upload rejection verification generated GL error");
        commands.reset();
        device.destroy(resolved);
        device.destroy(msaa);
        glBindTexture(GL_TEXTURE_2D, 0);
        glDeleteTextures(1, &sentinel_texture);
        glDeleteBuffers(1, &sentinel_buffer);
        for (size_t i = 0; i < 8; ++i)
            glPixelStorei(state_names[i], i == 0 ? 4 : 0);
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
    context.window = SDL_CreateWindow("OpenGL uploads", 0, 0, width, height,
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
        std::fprintf(stderr, "OpenGL uploads: %s\n", error.what());
        return 1;
    }
    std::puts("OpenGL tightly packed upload and state regressions passed");
    return 0;
}
