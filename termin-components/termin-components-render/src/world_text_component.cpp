#include <termin/render/world_text_component.hpp>

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <string>
#include <vector>

#include <termin/entity/component.hpp>
#include <tcbase/tc_log.hpp>
#include <tc_inspect_cpp.hpp>
#include <tgfx2/builtin_shader_sources.hpp>
#include <tgfx2/font_atlas.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/text3d_renderer.hpp>

extern "C" {
#include <tgfx/resources/tc_shader_registry.h>
}

namespace termin {
namespace {

constexpr const char* TEXT3D_SHADER_UUID = "termin-engine-text3d";

const std::vector<const char*> kDefaultFontCandidates = {
#if defined(_WIN32)
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "C:/Windows/Fonts/tahoma.ttf",
#elif defined(__APPLE__)
    "/System/Library/Fonts/SFNSText.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/Library/Fonts/Arial.ttf",
#else
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    "/usr/share/fonts/TTF/DejaVuSans.ttf",
#endif
};

std::string find_default_font_path() {
    for (const char* path : kDefaultFontCandidates) {
        if (!path || path[0] == '\0') {
            continue;
        }
        std::error_code ec;
        if (std::filesystem::exists(path, ec)) {
            return path;
        }
    }
    return "";
}

tc_render_state make_text_render_state(const WorldTextComponent& component) {
    tc_render_state state = component.blend
        ? tc_render_state_transparent()
        : tc_render_state_opaque();
    state.depth_test = component.depth_test ? 1 : 0;
    state.depth_write = component.depth_write ? 1 : 0;
    state.blend = component.blend ? 1 : 0;
    state.cull = component.cull ? 1 : 0;
    return state;
}

tgfx::Text3DRenderer::Anchor to_tgfx_anchor(WorldTextAnchor anchor) {
    switch (anchor) {
        case WorldTextAnchor::Left:
            return tgfx::Text3DRenderer::Anchor::Left;
        case WorldTextAnchor::Right:
            return tgfx::Text3DRenderer::Anchor::Right;
        case WorldTextAnchor::Center:
        default:
            return tgfx::Text3DRenderer::Anchor::Center;
    }
}

void extract_view_row3(const Mat44f& view, int row, float out[3]) {
    out[0] = view(0, row);
    out[1] = view(1, row);
    out[2] = view(2, row);
}

Vec3 normalized_or(const Vec3& value, const Vec3& fallback) {
    const double len = value.norm();
    if (len <= 1.0e-8) {
        return fallback;
    }
    return value / len;
}

void copy_basis_vec(const Vec3& value, float out[3]) {
    out[0] = static_cast<float>(value.x);
    out[1] = static_cast<float>(value.y);
    out[2] = static_cast<float>(value.z);
}

bool make_fixed_text_basis(
    const Vec3& plane_normal,
    const Vec3& text_up_source,
    const Mat44f& model,
    float text_right[3],
    float text_up[3])
{
    const Vec3 transformed_normal = model.transform_direction(plane_normal);
    Vec3 normal = normalized_or(transformed_normal, Vec3::unit_z());

    const Vec3 transformed_up = model.transform_direction(text_up_source);
    Vec3 up = transformed_up - normal * transformed_up.dot(normal);
    if (up.norm() <= 1.0e-8) {
        tc::Log::error(
            "[WorldTextComponent] text_up is parallel to plane_normal; using fallback basis");
        const Vec3 fallback = std::abs(normal.dot(Vec3::unit_z())) < 0.99
            ? Vec3::unit_z()
            : Vec3::unit_y();
        up = fallback - normal * fallback.dot(normal);
    }
    up = normalized_or(up, Vec3::unit_y());

    Vec3 right = up.cross(normal);
    if (right.norm() <= 1.0e-8) {
        tc::Log::error("[WorldTextComponent] failed to build fixed text basis");
        return false;
    }
    right = right.normalized();

    copy_basis_vec(right, text_right);
    copy_basis_vec(up, text_up);
    return true;
}

std::string sanitize_phase_mark(const std::string& value) {
    if (value.empty()) {
        return "transparent";
    }
    return value.substr(0, TC_PHASE_MARK_MAX - 1);
}

bool decode_text_anchor(uint32_t value, WorldTextAnchor& anchor)
{
    switch (value) {
        case static_cast<uint32_t>(WorldTextAnchor::Left):
        case static_cast<uint32_t>(WorldTextAnchor::Center):
        case static_cast<uint32_t>(WorldTextAnchor::Right):
            anchor = static_cast<WorldTextAnchor>(value);
            return true;
    }
    return false;
}

bool decode_text_orientation(uint32_t value, WorldTextOrientation& orientation)
{
    switch (value) {
        case static_cast<uint32_t>(WorldTextOrientation::Billboard):
        case static_cast<uint32_t>(WorldTextOrientation::Fixed):
            orientation = static_cast<WorldTextOrientation>(value);
            return true;
    }
    return false;
}

Vec3 vec3_from_payload(const tc_render_item_vec3& value)
{
    return Vec3{value.x, value.y, value.z};
}

bool world_text_render_item_draw_encoder(
    tgfx::RenderContext2& ctx,
    const tc_render_item& item,
    const RenderItemDrawSubmitRequest& request,
    void* user_data)
{
    (void)user_data;
    if (item.kind != TC_RENDER_ITEM_KIND_TEXT_BATCH) {
        tc::Log::error(
            "[WorldTextComponent] text encoder received unsupported item kind %u",
            item.kind);
        return false;
    }
    CxxComponent* component = CxxComponent::from_tc(item.component);
    auto* renderer = dynamic_cast<WorldTextComponent*>(component);
    if (!renderer) {
        const char* type_name = component ? component->type_name() : "<null>";
        tc::Log::error(
            "[WorldTextComponent] text RenderItem component is not WorldTextComponent: type='%s'",
            type_name ? type_name : "<unknown>");
        return false;
    }
    return renderer->encode_render_item_tgfx2(ctx, item, request);
}

void ensure_world_text_render_item_encoder_registered()
{
    static bool registered = false;
    if (registered) {
        return;
    }

    RenderItemDrawEncoderDesc desc{};
    desc.encode = world_text_render_item_draw_encoder;
    desc.debug_name = "WorldTextComponent";
    registered = register_render_item_draw_encoder(TC_RENDER_ITEM_KIND_TEXT_BATCH, desc);
}

} // namespace

WorldTextComponent::WorldTextComponent(const char* type_name)
    : Component(type_name)
{
    install_drawable_vtable(&_c);
}

void WorldTextComponent::register_type() {
    ensure_world_text_render_item_encoder_registered();
    register_component_type<WorldTextComponent>("WorldTextComponent", "Component");
    auto& inspect = tc::InspectRegistry::instance();
    inspect.add_with_callbacks<WorldTextComponent, std::string>(
        "WorldTextComponent",
        "text",
        "Text",
        "string",
        [](WorldTextComponent* self) -> std::string& { return self->text; },
        [](WorldTextComponent* self, const std::string& value) { self->set_text(value); }
    );
    inspect.add_with_callbacks<WorldTextComponent, std::string>(
        "WorldTextComponent",
        "font_path",
        "Font Path",
        "string",
        [](WorldTextComponent* self) -> std::string& { return self->font_path; },
        [](WorldTextComponent* self, const std::string& value) { self->set_font_path(value); }
    );
    inspect.add_with_callbacks<WorldTextComponent, std::string>(
        "WorldTextComponent",
        "phase_mark",
        "Phase Mark",
        "string",
        [](WorldTextComponent* self) -> std::string& { return self->phase_mark; },
        [](WorldTextComponent* self, const std::string& value) { self->set_phase_mark(value); }
    );
    tc::InspectAccessorFieldRegistrar<WorldTextComponent, tc_vec3>(
        "WorldTextComponent",
        "local_offset",
        "Local Offset",
        "vec3",
        [](WorldTextComponent* self) {
            return tc_vec3{self->local_offset.x, self->local_offset.y, self->local_offset.z};
        },
        [](WorldTextComponent* self, tc_vec3 value) {
            self->set_local_offset(Vec3{value.x, value.y, value.z});
        }
    );
    tc::InspectAccessorFieldRegistrar<WorldTextComponent, tc_vec3>(
        "WorldTextComponent",
        "plane_normal",
        "Plane Normal",
        "vec3",
        [](WorldTextComponent* self) {
            return tc_vec3{self->plane_normal.x, self->plane_normal.y, self->plane_normal.z};
        },
        [](WorldTextComponent* self, tc_vec3 value) {
            self->set_plane_normal(Vec3{value.x, value.y, value.z});
        }
    );
    tc::InspectAccessorFieldRegistrar<WorldTextComponent, tc_vec3>(
        "WorldTextComponent",
        "text_up",
        "Text Up",
        "vec3",
        [](WorldTextComponent* self) {
            return tc_vec3{self->text_up.x, self->text_up.y, self->text_up.z};
        },
        [](WorldTextComponent* self, tc_vec3 value) {
            self->set_text_up(Vec3{value.x, value.y, value.z});
        }
    );
    inspect.add_with_callbacks<WorldTextComponent, Vec4>(
        "WorldTextComponent",
        "color",
        "Color",
        "color",
        [](WorldTextComponent* self) -> Vec4& { return self->color; },
        [](WorldTextComponent* self, const Vec4& value) { self->set_color(value); }
    );
    inspect.add_with_callbacks<WorldTextComponent, float>(
        "WorldTextComponent",
        "size",
        "Size",
        "float",
        [](WorldTextComponent* self) -> float& { return self->size; },
        [](WorldTextComponent* self, const float& value) { self->set_size(value); },
        0.001,
        10.0,
        0.01
    );
    tc::InspectAccessorFieldChoicesRegistrar<WorldTextComponent, int>(
        "WorldTextComponent",
        "anchor",
        "Anchor",
        "enum",
        [](WorldTextComponent* self) -> int { return static_cast<int>(self->anchor); },
        [](WorldTextComponent* self, int value) { self->set_anchor(static_cast<WorldTextAnchor>(value)); },
        {
            {"0", "Left"},
            {"1", "Center"},
            {"2", "Right"},
        }
    );
    tc::InspectAccessorFieldChoicesRegistrar<WorldTextComponent, int>(
        "WorldTextComponent",
        "orientation",
        "Orientation",
        "enum",
        [](WorldTextComponent* self) -> int { return static_cast<int>(self->orientation); },
        [](WorldTextComponent* self, int value) { self->set_orientation(static_cast<WorldTextOrientation>(value)); },
        {
            {"0", "Billboard"},
            {"1", "Fixed"},
        }
    );
    inspect.add_with_callbacks<WorldTextComponent, int>(
        "WorldTextComponent",
        "priority",
        "Priority",
        "int",
        [](WorldTextComponent* self) -> int& { return self->priority; },
        [](WorldTextComponent* self, const int& value) { self->set_priority(value); },
        -32768,
        32767,
        1
    );
    inspect.add_with_callbacks<WorldTextComponent, bool>(
        "WorldTextComponent",
        "depth_test",
        "Depth Test",
        "bool",
        [](WorldTextComponent* self) -> bool& { return self->depth_test; },
        [](WorldTextComponent* self, const bool& value) { self->set_depth_test(value); }
    );
    inspect.add_with_callbacks<WorldTextComponent, bool>(
        "WorldTextComponent",
        "depth_write",
        "Depth Write",
        "bool",
        [](WorldTextComponent* self) -> bool& { return self->depth_write; },
        [](WorldTextComponent* self, const bool& value) { self->set_depth_write(value); }
    );
    inspect.add_with_callbacks<WorldTextComponent, bool>(
        "WorldTextComponent",
        "blend",
        "Blend",
        "bool",
        [](WorldTextComponent* self) -> bool& { return self->blend; },
        [](WorldTextComponent* self, const bool& value) { self->set_blend(value); }
    );
    inspect.add_with_callbacks<WorldTextComponent, bool>(
        "WorldTextComponent",
        "cull",
        "Cull",
        "bool",
        [](WorldTextComponent* self) -> bool& { return self->cull; },
        [](WorldTextComponent* self, const bool& value) { self->set_cull(value); }
    );
}

WorldTextComponent::~WorldTextComponent() = default;

void WorldTextComponent::set_text(const std::string& value) {
    text = value;
}

void WorldTextComponent::set_font_path(const std::string& value) {
    if (font_path == value) {
        return;
    }
    font_path = value;
    font_.reset();
    loaded_font_path_.clear();
}

void WorldTextComponent::set_phase_mark(const std::string& value) {
    phase_mark = sanitize_phase_mark(value);
    material_ = TcMaterial();
}

void WorldTextComponent::set_local_offset(const Vec3& value) {
    local_offset = value;
}

void WorldTextComponent::set_plane_normal(const Vec3& value) {
    if (value.norm() <= 1.0e-8) {
        tc::Log::error("[WorldTextComponent] plane_normal is zero; using +Z");
        plane_normal = Vec3::unit_z();
        return;
    }
    plane_normal = value;
}

void WorldTextComponent::set_text_up(const Vec3& value) {
    if (value.norm() <= 1.0e-8) {
        tc::Log::error("[WorldTextComponent] text_up is zero; using +Y");
        text_up = Vec3::unit_y();
        return;
    }
    text_up = value;
}

void WorldTextComponent::set_color(const Vec4& value) {
    color = value;
}

void WorldTextComponent::set_size(float value) {
    size = std::max(value, 0.001f);
}

void WorldTextComponent::set_anchor(WorldTextAnchor value) {
    anchor = value;
}

void WorldTextComponent::set_orientation(WorldTextOrientation value) {
    switch (value) {
        case WorldTextOrientation::Fixed:
        case WorldTextOrientation::Billboard:
            orientation = value;
            break;
        default:
            tc::Log::error("[WorldTextComponent] invalid orientation %d; using Billboard",
                           static_cast<int>(value));
            orientation = WorldTextOrientation::Billboard;
            break;
    }
}

void WorldTextComponent::set_priority(int value) {
    priority = value;
}

void WorldTextComponent::set_depth_test(bool value) {
    depth_test = value;
}

void WorldTextComponent::set_depth_write(bool value) {
    depth_write = value;
}

void WorldTextComponent::set_blend(bool value) {
    blend = value;
}

void WorldTextComponent::set_cull(bool value) {
    cull = value;
}

std::string WorldTextComponent::anchor_name() const {
    switch (anchor) {
        case WorldTextAnchor::Left:
            return "left";
        case WorldTextAnchor::Right:
            return "right";
        case WorldTextAnchor::Center:
        default:
            return "center";
    }
}

void WorldTextComponent::set_anchor_name(const std::string& value) {
    std::string key = value;
    std::transform(key.begin(), key.end(), key.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    if (key == "left") {
        anchor = WorldTextAnchor::Left;
    } else if (key == "right") {
        anchor = WorldTextAnchor::Right;
    } else {
        anchor = WorldTextAnchor::Center;
    }
}

std::string WorldTextComponent::orientation_name() const {
    switch (orientation) {
        case WorldTextOrientation::Fixed:
            return "fixed";
        case WorldTextOrientation::Billboard:
        default:
            return "billboard";
    }
}

void WorldTextComponent::set_orientation_name(const std::string& value) {
    std::string key = value;
    std::transform(key.begin(), key.end(), key.begin(),
                   [](unsigned char c) { return static_cast<char>(std::tolower(c)); });
    if (key == "fixed" || key == "plane" || key == "world") {
        orientation = WorldTextOrientation::Fixed;
    } else {
        orientation = WorldTextOrientation::Billboard;
    }
}

tc_value WorldTextComponent::serialize_data() const {
    return Component::serialize_data();
}

void WorldTextComponent::deserialize_data(const tc_value* data, tc_scene_handle scene) {
    Component::deserialize_data(data, scene);
    phase_mark = sanitize_phase_mark(phase_mark);
    size = std::max(size, 0.001f);
    set_orientation(orientation);
    set_plane_normal(plane_normal);
    set_text_up(text_up);
    material_ = TcMaterial();
    font_.reset();
    loaded_font_path_.clear();
}

TcMaterial WorldTextComponent::effective_material() const {
    sync_material_phase();
    return material_;
}

tc_material_phase* WorldTextComponent::sync_material_phase() const {
    const std::string mark = sanitize_phase_mark(phase_mark);
    if (!material_.is_valid()) {
        material_ = TcMaterial::create("WorldTextMaterial", "");
        if (!material_.is_valid()) {
            tc::Log::error("[WorldTextComponent] failed to create internal material");
            return nullptr;
        }
        material_.set_shader_name("Text3DEngineVSFS");

        tc_shader_handle shader_handle =
            tgfx::register_builtin_shader_from_catalog(TEXT3D_SHADER_UUID);
        if (tc_shader_handle_is_invalid(shader_handle)) {
            tc::Log::error("[WorldTextComponent] failed to register text3d shader");
            material_ = TcMaterial();
            return nullptr;
        }

        tc_material_phase* created = material_.add_phase(shader_handle, mark.c_str(), priority);
        if (!created) {
            tc::Log::error("[WorldTextComponent] failed to create internal material phase");
            material_ = TcMaterial();
            return nullptr;
        }
    }

    tc_material* raw = material_.get();
    if (!raw || raw->phase_count == 0) {
        return nullptr;
    }

    tc_material_phase* phase = &raw->phases[0];
    std::strncpy(phase->phase_mark, mark.c_str(), TC_PHASE_MARK_MAX - 1);
    phase->phase_mark[TC_PHASE_MARK_MAX - 1] = '\0';
    phase->priority = priority;
    phase->state = make_text_render_state(*this);
    tc_material_phase_set_color(
        phase,
        static_cast<float>(color.x),
        static_cast<float>(color.y),
        static_cast<float>(color.z),
        static_cast<float>(color.w));
    return phase;
}

tgfx::FontAtlas* WorldTextComponent::ensure_font() const {
    std::string path = font_path.empty() ? find_default_font_path() : font_path;
    if (path.empty()) {
        tc::Log::error("[WorldTextComponent] no font_path set and no default system font found");
        return nullptr;
    }
    if (font_ && loaded_font_path_ == path) {
        return font_.get();
    }

    try {
        font_ = std::make_unique<tgfx::FontAtlas>(path, 16.0f);
        loaded_font_path_ = path;
    } catch (const std::exception& exc) {
        tc::Log::error("[WorldTextComponent] failed to load font '%s': %s",
                       path.c_str(), exc.what());
        font_.reset();
        loaded_font_path_.clear();
    }
    return font_.get();
}

std::set<std::string> WorldTextComponent::get_phase_marks() const {
    if (text.empty()) {
        return {};
    }
    return {sanitize_phase_mark(phase_mark)};
}

void WorldTextComponent::collect_shader_usages(
    const std::string& draw_phase_mark,
    int geometry_id,
    TcShader original_shader,
    const std::function<void(TcShader)>& emit
) {
    (void)draw_phase_mark;
    (void)geometry_id;
    if (original_shader.is_valid()) {
        emit(original_shader);
    }
}

void WorldTextComponent::draw_geometry(const RenderContext& context, int geometry_id) {
    (void)context;
    (void)geometry_id;
}

bool WorldTextComponent::collect_render_items(
    const tc_render_item_collect_context& context,
    tc_render_item_sink& sink)
{
    if (!sink.emit) {
        tc::Log::error("[WorldTextComponent] cannot emit render items: sink callback is null");
        return false;
    }
    if (!context.phase_mark || text.empty()) {
        return true;
    }

    const std::string mark = sanitize_phase_mark(phase_mark);
    if (context.phase_mark != mark) {
        return true;
    }

    tc_material_phase* phase = sync_material_phase();
    if (!phase) {
        return true;
    }

    tc_render_item item{};
    item.kind = TC_RENDER_ITEM_KIND_TEXT_BATCH;
    item.flags = TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX | TC_RENDER_ITEM_FLAG_HAS_MATERIAL_PHASE;
    item.component = tc_component_ptr();
    item.geometry_id = 0;
    item.material_phase = phase;
    item.material = tc_material_handle_invalid();
    item.material_phase_index = SIZE_MAX;
    tc_material_find_phase_ref(phase, &item.material, &item.material_phase_index);

    Mat44f model = get_model_matrix(entity());
    std::memcpy(item.model_matrix, model.data, sizeof(float) * 16);

    item.payload.text_batch.text = text.c_str();
    item.payload.text_batch.font_path = font_path.c_str();
    item.payload.text_batch.local_offset =
        tc_render_item_vec3{local_offset.x, local_offset.y, local_offset.z};
    item.payload.text_batch.plane_normal =
        tc_render_item_vec3{plane_normal.x, plane_normal.y, plane_normal.z};
    item.payload.text_batch.text_up =
        tc_render_item_vec3{text_up.x, text_up.y, text_up.z};
    item.payload.text_batch.color =
        tc_render_item_vec4{color.x, color.y, color.z, color.w};
    item.payload.text_batch.size = size;
    item.payload.text_batch.anchor = static_cast<uint32_t>(anchor);
    item.payload.text_batch.orientation = static_cast<uint32_t>(orientation);

    return sink.emit(&item, sink.user_data);
}

bool WorldTextComponent::encode_render_item_tgfx2(
    tgfx::RenderContext2& ctx2,
    const tc_render_item& item,
    const RenderItemDrawSubmitRequest& request)
{
    if (item.kind != TC_RENDER_ITEM_KIND_TEXT_BATCH) {
        tc::Log::error(
            "[WorldTextComponent] cannot encode item kind %u as text batch",
            item.kind);
        return false;
    }
    if (!request.draw_context) {
        tc::Log::error("[WorldTextComponent] cannot encode text batch without draw context");
        return false;
    }
    if (!item.payload.text_batch.text || item.payload.text_batch.text[0] == '\0') {
        return true;
    }

    tgfx::FontAtlas* font = ensure_font();
    if (!font) {
        return true;
    }
    if (!renderer_) {
        renderer_ = std::make_unique<tgfx::Text3DRenderer>(font);
    }

    const RenderContext& context = *request.draw_context;
    Mat44f mvp = context.projection * context.view;
    float text_right[3]{};
    float text_up_basis[3]{};
    WorldTextOrientation decoded_orientation = WorldTextOrientation::Billboard;
    if (!decode_text_orientation(
            item.payload.text_batch.orientation,
            decoded_orientation)) {
        tc::Log::error(
            "[WorldTextComponent] cannot encode text batch with invalid orientation %u",
            item.payload.text_batch.orientation);
        return false;
    }
    if (decoded_orientation == WorldTextOrientation::Fixed) {
        if (!make_fixed_text_basis(
                vec3_from_payload(item.payload.text_batch.plane_normal),
                vec3_from_payload(item.payload.text_batch.text_up),
                context.model,
                text_right,
                text_up_basis)) {
            return true;
        }
    } else {
        extract_view_row3(context.view, 0, text_right);
        extract_view_row3(context.view, 2, text_up_basis);
    }

    Vec3 world_pos = context.model.transform_point(
        vec3_from_payload(item.payload.text_batch.local_offset));

    tc_render_item_vec4 payload_color = item.payload.text_batch.color;
    if (context.has_override_color) {
        payload_color = tc_render_item_vec4{
            context.override_color.x,
            context.override_color.y,
            context.override_color.z,
            context.override_color.w};
    }

    WorldTextAnchor decoded_anchor = WorldTextAnchor::Center;
    if (!decode_text_anchor(item.payload.text_batch.anchor, decoded_anchor)) {
        tc::Log::error(
            "[WorldTextComponent] cannot encode text batch with invalid anchor %u",
            item.payload.text_batch.anchor);
        return false;
    }

    renderer_->begin(&ctx2, mvp.data, text_right, text_up_basis, font);
    renderer_->draw(
        item.payload.text_batch.text,
        tgfx::Text3DRenderer::DrawOptions{
            Vec3f{
                static_cast<float>(world_pos.x),
                static_cast<float>(world_pos.y),
                static_cast<float>(world_pos.z),
            },
            Color4{
                static_cast<float>(payload_color.x),
                static_cast<float>(payload_color.y),
                static_cast<float>(payload_color.z),
                static_cast<float>(payload_color.w),
            },
            item.payload.text_batch.size,
            to_tgfx_anchor(decoded_anchor),
        });
    renderer_->end();
    return true;
}

tc_mesh* WorldTextComponent::get_mesh_for_phase(const std::string& draw_phase_mark, int geometry_id) const {
    (void)draw_phase_mark;
    (void)geometry_id;
    return nullptr;
}

std::vector<GeometryDrawCall> WorldTextComponent::get_geometry_draws(
    const RenderContext& context,
    const std::string* draw_phase_mark
) {
    (void)context;
    std::vector<GeometryDrawCall> draws;
    if (text.empty()) {
        return draws;
    }
    const std::string mark = sanitize_phase_mark(phase_mark);
    if (draw_phase_mark && *draw_phase_mark != mark) {
        return draws;
    }
    if (tc_material_phase* phase = sync_material_phase()) {
        draws.emplace_back(phase, 0);
    }
    return draws;
}

} // namespace termin
