#include <termin/render/sprite_renderer_2d.hpp>

#include <algorithm>
#include <cstring>

#include <tc_inspect_cpp.hpp>
#include <tcbase/tc_log.hpp>
#include <termin/tc_scene.hpp>
#include <tgfx/tgfx_texture_handle.hpp>
#include <tgfx2/render_context.hpp>

#include "sprite_reference_kind.hpp"

namespace termin {
    namespace {

        void register_sprite_tint(tc::InspectFacetBuilder& builder) {
            tc::InspectFieldInfo field;
            field.type_name = "SpriteRenderer2D";
            field.path = "tint";
            field.label = "Tint";
            field.kind = "color";
            field.getter = [](void* object) {
                const auto& tint = static_cast<SpriteRenderer2D*>(object)->tint;
                tc_value values = tc_value_list_new();
                for (int i = 0; i < 4; ++i) tc_value_list_push(&values, tc_value_double(tint[i]));
                return values;
            };
            field.setter = [](void* object, tc_value values, void*) {
                if (values.type != TC_VALUE_LIST || (values.data.list.count != 3 && values.data.list.count != 4)) {
                    tc::Log::error("[SpriteRenderer2D] tint requires three or four color channels");
                    return false;
                }
                Vec4 tint{1, 1, 1, 1};
                for (size_t i = 0; i < values.data.list.count; ++i) {
                    const auto& channel = values.data.list.items[i];
                    if (channel.type != TC_VALUE_FLOAT && channel.type != TC_VALUE_DOUBLE && channel.type != TC_VALUE_INT) {
                        tc::Log::error("[SpriteRenderer2D] tint channel %zu must be numeric", i);
                        return false;
                    }
                    tint[static_cast<int>(i)] = tc::tc_value_to_double(&channel);
                }
                static_cast<SpriteRenderer2D*>(object)->set_tint(tint);
                return true;
            };
            (void)builder.add_field(std::move(field));
        }

        bool encode_world_quad_id(tgfx::RenderContext2& ctx,
                                  const tc_render_item& item,
                                  const RenderItemDrawSubmitRequest& request,
                                  void*) {
            if (item.kind != TC_RENDER_ITEM_KIND_WORLD_QUAD) {
                tc::Log::error("[SpriteRenderer2D] ID encoder received item kind %u", item.kind);
                return false;
            }
            if (request.phase != TC_PHASE_NONE && request.phase != TC_PHASE_ID) {
                return false;
            }

            const auto& quad = item.payload.world_quad;
            const float vertices[] = {
                quad.min_x,
                0.0f,
                quad.min_z,
                quad.min_x,
                0.0f,
                quad.max_z,
                quad.max_x,
                0.0f,
                quad.max_z,
                quad.min_x,
                0.0f,
                quad.min_z,
                quad.max_x,
                0.0f,
                quad.max_z,
                quad.max_x,
                0.0f,
                quad.min_z,
            };
            tgfx::VertexLayoutDesc layout{};
            layout.stride = 3 * sizeof(float);
            layout.use_shader_input_locations = true;
            layout.attribute_count = 1;
            layout.attributes[0] = {0, tgfx::VertexFormat::Float3, 0, nullptr};
            ctx.draw_transient_arrays(vertices, sizeof(vertices), 6, layout, tgfx::PrimitiveTopology::TriangleList);
            return true;
        }

        void ensure_world_quad_id_encoder_registered() {
            static bool registered = false;
            if (registered) {
                return;
            }
            RenderItemDrawEncoderDesc desc{};
            desc.encode = encode_world_quad_id;
            desc.plan_task_shader = plan_render_item_passthrough_shader;
            desc.debug_name = "SpriteRenderer2D";
            desc.capabilities.phase_mask = TC_PHASE_ID;
            desc.capabilities.supported_task_input_mask =
                render_item_task_input_bit(RenderItemTaskInput::DrawContext) |
                render_item_task_input_bit(RenderItemTaskInput::ModelMatrix) |
                render_item_task_input_bit(RenderItemTaskInput::OverrideColor);
            desc.capabilities.required_task_input_mask = render_item_task_input_bit(RenderItemTaskInput::DrawContext);
            desc.capabilities.requires_draw_context = true;
            desc.capabilities.consumes_common_resources = true;
            registered = register_render_item_draw_encoder(TC_RENDER_ITEM_KIND_WORLD_QUAD, desc);
        }

        uint64_t sprite_stable_tie_breaker(const Entity& entity) {
            const uint64_t runtime_id = entity.runtime_id();
            return runtime_id != 0 ? runtime_id : static_cast<uint64_t>(entity.pick_id());
        }

        Mat44 to_double_matrix(const Mat44f& value) {
            Mat44 result;
            for (size_t index = 0; index < 16; ++index) {
                result.data[index] = value.data[index];
            }
            return result;
        }

    } // namespace

    SpriteRenderer2D::SpriteRenderer2D(const char* type_name)
        : Component(type_name) {
        install_drawable_vtable(&_c);
    }

    void SpriteRenderer2D::register_type() {
        register_sprite_reference_kind("sprite_asset");
        ensure_world_quad_id_encoder_registered();
        auto descriptor = ComponentTypeDescriptorBuilder::native<SpriteRenderer2D>(
            "SpriteRenderer2D", "termin-components-render", "Component");
        descriptor.category("Rendering/2D");
        auto& inspect = descriptor.inspect();
        inspect.add_with_callbacks<SpriteRenderer2D, std::string>(
            "SpriteRenderer2D",
            "sprite",
            "Sprite",
            "sprite_asset",
            [](SpriteRenderer2D* self) -> std::string& { return self->sprite_uuid; },
            [](SpriteRenderer2D* self, const std::string& value) { self->set_sprite_uuid(value); });
        register_sprite_tint(inspect);
        inspect.add_with_callbacks<SpriteRenderer2D, bool>(
            "SpriteRenderer2D",
            "flip_x",
            "Flip X",
            "bool",
            [](SpriteRenderer2D* self) -> bool& { return self->flip_x; },
            [](SpriteRenderer2D* self, const bool& value) { self->set_flip_x(value); });
        inspect.add_with_callbacks<SpriteRenderer2D, bool>(
            "SpriteRenderer2D",
            "flip_y",
            "Flip Y",
            "bool",
            [](SpriteRenderer2D* self) -> bool& { return self->flip_y; },
            [](SpriteRenderer2D* self, const bool& value) { self->set_flip_y(value); });
        inspect.add_with_callbacks<SpriteRenderer2D, int>(
            "SpriteRenderer2D",
            "sorting_layer",
            "Sorting Layer",
            "int",
            [](SpriteRenderer2D* self) -> int& { return self->sorting_layer; },
            [](SpriteRenderer2D* self, const int& value) { self->set_sorting_layer(value); });
        inspect.add_with_callbacks<SpriteRenderer2D, int>(
            "SpriteRenderer2D",
            "order_in_layer",
            "Order In Layer",
            "int",
            [](SpriteRenderer2D* self) -> int& { return self->order_in_layer; },
            [](SpriteRenderer2D* self, const int& value) { self->set_order_in_layer(value); });
        inspect.add_with_callbacks<SpriteRenderer2D, bool>(
            "SpriteRenderer2D",
            "visible",
            "Visible",
            "bool",
            [](SpriteRenderer2D* self) -> bool& { return self->visible; },
            [](SpriteRenderer2D* self, const bool& value) { self->set_visible(value); });
        (void)descriptor.commit();
    }

    const std::string& SpriteRenderer2D::effective_sprite_uuid() const {
        return animation_sprite_uuid_.empty() ? sprite_uuid : animation_sprite_uuid_;
    }

    void SpriteRenderer2D::set_animation_sprite_uuid(const std::string& value) {
        if (value == animation_sprite_uuid_) return;
        animation_sprite_uuid_ = value;
        last_missing_asset_version_ = UINT32_MAX;
        if (!value.empty() && !TcSpriteAsset::from_uuid(value).is_loaded()) {
            tc::Log::error("[SpriteRenderer2D] animation frame sprite is missing or unloaded: uuid='%s'", value.c_str());
            last_missing_asset_version_ = 0;
        }
        const auto scene = entity().scene();
        if (scene.valid()) tc_scene_request_render(scene.handle());
    }

    void SpriteRenderer2D::set_sprite_uuid(const std::string& value) {
        sprite_uuid = value;
        last_missing_asset_version_ = UINT32_MAX;
    }

    void SpriteRenderer2D::set_tint(const Vec4& value) {
        tint = value;
    }
    void SpriteRenderer2D::set_flip_x(bool value) {
        flip_x = value;
    }
    void SpriteRenderer2D::set_flip_y(bool value) {
        flip_y = value;
    }
    void SpriteRenderer2D::set_sorting_layer(int value) {
        sorting_layer = value;
    }
    void SpriteRenderer2D::set_order_in_layer(int value) {
        order_in_layer = value;
    }
    void SpriteRenderer2D::set_visible(bool value) {
        visible = value;
    }

    tc_value SpriteRenderer2D::serialize_data() const {
        tc_value data = Component::serialize_data();
        if (data.type == TC_VALUE_DICT && !sprite_uuid.empty()) {
            tc_value sprite = tc_value_dict_new();
            tc_value_dict_set(&sprite, "type", tc_value_string("uuid"));
            tc_value_dict_set(&sprite, "kind", tc_value_string("sprite_asset"));
            tc_value_dict_set(&sprite, "role", tc_value_string("sprite"));
            tc_value_dict_set(&sprite, "uuid", tc_value_string(sprite_uuid.c_str()));
            tc_value_dict_set(&data, "sprite", sprite);
        }
        return data;
    }

    void SpriteRenderer2D::deserialize_data(const tc_value* data, tc_scene_handle scene) {
        if (!data || data->type != TC_VALUE_DICT) {
            Component::deserialize_data(data, scene);
            return;
        }
        tc_value filtered = tc_value_copy(data);
        tc_value* sprite = tc_value_dict_get(&filtered, "sprite");
        if (sprite && sprite->type == TC_VALUE_DICT) {
            tc_value* uuid = tc_value_dict_get(sprite, "uuid");
            if (uuid && uuid->type == TC_VALUE_STRING && uuid->data.s) {
                tc_value_dict_set(&filtered, "sprite", tc_value_string(uuid->data.s));
            } else {
                tc::Log::error("[SpriteRenderer2D] serialized sprite reference has no UUID");
                tc_value_dict_set(&filtered, "sprite", tc_value_string(""));
            }
        }
        Component::deserialize_data(&filtered, scene);
        tc_value_free(&filtered);
        last_missing_asset_version_ = UINT32_MAX;
    }

    bool SpriteRenderer2D::resolved_quad(TcSpriteAsset& out_asset,
                                         World2DQuadRect& out_rect,
                                         float& out_u0,
                                         float& out_v0,
                                         float& out_u1,
                                         float& out_v1) const {
        out_asset = TcSpriteAsset::from_uuid(effective_sprite_uuid());
        SpriteAsset* asset = out_asset.get();
        if (!asset || !asset->loaded) {
            if (last_missing_asset_version_ != 0) {
                tc::Log::error("[SpriteRenderer2D] sprite asset is missing or unloaded: uuid='%s'",
                               effective_sprite_uuid().c_str());
                last_missing_asset_version_ = 0;
            }
            return false;
        }
        last_missing_asset_version_ = asset->version;

        const double width = static_cast<double>(asset->region.width) / asset->pixels_per_unit;
        const double height = static_cast<double>(asset->region.height) / asset->pixels_per_unit;
        out_rect = {
            -static_cast<double>(asset->pivot_x) * width,
            -static_cast<double>(1.0f - asset->pivot_y) * height,
            static_cast<double>(1.0f - asset->pivot_x) * width,
            static_cast<double>(asset->pivot_y) * height,
        };

        out_u0 = static_cast<float>(asset->region.x) / asset->source_width;
        out_v0 = static_cast<float>(asset->region.y) / asset->source_height;
        out_u1 = static_cast<float>(asset->region.x + asset->region.width) / asset->source_width;
        out_v1 = static_cast<float>(asset->region.y + asset->region.height) / asset->source_height;
        if (flip_x) {
            std::swap(out_u0, out_u1);
        }
        if (flip_y) {
            std::swap(out_v0, out_v1);
        }
        return true;
    }

    tc_phase_mask SpriteRenderer2D::get_phase_mask() const {
        return visible && !effective_sprite_uuid().empty() ? (TC_PHASE_TRANSPARENT | TC_PHASE_ID) : TC_PHASE_NONE;
    }

    bool SpriteRenderer2D::collect_materials(const tc_render_item_collect_context&, tc_material_sink& sink) {
        if (!sink.emit) {
            tc::Log::error("[SpriteRenderer2D] material sink is null");
            return false;
        }
        // WORLD_QUAD items carry a sprite texture directly, with no owner material.
        return true;
    }

    bool SpriteRenderer2D::collect_render_items(const tc_render_item_collect_context& context,
                                                tc_render_item_sink& sink) {
        if (!sink.emit) {
            tc::Log::error("[SpriteRenderer2D] render item sink is null");
            return false;
        }
        if (!visible || effective_sprite_uuid().empty()) {
            return true;
        }
        if (context.phase != TC_PHASE_NONE && context.phase != TC_PHASE_TRANSPARENT && context.phase != TC_PHASE_ID) {
            return true;
        }

        TcSpriteAsset asset_handle;
        World2DQuadRect rect;
        float u0 = 0.0f;
        float v0 = 0.0f;
        float u1 = 1.0f;
        float v1 = 1.0f;
        if (!resolved_quad(asset_handle, rect, u0, v0, u1, v1)) {
            return true;
        }
        const SpriteAsset* asset = asset_handle.get();
        TcTexture texture = TcTexture::from_uuid(asset->texture_uuid);
        if (!texture.is_valid()) {
            tc::Log::error("[SpriteRenderer2D] texture is not declared: sprite='%s' texture='%s'",
                           effective_sprite_uuid().c_str(),
                           asset->texture_uuid.c_str());
            return true;
        }

        tc_render_item item{};
        item.kind = TC_RENDER_ITEM_KIND_WORLD_QUAD;
        item.material = tc_material_handle_invalid();
        item.material_phase_index = SIZE_MAX;
        item.flags = TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX;
        item.geometry_id = 0;
        const Mat44f model = get_model_matrix(entity());
        std::memcpy(item.model_matrix, model.data, sizeof(item.model_matrix));

        auto& quad = item.payload.world_quad;
        quad.texture = texture.get();
        quad.texture_handle = texture.handle;
        quad.min_x = static_cast<float>(rect.min_x);
        quad.min_z = static_cast<float>(rect.min_z);
        quad.max_x = static_cast<float>(rect.max_x);
        quad.max_z = static_cast<float>(rect.max_z);
        quad.u0 = u0;
        quad.v0 = v0;
        quad.u1 = u1;
        quad.v1 = v1;
        quad.tint = {tint.x, tint.y, tint.z, tint.w};
        quad.sorting_layer = sorting_layer;
        quad.order_in_layer = order_in_layer;
        quad.spatial_depth = model(3, 1);
        quad.stable_tie_breaker = sprite_stable_tie_breaker(entity());
        quad.sampling =
            asset->sampling == SpriteSampling::Nearest ? TC_WORLD_QUAD_SAMPLING_NEAREST : TC_WORLD_QUAD_SAMPLING_LINEAR;
        return sink.emit(&item, sink.user_data);
    }

    AABB SpriteRenderer2D::world_bounds() const {
        TcSpriteAsset asset;
        World2DQuadRect rect;
        float u0 = 0.0f;
        float v0 = 0.0f;
        float u1 = 0.0f;
        float v1 = 0.0f;
        if (!resolved_quad(asset, rect, u0, v0, u1, v1)) {
            return {};
        }
        return world2d_quad_bounds(rect, to_double_matrix(get_model_matrix(entity())));
    }

    bool SpriteRenderer2D::ray_intersects(const Ray3& ray, double* out_ray_parameter) const {
        TcSpriteAsset asset;
        World2DQuadRect rect;
        float u0 = 0.0f;
        float v0 = 0.0f;
        float u1 = 0.0f;
        float v1 = 0.0f;
        if (!resolved_quad(asset, rect, u0, v0, u1, v1)) {
            return false;
        }
        return ray_intersects_world2d_quad(ray, rect, to_double_matrix(get_model_matrix(entity())), out_ray_parameter);
    }

} // namespace termin
