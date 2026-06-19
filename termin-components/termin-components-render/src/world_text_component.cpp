#include <termin/render/world_text_component.hpp>

#include <algorithm>
#include <cctype>
#include <cmath>
#include <cstring>
#include <filesystem>
#include <string>
#include <vector>

#include <tcbase/tc_log.hpp>
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
    const WorldTextComponent& component,
    const Mat44f& model,
    float text_right[3],
    float text_up[3])
{
    const Vec3 transformed_normal = model.transform_direction(component.plane_normal);
    Vec3 normal = normalized_or(transformed_normal, Vec3::unit_z());

    const Vec3 transformed_up = model.transform_direction(component.text_up);
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

} // namespace

WorldTextComponent::WorldTextComponent(const char* type_name)
    : Component(type_name)
{
    install_drawable_vtable(&_c);
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

bool WorldTextComponent::draw_tgfx2(tgfx::RenderContext2& ctx2,
                                    const RenderContext& context,
                                    const std::string& draw_phase_mark,
                                    tc_material_phase* phase,
                                    int geometry_id) {
    (void)phase;
    if (geometry_id != 0 || text.empty()) {
        return true;
    }
    if (draw_phase_mark != sanitize_phase_mark(phase_mark)) {
        return false;
    }

    tgfx::FontAtlas* font = ensure_font();
    if (!font) {
        return true;
    }
    if (!renderer_) {
        renderer_ = std::make_unique<tgfx::Text3DRenderer>(font);
    }

    Mat44f mvp = context.projection * context.view;
    float text_right[3]{};
    float text_up_basis[3]{};
    if (orientation == WorldTextOrientation::Fixed) {
        if (!make_fixed_text_basis(*this, context.model, text_right, text_up_basis)) {
            return true;
        }
    } else {
        extract_view_row3(context.view, 0, text_right);
        extract_view_row3(context.view, 2, text_up_basis);
    }

    Vec3 world_pos = context.model.transform_point(local_offset);
    float position[3] = {
        static_cast<float>(world_pos.x),
        static_cast<float>(world_pos.y),
        static_cast<float>(world_pos.z),
    };

    renderer_->begin(&ctx2, mvp.data, text_right, text_up_basis, font);
    renderer_->draw(
        text,
        position,
        static_cast<float>(color.x),
        static_cast<float>(color.y),
        static_cast<float>(color.z),
        static_cast<float>(color.w),
        size,
        to_tgfx_anchor(anchor));
    renderer_->end();
    return true;
}

bool WorldTextComponent::supports_direct_tgfx2_draw(
    const std::string& draw_phase_mark,
    int geometry_id,
    DirectTgfx2DrawKind kind
) const {
    return kind == DirectTgfx2DrawKind::MaterialPhase
        && geometry_id == 0
        && !text.empty()
        && draw_phase_mark == sanitize_phase_mark(phase_mark);
}

tc_mesh* WorldTextComponent::get_mesh_for_phase(const std::string& draw_phase_mark, int geometry_id) const {
    (void)draw_phase_mark;
    (void)geometry_id;
    return nullptr;
}

std::vector<GeometryDrawCall> WorldTextComponent::get_geometry_draws(const std::string* draw_phase_mark) {
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
