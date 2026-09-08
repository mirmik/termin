#include "tgfx2/canvas2d_renderer.hpp"
#include "tgfx2/descriptors.hpp"
#include "tgfx2/device_factory.hpp"
#include "tgfx2/i_render_device.hpp"
#include "tgfx2/pipeline_cache.hpp"
#include "tgfx2/render_context.hpp"
#include "tgfx2/tc_shader_bridge.hpp"

#include <array>
#include <cassert>
#include <chrono>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <exception>
#include <filesystem>
#include <memory>
#include <string>
#include <system_error>
#include <vector>

extern "C" {
#include <tgfx/resources/tc_shader_registry.h>
}

namespace {

    constexpr std::uint32_t width = 64;
    constexpr std::uint32_t height = 64;

    class NoFonts final : public tgfx::DrawResourceResolver2D {
    public:
        tgfx::FontAtlas* resolve_font(tgfx::FontHandle) override {
            return nullptr;
        }
    };

    class RetainedProbe final : public tgfx::RetainedDrawBatch2D {
    public:
        bool called = false;
        tgfx::RetainedDrawState2D state{};

        bool draw(tgfx::RenderContext2&, const tgfx::RetainedDrawState2D& value) override {
            called = true;
            state = value;
            return true;
        }
    };

    struct TempDirectory {
        std::filesystem::path path;

        ~TempDirectory() {
            std::error_code error;
            std::filesystem::remove_all(path, error);
        }
    };

    void configure_shader_tools(const char* executable) {
        std::error_code error;
        const auto executable_path = std::filesystem::absolute(executable, error);
        if (!error) {
            const auto compiler = executable_path.parent_path() / "termin_shaderc";
            if (std::filesystem::is_regular_file(compiler, error)) {
                termin::tgfx2_set_shader_compiler_path(compiler.string().c_str());
            }
        }
    }

    bool red(const float pixel[4]) {
        return pixel[0] > 0.8f && pixel[1] < 0.1f && pixel[2] < 0.1f && pixel[3] > 0.9f;
    }

    bool clear(const float pixel[4]) {
        return pixel[0] < 0.05f && pixel[1] < 0.05f && pixel[2] < 0.05f && pixel[3] > 0.9f;
    }

    bool clip_regressions(tgfx::IRenderDevice& device,
                          tgfx::RenderContext2& context,
                          tgfx::Canvas2DRenderer& canvas,
                          NoFonts& resources,
                          tgfx::TextureHandle target) {
        using Pixels = std::vector<float>;
        const termin::LinearColor black{0, 0, 0, 1};
        const auto render = [&](tgfx::DrawList2DBuilder& builder, Pixels& pixels) {
            auto list = builder.freeze();
            if (!list)
                return false;
            context.begin_frame();
            context.begin_pass(target, {}, &black, 1.0f, false);
            canvas.begin(context, width, height);
            const bool executed = canvas.execute(*list, resources);
            canvas.end();
            context.end_pass();
            context.end_frame();
            device.wait_idle();
            pixels.resize(width * height * 4);
            return device.read_texture_rgba_float(target, pixels.data()) && executed;
        };
        const auto pixel = [](const Pixels& p, unsigned x, unsigned y) {
            return p.data() + (y * width + x) * 4;
        };
        const auto same = [](const Pixels& a, const Pixels& b) {
            if (a.size() != b.size())
                return false;
            for (size_t i = 0; i < a.size(); ++i)
                if (std::abs(a[i] - b[i]) > 0.01f)
                    return false;
            return true;
        };
        bool passed = true;
        const auto check = [&](bool condition, const char* name) {
            if (!condition)
                std::fprintf(stderr, "DrawList2D clip regression failed: %s\n", name);
            passed &= condition;
        };

        tgfx::TextureDesc checker_desc;
        checker_desc.width = checker_desc.height = 4;
        checker_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
        checker_desc.usage = tgfx::TextureUsage::Sampled | tgfx::TextureUsage::CopyDst;
        const auto checker = device.create_texture(checker_desc);
        if (!checker)
            return false;
        std::array<uint8_t, 4 * 4 * 4> rgba{};
        for (unsigned y = 0; y < 4; ++y) {
            for (unsigned x = 0; x < 4; ++x) {
                const size_t offset = (y * 4 + x) * 4;
                const bool white = (x + y) % 2 == 0;
                rgba[offset] = rgba[offset + 1] = white ? 255 : 0;
                rgba[offset + 2] = rgba[offset + 3] = 255;
            }
        }
        device.upload_texture(checker, rgba);
        Pixels single, deep;
        for (unsigned depth : {1u, 32u}) {
            tgfx::DrawList2DBuilder builder;
            for (unsigned i = 0; i < depth; ++i)
                assert(builder.push_clip_rect({8.25f, 9.25f, 37.5f, 35.5f}));
            assert(builder.image(
                checker, {0, 0, 64, 64}, {0, 0, 1, 1}, {1, 1, 1, 1}, tgfx::DrawTextureSampling2D::Nearest));
            for (unsigned i = 0; i < depth; ++i)
                assert(builder.pop_clip());
            check(render(builder, depth == 1 ? single : deep), "fractional checker executes");
        }
        check(same(single, deep), "1 and 32 nested clips produce identical pixels");
        if (single.size() == width * height * 4) {
            bool expected_uv = true;
            for (unsigned y = 0; y < height; ++y) {
                for (unsigned x = 0; x < width; ++x) {
                    const auto* p = pixel(single, x, y);
                    const bool inside =
                        x + 0.5f >= 8.25f && x + 0.5f < 45.75f && y + 0.5f >= 9.25f && y + 0.5f < 44.75f;
                    if (!inside)
                        expected_uv &= clear(p);
                    else {
                        const bool white = (x / 16 + y / 16) % 2 == 0;
                        expected_uv &= std::abs(p[0] - (white ? 1.0f : 0.0f)) < 0.02f &&
                                       std::abs(p[1] - (white ? 1.0f : 0.0f)) < 0.02f && p[2] > 0.98f && p[3] > 0.98f;
                    }
                }
            }
            check(expected_uv, "fractional clipping preserves checker UV and pixel boundaries");
        }
        device.destroy(checker);

        tgfx::DrawList2DBuilder empty;
        assert(empty.push_clip_rect({4, 4, 16, 16}));
        assert(empty.push_clip_rect({40, 40, 8, 8}));
        assert(empty.rect({0, 0, 64, 64}, tgfx::FillPaint{{1, 0, 0, 1}}));
        assert(empty.pop_clip());
        assert(empty.rect({4, 4, 4, 4}, tgfx::FillPaint{{0, 1, 0, 1}}));
        assert(empty.pop_clip());
        assert(empty.rect({40, 40, 4, 4}, tgfx::FillPaint{{0, 0, 1, 1}}));
        Pixels empty_pixels;
        check(render(empty, empty_pixels), "empty intersection and pop execute");
        if (empty_pixels.size() == width * height * 4) {
            const auto* green = pixel(empty_pixels, 5, 5);
            const auto* blue = pixel(empty_pixels, 41, 41);
            check(green[1] > 0.98f && green[0] < 0.02f && blue[2] > 0.98f && blue[0] < 0.02f &&
                      clear(pixel(empty_pixels, 10, 10)) && clear(pixel(empty_pixels, 46, 46)) &&
                      clear(pixel(empty_pixels, 30, 30)),
                  "empty clip draws nothing and pop restores parent");
        }

        const auto hole_path = [] {
            tgfx::Path2f path;
            assert(path.move_to({8, 8}));
            assert(path.line_to({56, 8}));
            assert(path.line_to({56, 56}));
            assert(path.line_to({8, 56}));
            assert(path.close());
            assert(path.move_to({24, 24}));
            assert(path.line_to({40, 24}));
            assert(path.line_to({40, 40}));
            assert(path.line_to({24, 40}));
            assert(path.close());
            return path;
        };
        Pixels rect_first, hole_first;
        for (bool rect_outer : {true, false}) {
            tgfx::DrawList2DBuilder builder;
            if (rect_outer)
                assert(builder.push_clip_rect({12, 12, 40, 40}));
            assert(builder.push_clip(hole_path(), tgfx::FillRule::EvenOdd));
            if (!rect_outer)
                assert(builder.push_clip_rect({12, 12, 40, 40}));
            assert(builder.rect({0, 0, 64, 64}, tgfx::FillPaint{{1, 0, 0, 1}}));
            assert(builder.pop_clip());
            assert(builder.pop_clip());
            check(render(builder, rect_outer ? rect_first : hole_first), "mixed clip nesting executes");
        }
        check(same(rect_first, hole_first), "rect and generic hole intersection commutes");
        if (rect_first.size() == width * height * 4)
            check(clear(pixel(rect_first, 32, 32)) && red(pixel(rect_first, 20, 20)) &&
                      clear(pixel(rect_first, 9, 20)) && clear(pixel(rect_first, 54, 20)),
                  "generic hole and rectangle both remain effective");

        tgfx::Path2f bowtie;
        assert(bowtie.move_to({8, 8}));
        assert(bowtie.line_to({56, 56}));
        assert(bowtie.line_to({8, 56}));
        assert(bowtie.line_to({56, 8}));
        assert(bowtie.close());
        tgfx::DrawList2DBuilder bow;
        auto probe = std::make_shared<RetainedProbe>();
        assert(bow.push_clip(std::move(bowtie), tgfx::FillRule::EvenOdd));
        assert(bow.retained_batch(probe));
        assert(bow.rect({0, 0, 64, 64}, tgfx::FillPaint{{1, 0, 0, 1}}));
        assert(bow.pop_clip());
        Pixels bow_pixels;
        const bool bow_executed = render(bow, bow_pixels);
        // The existing general tessellator may reject self-intersections.
        // Either explicit rejection or a generic clip is valid; an AABB is not.
        check(!bow_executed || (probe->called && probe->state.unsupported_clip),
              "bowtie corners must not be classified as an axis rectangle");
        return passed;
    }

    int run(const char* executable) {
        const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
        TempDirectory artifacts{std::filesystem::temp_directory_path() /
                                ("termin-draw-list2d-" + std::to_string(unique))};
        std::filesystem::create_directories(artifacts.path);
#ifdef _WIN32
        _putenv_s("TERMIN_BUILTIN_SHADER_ROOT", TGFX2_BUILTIN_SHADER_ROOT);
#else
        setenv("TERMIN_BUILTIN_SHADER_ROOT", TGFX2_BUILTIN_SHADER_ROOT, 1);
#endif
        configure_shader_tools(executable);
        termin::tgfx2_set_shader_artifact_root(artifacts.path.string().c_str());
        termin::tgfx2_set_shader_cache_root((artifacts.path / "cache").string().c_str());
        termin::tgfx2_set_shader_dev_compile_enabled(true);

        std::unique_ptr<tgfx::IRenderDevice> device;
        try {
            device = tgfx::create_device(tgfx::BackendType::Vulkan);
        } catch (const std::exception& error) {
            std::fprintf(stderr, "Vulkan device unavailable: %s\n", error.what());
            return 1;
        }

        tgfx::TextureDesc target_desc;
        target_desc.width = width;
        target_desc.height = height;
        target_desc.format = tgfx::PixelFormat::RGBA8_UNorm;
        target_desc.usage = tgfx::TextureUsage::ColorAttachment | tgfx::TextureUsage::CopySrc;
        const auto target = device->create_texture(target_desc);
        if (!target)
            return 2;

        tgfx::DrawList2DBuilder builder;
        constexpr float pi = 3.14159265358979323846f;
        assert(builder.push_transform(termin::Affine2f::translation(32, 32) * termin::Affine2f::rotation(pi * 0.25f)));
        assert(builder.push_clip_rect({-16, -16, 32, 32}));
        tgfx::Path2f ring;
        assert(ring.move_to({-20, -20}));
        assert(ring.line_to({20, -20}));
        assert(ring.line_to({20, 20}));
        assert(ring.line_to({-20, 20}));
        assert(ring.close());
        assert(ring.move_to({-6, -6}));
        assert(ring.line_to({6, -6}));
        assert(ring.line_to({6, 6}));
        assert(ring.line_to({-6, 6}));
        assert(ring.close());
        assert(builder.push_clip(std::move(ring), tgfx::FillRule::EvenOdd));
        assert(builder.rect({-100, -100, 200, 200}, tgfx::FillPaint{{1, 0, 0, 1}}));
        assert(builder.pop_clip());
        assert(builder.pop_clip());
        assert(builder.pop_transform());
        assert(builder.rounded_rect({48, 4, 8, 24}, 4, tgfx::FillPaint{{0, 1, 0, 1}}));
        assert(builder.rounded_rect({36, 52, 24, 8}, 4, tgfx::FillPaint{{0, 1, 0, 1}}));
        auto retained_probe = std::make_shared<RetainedProbe>();
        assert(builder.push_opacity(0.4f));
        assert(builder.push_clip_rect({2, 3, 20, 21}));
        assert(builder.retained_batch(retained_probe));
        assert(builder.pop_clip());
        assert(builder.pop_opacity());
        auto list = builder.freeze();
        assert(list);

        tgfx::PipelineCache cache(*device);
        tgfx::RenderContext2 context(*device, cache);
        tgfx::Canvas2DRenderer canvas;
        NoFonts resources;
        const termin::LinearColor black{0, 0, 0, 1};
        context.begin_frame();
        context.begin_pass(target, {}, &black, 1.0f, false);
        canvas.begin(context, static_cast<int>(width), static_cast<int>(height));
        const bool executed = canvas.execute(*list, resources);
        canvas.draw_rect(0, 0, 4, 4, {0, 0, 1, 1});
        canvas.end();
        context.end_pass();
        context.end_frame();
        device->wait_idle();

        float center[4]{};
        float inside_tip[4]{};
        float outside_corner[4]{};
        float immediate_control[4]{};
        float vertical_capsule[4]{};
        float horizontal_capsule[4]{};
        const bool read = device->read_pixel_rgba8(target, 32, 32, center) &&
                          device->read_pixel_rgba8(target, 32, 16, inside_tip) &&
                          device->read_pixel_rgba8(target, 10, 10, outside_corner) &&
                          device->read_pixel_rgba8(target, 1, 1, immediate_control) &&
                          device->read_pixel_rgba8(target, 52, 16, vertical_capsule) &&
                          device->read_pixel_rgba8(target, 48, 56, horizontal_capsule);
        const bool blue_control = immediate_control[0] < 0.1f && immediate_control[1] < 0.1f &&
                                  immediate_control[2] > 0.8f && immediate_control[3] > 0.9f;
        const auto green = [](const float pixel[4]) {
            return pixel[0] < 0.1f && pixel[1] > 0.8f && pixel[2] < 0.1f && pixel[3] > 0.9f;
        };
        const bool result = executed && read && clear(center) && red(inside_tip) && clear(outside_corner) &&
                            blue_control && green(vertical_capsule) && green(horizontal_capsule) &&
                            retained_probe->called && retained_probe->state.has_clip_rect &&
                            !retained_probe->state.unsupported_clip &&
                            std::fabs(retained_probe->state.opacity - 0.4f) < 1.0e-6f;
        if (!result) {
            std::fprintf(stderr,
                         "DrawList2D clip smoke failed: execute=%d read=%d "
                         "center=(%.2f %.2f %.2f %.2f) "
                         "inside=(%.2f %.2f %.2f %.2f) "
                         "outside=(%.2f %.2f %.2f %.2f)\n",
                         executed,
                         read,
                         center[0],
                         center[1],
                         center[2],
                         center[3],
                         inside_tip[0],
                         inside_tip[1],
                         inside_tip[2],
                         inside_tip[3],
                         outside_corner[0],
                         outside_corner[1],
                         outside_corner[2],
                         outside_corner[3]);
            std::fprintf(stderr,
                         "immediate=(%.2f %.2f %.2f %.2f)\n",
                         immediate_control[0],
                         immediate_control[1],
                         immediate_control[2],
                         immediate_control[3]);
        }
        const bool regressions_ok = clip_regressions(*device, context, canvas, resources, target);
        canvas.release_gpu();
        device->destroy(target);
        return result && regressions_ok ? 0 : 3;
    }

} // namespace

int main(int argc, char** argv) {
    if (!tgfx::backend_is_compiled(tgfx::BackendType::Vulkan)) {
        std::printf("Vulkan backend not compiled, skipping test\n");
        return 0;
    }
    tc_shader_init();
    const int first_result = run(argc > 0 ? argv[0] : "");
    tc_shader_shutdown();
    if (first_result != 0) {
        return first_result;
    }

    // Process-scoped render hosts may replace their device and restart the
    // global registries across an Activity/surface lifecycle. Exercise a
    // second render in the same process so static built-in shader caches must
    // reject generation-stale handles and reacquire the new registry slots.
    tc_shader_init();
    const int second_result = run(argc > 0 ? argv[0] : "");
    tc_shader_shutdown();
    return second_result;
}
