#include "visual_scene_example.hpp"

#include <cmath>
#include <memory>
#include <optional>
#include <stdexcept>
#include <string_view>
#include <vector>

#include <tcbase/tc_log.h>
#include <termin/geom/affine2.hpp>
#include <termin/geom/color.hpp>
#include <termin_visual_scene/builtin_items2d.hpp>
#include <termin_visual_scene/scene_render2d.hpp>
#include <tgfx2/canvas2d_renderer.hpp>
#include <tgfx2/graphics_host.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/webgpu/webgpu_render_device.hpp>

namespace termin::web {
    namespace {

        class SceneResources final : public visual::SceneRenderResourceResolver2D {
        public:
            std::optional<tgfx::FontHandle> resolve_font(std::string_view) override {
                return std::nullopt;
            }

            std::optional<tgfx::TextureHandle> resolve_image(std::string_view) override {
                return std::nullopt;
            }

            std::optional<visual::ResolvedCustomBatch2D> resolve_custom_batch(std::string_view,
                                                                              termin::Bounds2f) override {
                return std::nullopt;
            }
        };

        class DrawResources final : public tgfx::DrawResourceResolver2D {
        public:
            tgfx::FontAtlas* resolve_font(tgfx::FontHandle) override {
                return nullptr;
            }
        };

        class OwnedVisualScene {
        public:
            OwnedVisualScene()
                : scene_(tc_visual_scene_create()) {
                if (!scene_.valid()) {
                    throw std::runtime_error("failed to create TcVisualScene");
                }
            }

            ~OwnedVisualScene() {
                if (scene_.valid()) {
                    tc_visual_scene_destroy(scene_.handle());
                }
            }

            visual::TcVisualScene& scene() {
                return scene_;
            }

        private:
            visual::TcVisualScene scene_;
        };

        tgfx::FillPaint fill(float red, float green, float blue, float alpha = 1.0f) {
            return tgfx::FillPaint{termin::LinearColor{red, green, blue, alpha}};
        }

        tgfx::StrokePaint stroke(float red, float green, float blue, float width, float alpha = 1.0f) {
            tgfx::StrokePaint result;
            result.color = {red, green, blue, alpha};
            result.width = width;
            result.join = tgfx::StrokeJoin::Round;
            result.cap = tgfx::StrokeCap::Round;
            return result;
        }

        tgfx::Path2f rectangle_path(float width, float height) {
            tgfx::Path2f path;
            if (!path.move_to({0.0f, 0.0f}) || !path.line_to({width, 0.0f}) || !path.line_to({width, height}) ||
                !path.line_to({0.0f, height}) || !path.close()) {
                throw std::runtime_error("failed to build visual-scene clip path");
            }
            return path;
        }

        tgfx::Path2f star_path(float outer_radius, float inner_radius) {
            constexpr float pi = 3.14159265358979323846f;
            tgfx::Path2f path;
            for (int index = 0; index < 10; ++index) {
                const float angle = -pi * 0.5f + static_cast<float>(index) * pi / 5.0f;
                const float radius = (index % 2 == 0) ? outer_radius : inner_radius;
                const termin::Vec2f point{std::cos(angle) * radius, std::sin(angle) * radius};
                const bool ok = index == 0 ? path.move_to(point) : path.line_to(point);
                if (!ok) {
                    throw std::runtime_error("failed to build visual-scene star path");
                }
            }
            if (!path.close()) {
                throw std::runtime_error("failed to close visual-scene star path");
            }
            return path;
        }

        template <typename Item>
        Item& adopt(visual::TcVisualScene& scene, std::unique_ptr<Item> item, visual::GraphicItem2D* parent = nullptr) {
            Item* result = item.get();
            if (!scene.adopt(std::move(item), parent)) {
                throw std::runtime_error("failed to adopt visual-scene item");
            }
            return *result;
        }

        tgfx::DrawList2D build_example_scene() {
            OwnedVisualScene owned_scene;
            visual::TcVisualScene& scene = owned_scene.scene();

            auto& root = adopt(scene, std::make_unique<visual::GroupItem2D>());
            root.set_local_transform(termin::Affine2f::translation(80.0f, 70.0f));
            root.set_clip(visual::GeometricClip2D{rectangle_path(800.0f, 440.0f), tgfx::FillRule::NonZero});

            adopt(scene,
                  std::make_unique<visual::RoundedRectItem2D>(
                      termin::Rect2f{0.0f, 0.0f, 800.0f, 440.0f}, 28.0f, fill(0.035f, 0.075f, 0.14f)),
                  &root);
            adopt(scene,
                  std::make_unique<visual::RectItem2D>(termin::Rect2f{0.0f, 0.0f, 800.0f, 76.0f},
                                                       fill(0.02f, 0.55f, 0.72f)),
                  &root);
            adopt(scene,
                  std::make_unique<visual::RectItem2D>(termin::Rect2f{36.0f, 34.0f, 210.0f, 8.0f},
                                                       fill(0.72f, 0.96f, 1.0f)),
                  &root);

            auto& orbit_group = adopt(scene, std::make_unique<visual::GroupItem2D>(), &root);
            orbit_group.set_local_transform(termin::Affine2f::translation(168.0f, 246.0f) *
                                            termin::Affine2f::rotation(-0.16f));
            orbit_group.set_opacity(0.88f);
            adopt(scene,
                  std::make_unique<visual::EllipseItem2D>(termin::Rect2f{-135.0f, -135.0f, 270.0f, 270.0f},
                                                          fill(0.45f, 0.08f, 0.72f)),
                  &orbit_group);
            adopt(scene,
                  std::make_unique<visual::EllipseItem2D>(termin::Rect2f{-82.0f, -82.0f, 164.0f, 164.0f},
                                                          fill(0.93f, 0.18f, 0.48f)),
                  &orbit_group);
            adopt(scene,
                  std::make_unique<visual::EllipseItem2D>(termin::Rect2f{-31.0f, -31.0f, 62.0f, 62.0f},
                                                          fill(1.0f, 0.72f, 0.18f)),
                  &orbit_group);

            auto& star = adopt(scene,
                               std::make_unique<visual::PathItem2D>(
                                   star_path(94.0f, 42.0f), fill(1.0f, 0.66f, 0.08f), stroke(1.0f, 0.92f, 0.58f, 6.0f)),
                               &root);
            star.set_local_transform(termin::Affine2f::translation(440.0f, 235.0f) * termin::Affine2f::rotation(0.18f));

            adopt(scene,
                  std::make_unique<visual::PolylineItem2D>(
                      std::vector<termin::Vec2f>{
                          {548.0f, 340.0f}, {590.0f, 280.0f}, {638.0f, 306.0f}, {688.0f, 194.0f}, {744.0f, 236.0f}},
                      stroke(0.18f, 0.95f, 0.58f, 10.0f)),
                  &root);
            adopt(scene,
                  std::make_unique<visual::RoundedRectItem2D>(
                      termin::Rect2f{618.0f, 348.0f, 146.0f, 56.0f}, 16.0f, fill(0.95f, 0.25f, 0.10f)),
                  &root);

            SceneResources resources;
            tgfx::DrawList2DBuilder builder;
            if (!scene.paint(builder, resources)) {
                throw std::runtime_error("TcVisualScene paint failed");
            }
            std::optional<tgfx::DrawList2D> list = builder.freeze();
            if (!list) {
                throw std::runtime_error("failed to freeze visual-scene DrawList2D");
            }
            return std::move(*list);
        }

    } // namespace

    bool render_visual_scene_example(tgfx::WebGpuRenderDevice& device,
                                     tgfx::GraphicsHost& graphics_host,
                                     std::uint32_t width,
                                     std::uint32_t height,
                                     std::string& error) {
        error.clear();
        if (width == 0 || height == 0) {
            error = "visual-scene canvas size must be positive";
            tc_log_error("Termin Web visual-scene example: %s", error.c_str());
            return false;
        }
        try {
            tgfx::DrawList2D list = build_example_scene();
            tgfx::RenderContext2& context = graphics_host.context();
            if (context.in_frame()) {
                throw std::runtime_error("graphics host already has an active frame");
            }

            const tgfx::TextureHandle surface = device.acquire_surface_texture();
            const termin::LinearColor clear{0.012f, 0.025f, 0.055f, 1.0f};
            tgfx::Canvas2DRenderer canvas;
            DrawResources resources;
            context.begin_frame();
            context.begin_pass(surface, {}, &clear, 1.0f, false);
            canvas.begin(context, static_cast<int>(width), static_cast<int>(height));
            const bool executed = canvas.execute(list, resources);
            canvas.end();
            context.end_pass();
            context.end_frame();
            if (!executed) {
                throw std::runtime_error("Canvas2DRenderer rejected the visual-scene DrawList2D");
            }
            device.present();
            return true;
        } catch (const std::exception& exception) {
            error = exception.what();
            tc_log_error("Termin Web visual-scene example failed: %s", error.c_str());
            return false;
        }
    }

} // namespace termin::web
