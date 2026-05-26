#include <termin/foliage/foliage_layer_component.hpp>

#include <any>
#include <cmath>
#include <cstddef>
#include <cstring>
#include <functional>
#include <limits>
#include <span>
#include <string>
#include <unordered_map>
#include <utility>
#include <vector>

#include <termin/foliage/foliage_data_registry.hpp>
#include <termin/geom/general_pose3.hpp>
#include <termin/render/material_ubo_runtime.hpp>
#include <inspect/tc_kind_cpp.hpp>
#include <tcbase/tc_log.hpp>
#include <tc_inspect_cpp.hpp>
#include <tgfx/resources/tc_mesh.h>
#include <tgfx/resources/tc_shader.h>
#include <tgfx/resources/tc_shader_registry.h>
#include <tgfx/tgfx_shader_handle.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/tc_shader_bridge.hpp>
#include <tgfx2/vertex_layout.hpp>

namespace termin {
namespace {

constexpr int FOLIAGE_GEOMETRY_ID = 0;

const char* FOLIAGE_VARIANT_VERT = R"(
#version 330 core

layout(std140, binding = 2) uniform PerFrame {
    mat4 u_view;
    mat4 u_projection;
    mat4 u_view_projection;
    mat4 u_inv_view;
    mat4 u_inv_proj;
    vec4 u_camera_position;
    vec2 u_resolution;
    float u_near;
    float u_far;
};

struct FoliagePushData {
    mat4 u_position_model;
    mat4 u_vector_model;
};
#ifdef VULKAN
layout(push_constant) uniform FoliagePushBlock { FoliagePushData pc; };
#else
layout(std140, binding = 14) uniform FoliagePushBlock { FoliagePushData pc; };
#endif

layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;
layout(location = 2) in vec2 a_uv;

layout(location = 8) in vec3 i_position;
layout(location = 9) in float i_yaw;
layout(location = 10) in vec3 i_normal;
layout(location = 11) in float i_seed;

out vec3 v_world_pos;
out vec3 v_normal;
out vec2 v_uv;
out mat3 v_TBN;
out vec3 v_tangent;
out float v_foliage_seed;

void main() {
    vec3 up = normalize(i_normal);
    // Keep yaw=0 aligned with ordinary mesh rendering on flat Z-up surfaces:
    // local X -> world X, local Y -> world Y, local Z -> world Z.
    vec3 helper = abs(up.z) > 0.85 ? vec3(0.0, 1.0, 0.0) : vec3(0.0, 0.0, 1.0);
    vec3 right = normalize(cross(helper, up));
    vec3 forward = cross(up, right);

    float c = cos(i_yaw);
    float s = sin(i_yaw);
    vec3 yaw_right = right * c + forward * s;
    vec3 yaw_forward = -right * s + forward * c;
    vec3 local_offset =
        yaw_right * a_position.x +
        yaw_forward * a_position.y +
        up * a_position.z;

    vec3 source_normal = length(a_normal) > 0.0001 ? normalize(a_normal) : vec3(0.0, 0.0, 1.0);
    vec3 local_normal = normalize(
        yaw_right * source_normal.x +
        yaw_forward * source_normal.y +
        up * source_normal.z
    );
    vec3 world_pos =
        (pc.u_position_model * vec4(i_position, 1.0)).xyz +
        (pc.u_vector_model * vec4(local_offset, 0.0)).xyz;
    vec3 world_normal = normalize((pc.u_vector_model * vec4(local_normal, 0.0)).xyz);

    v_world_pos = world_pos;
    v_normal = world_normal;
    v_uv = a_uv;
    v_TBN = mat3(0.0);
    v_tangent = vec3(0.0);
    v_foliage_seed = fract(i_seed * 0.61803398875);
    gl_Position = u_view_projection * vec4(world_pos, 1.0);
}
)";

const char* FOLIAGE_SHADOW_VARIANT_VERT = R"(
#version 450 core

layout(location = 0) in vec3 a_position;

layout(location = 8) in vec3 i_position;
layout(location = 9) in float i_yaw;
layout(location = 10) in vec3 i_normal;

layout(std140, binding = 0) uniform PerFrame {
    mat4 u_view;
    mat4 u_projection;
};

struct FoliagePushData {
    mat4 u_position_model;
    mat4 u_vector_model;
};
#ifdef VULKAN
layout(push_constant) uniform FoliagePushBlock { FoliagePushData pc; };
#else
layout(std140, binding = 14) uniform FoliagePushBlock { FoliagePushData pc; };
#endif

void main() {
    vec3 up = normalize(i_normal);
    // Keep yaw=0 aligned with ordinary mesh rendering on flat Z-up surfaces:
    // local X -> world X, local Y -> world Y, local Z -> world Z.
    vec3 helper = abs(up.z) > 0.85 ? vec3(0.0, 1.0, 0.0) : vec3(0.0, 0.0, 1.0);
    vec3 right = normalize(cross(helper, up));
    vec3 forward = cross(up, right);

    float c = cos(i_yaw);
    float s = sin(i_yaw);
    vec3 yaw_right = right * c + forward * s;
    vec3 yaw_forward = -right * s + forward * c;
    vec3 local_offset =
        yaw_right * a_position.x +
        yaw_forward * a_position.y +
        up * a_position.z;

    vec3 world_pos =
        (pc.u_position_model * vec4(i_position, 1.0)).xyz +
        (pc.u_vector_model * vec4(local_offset, 0.0)).xyz;
    gl_Position = u_projection * u_view * vec4(world_pos, 1.0);
}
)";

struct FoliageGpuInstance {
    float position[3];
    float yaw;
    float normal[3];
    float seed;
};

struct UploadedVertexStream {
    tgfx::BufferHandle buffer;
    uint64_t offset = 0;
};

struct TcShaderHash {
    size_t operator()(const TcShader& shader) const {
        return std::hash<uint32_t>()(shader.handle.index)
            ^ (std::hash<uint32_t>()(shader.handle.generation) << 1);
    }
};

struct TcShaderEqual {
    bool operator()(const TcShader& a, const TcShader& b) const {
        return a.handle.index == b.handle.index
            && a.handle.generation == b.handle.generation;
    }
};

std::unordered_map<TcShader, TcShader, TcShaderHash, TcShaderEqual>& foliage_shader_cache() {
    static std::unordered_map<TcShader, TcShader, TcShaderHash, TcShaderEqual> cache;
    return cache;
}

std::unordered_map<TcShader, TcShader, TcShaderHash, TcShaderEqual>& foliage_shadow_shader_cache() {
    static std::unordered_map<TcShader, TcShader, TcShaderHash, TcShaderEqual> cache;
    return cache;
}

TcShader get_foliage_instanced_shader(TcShader original_shader, bool shadow_variant = false) {
    if (!original_shader.is_valid()) {
        return TcShader();
    }
    const tc_shader_variant_op variant_op =
        shadow_variant ? TC_SHADER_VARIANT_FOLIAGE_SHADOW : TC_SHADER_VARIANT_FOLIAGE;
    if (original_shader.variant_op() == variant_op) {
        return original_shader;
    }

    auto& cache = shadow_variant ? foliage_shadow_shader_cache() : foliage_shader_cache();
    auto it = cache.find(original_shader);
    if (it != cache.end()) {
        TcShader& cached = it->second;
        if (!cached.variant_is_stale()) {
            return cached;
        }
        cache.erase(it);
    }

    const char* fragment_source = original_shader.fragment_source();
    if (!fragment_source || fragment_source[0] == '\0') {
        tc::Log::error(
            "[FoliageLayerComponent] cannot create foliage shader variant for '%s': fragment source is empty",
            original_shader.name()
        );
        return TcShader();
    }

    const char* geometry_source = original_shader.geometry_source();
    if (geometry_source && geometry_source[0] != '\0') {
        tc::Log::error(
            "[FoliageLayerComponent] cannot create foliage shader variant for '%s': geometry shaders are not supported yet",
            original_shader.name()
        );
        return TcShader();
    }

    std::string variant_name = std::string(original_shader.name())
        + (shadow_variant ? "_FoliageShadow" : "_Foliage");
    char variant_uuid[40];
    tc_shader_make_variant_uuid(
        variant_uuid,
        sizeof(variant_uuid),
        original_shader.uuid(),
        variant_op
    );

    tc_shader_handle handle = tc_shader_from_sources(
        shadow_variant ? FOLIAGE_SHADOW_VARIANT_VERT : FOLIAGE_VARIANT_VERT,
        fragment_source,
        nullptr,
        variant_name.c_str(),
        original_shader.source_path(),
        variant_uuid
    );
    if (tc_shader_handle_is_invalid(handle)) {
        tc::Log::error(
            "[FoliageLayerComponent] failed to create foliage shader variant for '%s'",
            original_shader.name()
        );
        return TcShader();
    }

    TcShader variant(handle);
    variant.set_features(original_shader.features());

    tc_shader* original_raw = original_shader.get();
    tc_shader* variant_raw = variant.get();
    if (original_raw && variant_raw) {
        tc_shader_set_material_ubo_layout(
            variant_raw,
            original_raw->material_ubo_entries,
            original_raw->material_ubo_entry_count,
            original_raw->material_ubo_block_size
        );
    }

    variant.set_variant_info(original_shader, variant_op);
    cache[original_shader] = variant;
    return variant;
}

bool convert_foliage_vertex_layout(const tc_mesh* mesh, tgfx::VertexBufferLayout& out) {
    if (!mesh || mesh->layout.stride == 0) {
        return false;
    }

    out.stride = mesh->layout.stride;
    out.per_instance = false;
    out.attributes.clear();
    bool has_position = false;
    for (uint8_t i = 0; i < mesh->layout.attrib_count; i++) {
        const tgfx_vertex_attrib& attr = mesh->layout.attribs[i];
        if (attr.location > 2) {
            continue;
        }
        if (static_cast<tgfx_attrib_type>(attr.type) != TGFX_ATTRIB_FLOAT32) {
            tc::Log::error(
                "[FoliageLayerComponent] prototype mesh attribute location=%u must be float, got type=%u",
                unsigned(attr.location),
                unsigned(attr.type)
            );
            return false;
        }

        tgfx::VertexFormat format = tgfx::VertexFormat::Float3;
        switch (attr.size) {
            case 1: format = tgfx::VertexFormat::Float; break;
            case 2: format = tgfx::VertexFormat::Float2; break;
            case 3: format = tgfx::VertexFormat::Float3; break;
            case 4: format = tgfx::VertexFormat::Float4; break;
            default:
                tc::Log::error(
                    "[FoliageLayerComponent] unsupported prototype mesh position size=%u",
                    unsigned(attr.size)
                );
                return false;
        }

        out.attributes.push_back({attr.location, format, attr.offset});
        if (attr.location == 0) {
            has_position = true;
        }
    }

    if (!has_position) {
        tc::Log::error("[FoliageLayerComponent] prototype mesh has no position attribute at location 0");
        return false;
    }
    return true;
}

tgfx::VertexBufferLayout foliage_instance_layout() {
    tgfx::VertexBufferLayout layout;
    layout.stride = sizeof(FoliageGpuInstance);
    layout.per_instance = true;
    layout.attributes = {
        {8, tgfx::VertexFormat::Float3, static_cast<uint32_t>(offsetof(FoliageGpuInstance, position))},
        {9, tgfx::VertexFormat::Float, static_cast<uint32_t>(offsetof(FoliageGpuInstance, yaw))},
        {10, tgfx::VertexFormat::Float3, static_cast<uint32_t>(offsetof(FoliageGpuInstance, normal))},
        {11, tgfx::VertexFormat::Float, static_cast<uint32_t>(offsetof(FoliageGpuInstance, seed))},
    };
    return layout;
}

tgfx::VertexBufferLayout foliage_instance_shadow_layout() {
    tgfx::VertexBufferLayout layout;
    layout.stride = sizeof(FoliageGpuInstance);
    layout.per_instance = true;
    layout.attributes = {
        {8, tgfx::VertexFormat::Float3, static_cast<uint32_t>(offsetof(FoliageGpuInstance, position))},
        {9, tgfx::VertexFormat::Float, static_cast<uint32_t>(offsetof(FoliageGpuInstance, yaw))},
        {10, tgfx::VertexFormat::Float3, static_cast<uint32_t>(offsetof(FoliageGpuInstance, normal))},
    };
    return layout;
}

UploadedVertexStream upload_vertex_stream(
    tgfx::RenderContext2& ctx2,
    const void* data,
    uint32_t size
) {
    if (!data || size == 0) {
        return {};
    }

    tgfx::IRenderDevice& device = ctx2.device();
    uint64_t offset = device.transient_vertex_write(data, size);
    if (offset != std::numeric_limits<uint64_t>::max()) {
        return {device.transient_vertex_buffer(), offset};
    }

    tgfx::BufferDesc desc;
    desc.size = size;
    desc.usage = tgfx::BufferUsage::Vertex | tgfx::BufferUsage::CopyDst;
    tgfx::BufferHandle buffer = device.create_buffer(desc);
    if (!buffer) {
        tc::Log::error("[FoliageLayerComponent] failed to allocate temporary vertex stream (%u bytes)", size);
        return {};
    }

    const auto* bytes = static_cast<const uint8_t*>(data);
    device.upload_buffer(buffer, std::span<const uint8_t>(bytes, size));
    ctx2.defer_destroy(buffer);
    return {buffer, 0};
}

FoliageGpuInstance make_gpu_instance(const FoliageInstance& instance) {
    FoliageGpuInstance gpu{};
    gpu.position[0] = instance.px;
    gpu.position[1] = instance.py;
    gpu.position[2] = instance.pz;
    gpu.yaw = instance.yaw;

    float nx = instance.nx;
    float ny = instance.ny;
    float nz = instance.nz;
    float len2 = nx * nx + ny * ny + nz * nz;
    if (!std::isfinite(len2) || len2 < 1.0e-8f) {
        nx = 0.0f;
        ny = 0.0f;
        nz = 1.0f;
        len2 = 1.0f;
    }
    const float inv_len = 1.0f / std::sqrt(len2);
    gpu.normal[0] = nx * inv_len;
    gpu.normal[1] = ny * inv_len;
    gpu.normal[2] = nz * inv_len;
    gpu.seed = static_cast<float>(instance.seed != 0 ? instance.seed : instance.variant + 1u);
    return gpu;
}

Mat44f layer_model_without_scale(const Entity& entity) {
    GeneralPose3 pose = entity.transform().global_pose();
    return Mat44f::compose(pose.lin, pose.ang, Vec3(1.0, 1.0, 1.0));
}

Mat44f layer_model_with_scale(const Entity& entity) {
    GeneralPose3 pose = entity.transform().global_pose();
    return Mat44f::compose(pose.lin, pose.ang, pose.scale);
}

struct FoliageDataHandleKindRegistrar {
    FoliageDataHandleKindRegistrar() {
        tc::KindRegistryCpp::instance().register_kind(
            "foliage_data_handle",
            [](const std::any& value) -> tc_value {
                const std::string uuid =
                    value.type() == typeid(std::string) ? std::any_cast<std::string>(value) : std::string();
                tc_value result = tc_value_dict_new();
                tc_value_dict_set(&result, "uuid", tc_value_string(uuid.c_str()));
                tc_value_dict_set(&result, "name", tc_value_string(""));
                return result;
            },
            [](const tc_value* value, void*) -> std::any {
                if (!value || value->type == TC_VALUE_NIL) {
                    return std::string();
                }
                if (value->type == TC_VALUE_STRING && value->data.s) {
                    return std::string(value->data.s);
                }
                if (value->type == TC_VALUE_DICT) {
                    tc_value* uuid = tc_value_dict_get(const_cast<tc_value*>(value), "uuid");
                    if (uuid && uuid->type == TC_VALUE_STRING && uuid->data.s) {
                        return std::string(uuid->data.s);
                    }
                }
                return std::string();
            }
        );
    }
};

FoliageDataHandleKindRegistrar foliage_data_handle_kind_registrar;

} // namespace

FoliageLayerComponent::FoliageLayerComponent()
    : CxxComponent("FoliageLayerComponent")
{
    install_drawable_vtable(&_c);
}

void FoliageLayerComponent::register_type() {
    auto& component_registry = ComponentRegistry::instance();
    if (!component_registry.has("FoliageLayerComponent")) {
        component_registry.register_native(
            "FoliageLayerComponent",
            &CxxComponentFactoryData<FoliageLayerComponent>::create,
            nullptr,
            "Component"
        );
    }

    auto& inspect = tc::InspectRegistry::instance();
    inspect.set_type_parent("FoliageLayerComponent", "Component");
    if (!inspect.find_field("FoliageLayerComponent", "enabled")) {
        inspect.add<FoliageLayerComponent, bool>(
            "FoliageLayerComponent",
            &FoliageLayerComponent::enabled,
            "enabled",
            "Enabled",
            "bool"
        );
    }
    if (!inspect.find_field("FoliageLayerComponent", "prototype_mesh")) {
        inspect.add<FoliageLayerComponent, TcMesh>(
            "FoliageLayerComponent",
            &FoliageLayerComponent::prototype_mesh,
            "prototype_mesh",
            "Prototype Mesh",
            "tc_mesh"
        );
    }
    if (!inspect.find_field("FoliageLayerComponent", "material")) {
        inspect.add<FoliageLayerComponent, TcMaterial>(
            "FoliageLayerComponent",
            &FoliageLayerComponent::material,
            "material",
            "Material",
            "tc_material"
        );
    }
    if (!inspect.find_field("FoliageLayerComponent", "layer_name")) {
        inspect.add<FoliageLayerComponent, std::string>(
            "FoliageLayerComponent",
            &FoliageLayerComponent::layer_name,
            "layer_name",
            "Layer Name",
            "string"
        );
    }
    if (!inspect.find_field("FoliageLayerComponent", "density")) {
        inspect.add<FoliageLayerComponent, double>(
            "FoliageLayerComponent",
            &FoliageLayerComponent::density,
            "density",
            "Density",
            "double"
        );
    }
    if (!inspect.find_field("FoliageLayerComponent", "min_spacing")) {
        inspect.add<FoliageLayerComponent, double>(
            "FoliageLayerComponent",
            &FoliageLayerComponent::min_spacing,
            "min_spacing",
            "Min Spacing",
            "double"
        );
    }
    if (!inspect.find_field("FoliageLayerComponent", "scale_min")) {
        inspect.add<FoliageLayerComponent, double>(
            "FoliageLayerComponent",
            &FoliageLayerComponent::scale_min,
            "scale_min",
            "Scale Min",
            "double"
        );
    }
    if (!inspect.find_field("FoliageLayerComponent", "scale_max")) {
        inspect.add<FoliageLayerComponent, double>(
            "FoliageLayerComponent",
            &FoliageLayerComponent::scale_max,
            "scale_max",
            "Scale Max",
            "double"
        );
    }
    if (!inspect.find_field("FoliageLayerComponent", "slope_limit_degrees")) {
        inspect.add<FoliageLayerComponent, double>(
            "FoliageLayerComponent",
            &FoliageLayerComponent::slope_limit_degrees,
            "slope_limit_degrees",
            "Slope Limit",
            "double"
        );
    }
}

std::set<std::string> FoliageLayerComponent::get_phase_marks() const {
    if (!enabled || foliage_uuid.empty() || !prototype_mesh.is_valid() || !material.is_valid()) {
        return {};
    }

    std::set<std::string> marks;
    tc_material* mat = material.get();
    if (mat) {
        for (size_t i = 0; i < mat->phase_count; i++) {
            marks.insert(mat->phases[i].phase_mark);
        }
    }
    return marks;
}

void FoliageLayerComponent::draw_geometry(const RenderContext& context, int geometry_id) {
    (void)context;
    (void)geometry_id;
    // Foliage is rendered through draw_tgfx2() as a single instanced batch.
}

std::vector<GeometryDrawCall> FoliageLayerComponent::get_geometry_draws(const std::string* phase_mark) {
    std::vector<GeometryDrawCall> draws;
    if (!enabled || foliage_uuid.empty() || !prototype_mesh.is_valid() || !material.is_valid()) {
        return draws;
    }

    TcFoliageData foliage = TcFoliageData::from_uuid(foliage_uuid);
    if (!foliage.is_valid() || !foliage.ensure_loaded() || foliage.instance_count() == 0) {
        return draws;
    }

    tc_material* mat = material.get();
    if (!mat) {
        return draws;
    }

    if (phase_mark) {
        tc_material_phase* phases[TC_MATERIAL_MAX_PHASES];
        size_t count = tc_material_get_phases_for_mark(mat, phase_mark->c_str(), phases, TC_MATERIAL_MAX_PHASES);
        draws.reserve(count);
        for (size_t i = 0; i < count; i++) {
            draws.emplace_back(phases[i], FOLIAGE_GEOMETRY_ID);
        }
        return draws;
    }

    draws.reserve(mat->phase_count);
    for (size_t i = 0; i < mat->phase_count; i++) {
        draws.emplace_back(&mat->phases[i], FOLIAGE_GEOMETRY_ID);
    }
    return draws;
}

tc_mesh* FoliageLayerComponent::get_mesh_for_phase(const std::string& phase_mark, int geometry_id) const {
    (void)phase_mark;
    (void)geometry_id;
    // Returning nullptr opts ColorPass into the direct draw_tgfx2 path.
    return nullptr;
}

TcShader FoliageLayerComponent::override_shader(
    const std::string& phase_mark,
    int geometry_id,
    TcShader original_shader
) {
    if (geometry_id != FOLIAGE_GEOMETRY_ID || !original_shader.is_valid()) {
        return original_shader;
    }

    TcShader variant = get_foliage_instanced_shader(original_shader, phase_mark == "shadow");
    if (!variant.is_valid()) {
        tc::Log::error(
            "[FoliageLayerComponent] failed to create foliage shader variant for '%s'",
            original_shader.name()
        );
        return TcShader();
    }
    return variant;
}

void FoliageLayerComponent::collect_shader_usages(
    const std::string& phase_mark,
    int geometry_id,
    TcShader original_shader,
    const std::function<void(TcShader)>& emit
) {
    emit(original_shader);
    if (geometry_id != FOLIAGE_GEOMETRY_ID || !original_shader.is_valid()) {
        return;
    }

    TcShader variant = get_foliage_instanced_shader(original_shader, phase_mark == "shadow");
    if (variant.is_valid()) {
        emit(variant);
    }
}

bool FoliageLayerComponent::draw_tgfx2(
    tgfx::RenderContext2& ctx2,
    const RenderContext& context,
    const std::string& phase_mark,
    tc_material_phase* phase,
    int geometry_id
) {
    (void)phase_mark;
    if (!enabled || geometry_id != FOLIAGE_GEOMETRY_ID) {
        return false;
    }
    if (foliage_uuid.empty()) {
        return false;
    }

    tc_mesh* mesh = prototype_mesh.get();
    if (!mesh) {
        tc::Log::error("[FoliageLayerComponent] cannot draw foliage: prototype mesh is missing");
        return false;
    }

    tc_material* mat = material.get();
    if (!mat) {
        tc::Log::error("[FoliageLayerComponent] cannot draw foliage: material is missing");
        return false;
    }
    if (!phase) {
        tc::Log::error("[FoliageLayerComponent] cannot draw foliage: material phase is missing");
        return false;
    }

    TcFoliageData foliage = TcFoliageData::from_uuid(foliage_uuid);
    if (!foliage.is_valid()) {
        tc::Log::error(
            "[FoliageLayerComponent] cannot draw foliage: asset '%s' is not declared",
            foliage_uuid.c_str()
        );
        return false;
    }
    if (!foliage.ensure_loaded()) {
        tc::Log::error(
            "[FoliageLayerComponent] cannot draw foliage: asset '%s' failed to load",
            foliage_uuid.c_str()
        );
        return false;
    }
    FoliageData* data = foliage.get();
    if (!data || data->instances.empty()) {
        return true;
    }
    if (data->instances.size() > static_cast<size_t>(std::numeric_limits<uint32_t>::max())) {
        tc::Log::error(
            "[FoliageLayerComponent] cannot draw foliage: instance count %zu exceeds uint32 draw limit",
            data->instances.size()
        );
        return false;
    }

    tgfx::VertexBufferLayout vertex_layout;
    if (!convert_foliage_vertex_layout(mesh, vertex_layout)) {
        return false;
    }
    if (!mesh->indices || mesh->index_count == 0) {
        tc::Log::error("[FoliageLayerComponent] prototype mesh must be indexed for instanced foliage draw");
        return false;
    }
    if (mesh->index_count > static_cast<size_t>(std::numeric_limits<uint32_t>::max())) {
        tc::Log::error("[FoliageLayerComponent] prototype mesh index count exceeds uint32 draw limit");
        return false;
    }

    std::vector<FoliageGpuInstance> instances;
    instances.reserve(data->instances.size());
    for (const FoliageInstance& instance : data->instances) {
        instances.push_back(make_gpu_instance(instance));
    }

    UploadedVertexStream instance_stream = upload_vertex_stream(
        ctx2,
        instances.data(),
        static_cast<uint32_t>(instances.size() * sizeof(FoliageGpuInstance))
    );
    if (!instance_stream.buffer) {
        return false;
    }

    auto [vertex_buffer, index_buffer] = ctx2.device().ensure_tc_mesh(mesh);
    if (!vertex_buffer || !index_buffer) {
        tc::Log::error("[FoliageLayerComponent] failed to upload prototype mesh for instanced draw");
        return false;
    }

    TcShader shader = context.current_tc_shader;
    if (!shader.is_valid()) {
        shader = get_foliage_instanced_shader(TcShader(phase->shader), phase_mark == "shadow");
    } else if (shader.variant_op() != TC_SHADER_VARIANT_FOLIAGE
        && shader.variant_op() != TC_SHADER_VARIANT_FOLIAGE_SHADOW) {
        shader = get_foliage_instanced_shader(shader, phase_mark == "shadow");
    }
    if (!shader.is_valid()) {
        tc::Log::error("[FoliageLayerComponent] cannot draw foliage: shader variant is invalid");
        return false;
    }
    tc_shader* raw_shader = tc_shader_get(shader.handle);
    tgfx::ShaderHandle vs2;
    tgfx::ShaderHandle fs2;
    if (!raw_shader || !tc_shader_ensure_tgfx2(raw_shader, &ctx2.device(), &vs2, &fs2)) {
        tc::Log::error("[FoliageLayerComponent] failed to prepare instanced shader");
        return false;
    }

    struct ColorPushData {
        float u_position_model[16];
        float u_vector_model[16];
    };
    ColorPushData push{};
    Mat44f position_model = layer_model_with_scale(entity());
    Mat44f vector_model = layer_model_without_scale(entity());
    std::memcpy(push.u_position_model, position_model.data, sizeof(push.u_position_model));
    std::memcpy(push.u_vector_model, vector_model.data, sizeof(push.u_vector_model));

    ctx2.bind_shader(vs2, fs2);
    apply_material_phase_ubo_runtime(
        phase,
        raw_shader,
        TC_MATERIAL_UBO_BINDING_SLOT,
        4,
        ctx2.device(),
        ctx2
    );
    ctx2.set_push_constants(&push, sizeof(push));
    ctx2.set_topology(mesh->draw_mode == TC_DRAW_LINES
        ? tgfx::PrimitiveTopology::LineList
        : tgfx::PrimitiveTopology::TriangleList);
    ctx2.set_vertex_layouts({
        vertex_layout,
        phase_mark == "shadow" ? foliage_instance_shadow_layout() : foliage_instance_layout()
    });
    ctx2.draw_indexed_instanced(
        vertex_buffer,
        0,
        index_buffer,
        0,
        instance_stream.buffer,
        instance_stream.offset,
        static_cast<uint32_t>(mesh->index_count),
        static_cast<uint32_t>(instances.size())
    );
    return true;
}

namespace {

tc::InspectAccessorFieldRegistrar<FoliageLayerComponent, std::string>
    foliage_layer_asset_field_reg{
        "FoliageLayerComponent",
        "foliage",
        "Foliage Data",
        "foliage_data_handle",
        [](FoliageLayerComponent* self) { return self->foliage_uuid; },
        [](FoliageLayerComponent* self, std::string value) { self->foliage_uuid = std::move(value); }
    };

} // namespace

REGISTER_COMPONENT(FoliageLayerComponent, Component);

} // namespace termin
