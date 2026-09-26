#include <cassert>
#include <cmath>
#include <cstring>

#include "termin_visual_scene/graphic_item2d.hpp"
#include "termin_visual_scene/items/text_item2d.hpp"
#include "termin_visual_scene/items/rect_item2d.hpp"
#include "termin_visual_scene/scene2d.hpp"
#include "termin_visual_scene/scene_render2d.hpp"
#include "termin_visual_scene/tc_builtin_items2d.h"

namespace {

    tc_visual_color4f color(float r, float g, float b, float a = 1.0f) {
        return {r, g, b, a};
    }

    tc_visual_fill_paint2d fill(tc_visual_color4f value) {
        return {value, TC_VISUAL_FILL_RULE_NON_ZERO};
    }

    tc_visual_stroke_paint2d stroke(tc_visual_color4f value) {
        return {
            .color = value,
            .width = 2.0f,
            .join = TC_VISUAL_STROKE_JOIN_ROUND,
            .cap = TC_VISUAL_STROKE_CAP_ROUND,
            .miter_limit = 4.0f,
            .dash_pattern = nullptr,
            .dash_count = 0,
            .dash_offset = 0.0f,
        };
    }

    tc_visual_path2d_view triangle() {
        static const tc_visual_path_verb2d verbs[] = {
            TC_VISUAL_PATH_MOVE_TO,
            TC_VISUAL_PATH_LINE_TO,
            TC_VISUAL_PATH_LINE_TO,
            TC_VISUAL_PATH_CLOSE,
        };
        static const tc_vec2f points[] = {
            {0.0f, 0.0f},
            {20.0f, 0.0f},
            {10.0f, 15.0f},
        };
        return {verbs, 4, points, 3};
    }

    bool same_handle(tc_graphic_item_handle lhs, tc_graphic_item_handle rhs) {
        return lhs.scene_id == rhs.scene_id && lhs.index == rhs.index && lhs.generation == rhs.generation;
    }

    class ColorResolver final : public termin::visual::SceneRenderResourceResolver2D {
    public:
        std::optional<tgfx::FontHandle> resolve_font(std::string_view) override { return tgfx::FontHandle{1}; }
        std::optional<tgfx::TextureHandle> resolve_image(std::string_view) override { return tgfx::TextureHandle{2}; }
        std::optional<termin::visual::ResolvedCustomBatch2D> resolve_custom_batch(
            std::string_view, termin::Bounds2f) override { return std::nullopt; }
    };

    void check_linear(termin::LinearColor actual, tc_visual_color4f authored) {
        const auto expected = termin::srgb_to_linear(termin::SrgbColor{authored.r, authored.g, authored.b, authored.a});
        assert(std::abs(actual.r - expected.r) < 1e-6f);
        assert(std::abs(actual.g - expected.g) < 1e-6f);
        assert(std::abs(actual.b - expected.b) < 1e-6f);
        assert(actual.a == authored.a);
    }

    void test_authored_color_boundary() {
        const auto handle = tc_visual_scene_create();
        termin::visual::TcVisualScene scene{handle};
        const auto no_parent = tc_graphic_item_handle_invalid();
        auto authored = color(0.3f, 0.4f, 0.6f, 0.7f);
        auto fill_paint = fill(authored);
        auto stroke_paint = stroke(authored);
        const auto rect = tc_visual_rect_item2d_create(handle, no_parent, {0, 0, 20, 20}, fill_paint, &stroke_paint);
        const auto path = tc_visual_path_item2d_create(handle, no_parent, triangle(), &fill_paint, &stroke_paint);
        tc_visual_text_desc2d text_desc{"test", "font://test", {0, 0}, 12, authored,
            TC_VISUAL_TEXT_ANCHOR_LEFT, {0, 0, 30, 15}, false, 1};
        tc_visual_image_desc2d image_desc{"image://test", {0, 0, 20, 20}, {0, 0, 1, 1}, authored,
            TC_VISUAL_TEXTURE_SAMPLING_LINEAR};
        const auto text = tc_visual_text_item2d_create(handle, no_parent, &text_desc);
        const auto image = tc_visual_image_item2d_create(handle, no_parent, &image_desc);
        for (auto item : {rect, path, text, image})
            assert(tc_visual_scene_item_is_valid(handle, item));
        ColorResolver resolver;
        for (int mutation = 0; mutation < 2; ++mutation) {
            if (mutation) {
                authored = color(0.7f, 0.2f, 0.5f, 0.4f);
                fill_paint = fill(authored);
                stroke_paint = stroke(authored);
                text_desc.color = authored;
                image_desc.tint = authored;
                assert(tc_visual_rect_item2d_set(handle, rect, {0, 0, 20, 20}, fill_paint, &stroke_paint));
                assert(tc_visual_path_item2d_set(handle, path, triangle(), &fill_paint, &stroke_paint));
                assert(tc_visual_text_item2d_set(handle, text, &text_desc));
                assert(tc_visual_image_item2d_set(handle, image, &image_desc));
            }
            const auto* base = tc_visual_scene_resolve_item_const(handle, rect);
            assert(base);
            const auto* body = static_cast<const termin::visual::RectItem2D*>(base->body);
            check_linear(body->fill().color, authored);
            assert(body->stroke());
            check_linear(body->stroke()->color, authored);
            tgfx::DrawList2DBuilder builder;
            assert(scene.paint(builder, resolver));
            const auto list = builder.freeze();
            assert(list);
            bool saw_path = false, saw_text = false, saw_image = false;
            for (const auto& command : list->commands()) {
                if (const auto* value = std::get_if<tgfx::DrawPath2D>(&command)) {
                    if (value->fill) check_linear(value->fill->color, authored);
                    if (value->stroke) check_linear(value->stroke->color, authored);
                    saw_path = true;
                } else if (const auto* value = std::get_if<tgfx::DrawText2D>(&command)) {
                    check_linear(value->color, authored);
                    saw_text = true;
                } else if (const auto* value = std::get_if<tgfx::DrawImage2D>(&command)) {
                    check_linear(value->tint, authored);
                    saw_image = true;
                }
            }
            assert(saw_path && saw_text && saw_image);
        }
        tc_visual_scene_destroy(handle);
    }

} // namespace

int main() {
    test_authored_color_boundary();
    const auto scene = tc_visual_scene_create();
    const auto other = tc_visual_scene_create();
    assert(tc_visual_scene_is_valid(scene));

    const auto group = tc_visual_group_item2d_create(scene, tc_graphic_item_handle_invalid());
    assert(tc_visual_scene_item_is_valid(scene, group));
    assert(tc_visual_scene_item_is_type(scene, group, "termin.visual.Group2D"));

    const auto white = fill(color(1.0f, 1.0f, 1.0f));
    const auto black = stroke(color(0.0f, 0.0f, 0.0f));
    const auto rect = tc_visual_rect_item2d_create(scene, group, {1.0f, 2.0f, 40.0f, 30.0f}, white, &black);
    assert(tc_visual_scene_item_is_valid(scene, rect));
    assert(tc_visual_scene_item_parent(scene, rect).index == group.index);
    assert(tc_visual_scene_item_child_count(scene, group) == 1);
    assert(tc_visual_scene_item_child_at(scene, group, 0).index == rect.index);

    assert(tc_visual_scene_item_set_transform(scene, rect, tc_affine2f_translation(5.0f, 7.0f)));
    tc_affine2f transform{};
    assert(tc_visual_scene_item_get_transform(scene, rect, &transform));
    assert(transform.tx == 5.0f && transform.ty == 7.0f);
    assert(tc_visual_scene_item_set_visible(scene, rect, false));
    bool visible = true;
    assert(tc_visual_scene_item_get_visible(scene, rect, &visible));
    assert(!visible);
    assert(tc_visual_scene_item_set_enabled(scene, rect, false));
    assert(tc_visual_scene_item_set_opacity(scene, rect, 0.5f));
    assert(tc_visual_scene_item_set_z_order(scene, rect, 42));
    assert(tc_visual_scene_item_set_clip_rect(scene, rect, {0.0f, 0.0f, 20.0f, 20.0f}));

    tc_bounds2f bounds{};
    assert(tc_visual_scene_item_get_local_bounds(scene, rect, &bounds));
    assert(bounds.x0 <= 0.0f && bounds.x1 >= 41.0f);
    assert(tc_visual_scene_item_get_world_bounds(scene, rect, &bounds));
    assert(tc_visual_rect_item2d_set(scene, rect, {0.0f, 0.0f, 10.0f, 10.0f}, white, nullptr));
    const auto* rect_base = tc_visual_scene_resolve_item_const(scene, rect);
    assert(rect_base != nullptr);
    assert(static_cast<const termin::visual::GraphicItem2D*>(rect_base->body)->clip().has_value());
    assert(!tc_visual_path_item2d_set(scene, rect, triangle(), &white, nullptr));
    assert(!tc_visual_scene_item_is_valid(other, rect));

    const auto path = tc_visual_path_item2d_create(scene, group, triangle(), &white, &black);
    const tc_visual_text_desc2d text_desc{
        .text = "axis",
        .font_uri = "ui://default-font",
        .origin = {0.0f, 12.0f},
        .size_px = 12.0f,
        .color = color(0.0f, 0.0f, 0.0f),
        .anchor = TC_VISUAL_TEXT_ANCHOR_LEFT,
        .layout_bounds = {0.0f, 0.0f, 60.0f, 20.0f},
        .has_coverage_gamma = true,
        .coverage_gamma = 1.3f,
    };
    const auto text = tc_visual_text_item2d_create(scene, group, &text_desc);
    const tc_visual_image_desc2d image_desc{
        .image_uri = "asset://plot-icon",
        .rect = {0.0f, 0.0f, 16.0f, 16.0f},
        .uv = {0.0f, 0.0f, 1.0f, 1.0f},
        .tint = color(1.0f, 1.0f, 1.0f),
        .sampling = TC_VISUAL_TEXTURE_SAMPLING_LINEAR,
    };
    const auto image = tc_visual_image_item2d_create(scene, group, &image_desc);
    const auto hit = tc_visual_hit_region_item2d_create(scene, group, triangle(), TC_VISUAL_FILL_RULE_EVEN_ODD);
    assert(tc_visual_scene_item_is_valid(scene, path));
    assert(tc_visual_scene_item_is_valid(scene, text));
    const auto* text_base = tc_visual_scene_resolve_item_const(scene, text);
    assert(text_base != nullptr);
    const auto* text_body = static_cast<const termin::visual::TextItem2D*>(text_base->body);
    assert(text_body->coverage_gamma() && *text_body->coverage_gamma() == 1.3f);
    assert(tc_visual_scene_item_is_valid(scene, image));
    assert(tc_visual_scene_item_is_valid(scene, hit));
    assert(tc_visual_scene_item_set_parent(scene, hit, group, 0));
    assert(same_handle(tc_visual_scene_item_child_at(scene, group, 0), hit));

    tc_graphic_item_handle ordered[6]{};
    assert(tc_visual_scene_copy_item_handles(scene, ordered, 6) == 6);
    assert(same_handle(ordered[0], group));
    assert(same_handle(ordered[1], rect));
    assert(same_handle(ordered[2], path));
    assert(same_handle(ordered[3], text));
    assert(same_handle(ordered[4], image));
    assert(same_handle(ordered[5], hit));

    assert(tc_visual_scene_item_set_parent(scene, rect, tc_graphic_item_handle_invalid(), 0));
    assert(tc_graphic_item_handle_is_invalid(tc_visual_scene_item_parent(scene, rect)));
    assert(!tc_visual_scene_item_set_parent(scene, rect, path, 99));
    assert(tc_visual_scene_item_clear_clip(scene, rect));

    assert(tc_visual_scene_destroy_item(scene, group));
    assert(!tc_visual_scene_item_is_valid(scene, group));
    assert(!tc_visual_scene_item_is_valid(scene, path));
    assert(tc_visual_scene_item_is_valid(scene, rect));
    tc_visual_scene_destroy(scene);
    assert(!tc_visual_scene_item_is_valid(scene, rect));
    tc_visual_scene_destroy(other);
    return 0;
}
