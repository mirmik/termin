#include <termin/foliage/foliage_layer_component.hpp>

#include <any>
#include <cmath>
#include <cstddef>
#include <cstring>
#include <functional>
#include <initializer_list>
#include <limits>
#include <span>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

#include <termin/foliage/foliage_data_registry.hpp>
#include <termin/geom/general_pose3.hpp>
#include <termin/render/material_pipeline.hpp>
#include <termin/render/render_item_submission.hpp>
#include <termin/render/tgfx2_bridge.hpp>
#include <inspect/tc_kind_cpp.hpp>
#include <tcbase/tc_log.hpp>
#include <tc_inspect_cpp.hpp>
#include <tgfx/resources/tc_mesh.h>
#include <tgfx/resources/tc_shader.h>
#include <tgfx/tgfx_shader_handle.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/vertex_layout.hpp>

namespace termin {
namespace {

constexpr int FOLIAGE_GEOMETRY_ID = 0;

struct FoliageGpuInstance {
    float position[3];
    float yaw;
    float normal[3];
    float seed;
};

struct UploadedBuffer {
    tgfx::BufferHandle buffer;
    uint64_t offset = 0;
};

struct MeshBindingReleaseGuard {
    tgfx::IRenderDevice& device;
    const termin::Tgfx2MeshBinding& binding;

    ~MeshBindingReleaseGuard() {
        termin::release_mesh_binding(device, binding);
    }
};

TcShader get_foliage_instanced_shader(
    TcShader original_shader,
    const MaterialPipelinePassContract& pass_contract)
{
    if (!pass_contract.foliage_vertex_transform.has_value()) {
        return TcShader();
    }
    const VertexTransformContract& foliage_transform =
        *pass_contract.foliage_vertex_transform;
    const bool shadow_variant =
        foliage_transform.kind == VertexTransformKind::FoliageShadow;
    MaterialShaderOverrideRequest request{};
    request.original_shader = original_shader;
    request.vertex_transform_kind = foliage_transform.kind;
    request.pass_contract = pass_contract;
    request.vertex_transform_contract = foliage_transform;
    request.shader_variant_op = shadow_variant
        ? TC_SHADER_VARIANT_FOLIAGE_SHADOW
        : TC_SHADER_VARIANT_FOLIAGE;
    request.debug_context = "FoliageLayerComponent";
    return assemble_material_shader_override(request);
}

MaterialPipelinePassContract legacy_foliage_material_pass_contract()
{
    MaterialPipelinePassContract contract;
    contract.debug_name = "legacy_foliage_material";
    contract.required_material_fragment_input =
        material_pipeline_standard_material_fragment_interface();
    contract.uses_material_fragment = true;

    MaterialFragmentInterface fragment_input =
        material_pipeline_standard_material_fragment_interface();
    contract.static_vertex_transform =
        material_pipeline_make_static_vertex_transform_contract(
            "static",
            material_pipeline_full_material_mesh_input(),
            fragment_input,
            material_pipeline_common_vertex_resources("draw_data"));
    contract.foliage_vertex_transform =
        material_pipeline_make_foliage_vertex_transform_contract(
            VertexTransformKind::Foliage,
            "foliage",
            "termin-engine-foliage-instanced",
            material_pipeline_foliage_material_mesh_input(),
            fragment_input,
            material_pipeline_foliage_vertex_resources());
    return contract;
}

MaterialPipelinePassContract legacy_foliage_shadow_pass_contract()
{
    MaterialPipelinePassContract contract;
    contract.debug_name = "legacy_foliage_shadow";
    contract.required_material_fragment_input = MaterialFragmentInterface{};
    contract.uses_material_fragment = true;

    MaterialFragmentInterface fragment_input =
        material_pipeline_standard_material_fragment_interface();
    contract.static_vertex_transform =
        material_pipeline_make_static_vertex_transform_contract(
            "static_shadow",
            material_pipeline_position_mesh_input(),
            fragment_input,
            material_pipeline_common_vertex_resources("shadow_draw"));
    contract.foliage_vertex_transform =
        material_pipeline_make_foliage_vertex_transform_contract(
            VertexTransformKind::FoliageShadow,
            "foliage_shadow",
            "termin-engine-foliage-shadow",
            material_pipeline_position_mesh_input(),
            fragment_input,
            material_pipeline_foliage_vertex_resources());
    return contract;
}

bool shader_contract_requires_foliage_instances(TcShader shader)
{
    tc_shader_contract_view contract{};
    if (!tc_shader_get_contract_view(shader.get(), &contract)) {
        return false;
    }
    for (uint32_t i = 0; i < contract.resource_count; ++i) {
        const tc_shader_resource_requirement& resource = contract.resources[i];
        if (std::strncmp(
                resource.name,
                "foliage_instances",
                TC_SHADER_RESOURCE_NAME_MAX) == 0 &&
            resource.kind == TC_SHADER_RESOURCE_STORAGE_BUFFER) {
            return true;
        }
    }
    return false;
}

bool validate_foliage_vertex_layout(
    const tgfx::VertexLayoutDesc& layout,
    std::initializer_list<std::string_view> required_semantics,
    const char* variant_name)
{
    bool ok = true;
    for (std::string_view semantic : required_semantics) {
        if (!tgfx::vertex_layout_has_semantic(layout, semantic)) {
            tc::Log::error(
                "[FoliageLayerComponent] prototype mesh is incompatible with %s foliage shader: "
                "missing '%.*s' vertex attribute semantic",
                variant_name,
                static_cast<int>(semantic.size()),
                semantic.data());
            ok = false;
        }
    }
    return ok;
}

bool build_foliage_vertex_layout(
    const termin::Tgfx2MeshBinding& binding,
    bool shadow_variant,
    tgfx::VertexLayoutDesc& out)
{
    if (shadow_variant) {
        const std::initializer_list<std::string_view> required = {"position"};
        if (!validate_foliage_vertex_layout(binding.layout_desc, required, "shadow")) {
            return false;
        }
        out = tgfx::filter_vertex_layout_to_semantics(
            binding.layout_desc,
            required,
            true);
        return true;
    }

    const std::initializer_list<std::string_view> required = {"position", "normal", "uv"};
    if (!validate_foliage_vertex_layout(binding.layout_desc, required, "material")) {
        return false;
    }
    out = tgfx::filter_vertex_layout_to_semantics(
        binding.layout_desc,
        required,
        true);
    return true;
}

UploadedBuffer upload_storage_buffer(
    tgfx::RenderContext2& ctx2,
    const void* data,
    uint32_t size,
    uint32_t structured_stride
) {
    if (!data || size == 0) {
        return {};
    }

    tgfx::IRenderDevice& device = ctx2.device();
    tgfx::BufferDesc desc;
    desc.size = size;
    desc.usage = tgfx::BufferUsage::Storage | tgfx::BufferUsage::CopyDst;
    desc.structured_stride = structured_stride;
    tgfx::BufferHandle buffer = device.create_buffer(desc);
    if (!buffer) {
        tc::Log::error("[FoliageLayerComponent] failed to allocate temporary storage buffer (%u bytes)", size);
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

bool foliage_render_item_draw_encoder(
    tgfx::RenderContext2& ctx,
    const tc_render_item& item,
    const RenderItemDrawSubmitRequest& request,
    void* user_data)
{
    (void)user_data;
    if (item.kind != TC_RENDER_ITEM_KIND_FOLIAGE_BATCH) {
        tc::Log::error(
            "[FoliageLayerComponent] foliage encoder received unsupported item kind %u",
            item.kind);
        return false;
    }
    CxxComponent* component = CxxComponent::from_tc(item.component);
    auto* foliage = dynamic_cast<FoliageLayerComponent*>(component);
    if (!foliage) {
        const char* type_name = component ? component->type_name() : "<null>";
        tc::Log::error(
            "[FoliageLayerComponent] foliage RenderItem component is not FoliageLayerComponent: type='%s'",
            type_name ? type_name : "<unknown>");
        return false;
    }
    return foliage->encode_render_item_tgfx2(ctx, item, request);
}

RenderItemTaskRejection foliage_render_item_task_shader_planner(
    const RenderItemTaskPlanningRequest& request,
    RenderItemTaskShaderPlan& out_plan,
    const char*& out_detail,
    void* user_data)
{
    (void)user_data;
    if (!request.item || request.item->kind != TC_RENDER_ITEM_KIND_FOLIAGE_BATCH ||
        !request.contract) {
        out_detail = "foliage planner received an invalid request";
        return RenderItemTaskRejection::ShaderPlanningRejected;
    }
    out_plan.final_shader = request.candidate_shader;
    out_plan.has_vertex_transform_kind = true;
    out_plan.vertex_transform_kind =
        request.contract->pass_semantic == RenderItemPassSemantic::Shadow
        ? VertexTransformKind::FoliageShadow
        : VertexTransformKind::Foliage;
    out_detail = nullptr;
    return RenderItemTaskRejection::None;
}

void ensure_foliage_render_item_encoder_registered()
{
    static bool registered = false;
    if (registered) {
        return;
    }

    RenderItemDrawEncoderDesc desc{};
    desc.encode = foliage_render_item_draw_encoder;
    desc.plan_task_shader = foliage_render_item_task_shader_planner;
    desc.debug_name = "FoliageLayerComponent";
    desc.capabilities.pass_semantic_mask =
        render_item_pass_semantic_bit(RenderItemPassSemantic::Color)
        | render_item_pass_semantic_bit(RenderItemPassSemantic::Shadow);
    desc.capabilities.vertex_transform_kind_mask =
        render_item_vertex_transform_kind_bit(VertexTransformKind::Foliage)
        | render_item_vertex_transform_kind_bit(VertexTransformKind::FoliageShadow);
    desc.capabilities.supported_task_input_mask =
        render_item_task_input_bit(RenderItemTaskInput::DrawContext)
        | render_item_task_input_bit(RenderItemTaskInput::ModelMatrix);
    desc.capabilities.required_task_input_mask =
        render_item_task_input_bit(RenderItemTaskInput::DrawContext);
    desc.capabilities.requires_draw_context = true;
    desc.capabilities.consumes_common_resources = true;
    registered = register_render_item_draw_encoder(TC_RENDER_ITEM_KIND_FOLIAGE_BATCH, desc);
}

void register_foliage_data_handle_kind() {
    if (tc::KindRegistryCpp::instance().has("foliage_data_handle")) {
        return;
    }
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

} // namespace

FoliageLayerComponent::FoliageLayerComponent()
    : CxxComponent("FoliageLayerComponent")
{
    install_drawable_vtable(&_c);
}

void FoliageLayerComponent::register_type() {
    ensure_foliage_render_item_encoder_registered();
    register_foliage_data_handle_kind();

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
    tc::InspectAccessorFieldRegistrar<FoliageLayerComponent, std::string>(
        "FoliageLayerComponent",
        "foliage",
        "Foliage Data",
        "foliage_data_handle",
        [](FoliageLayerComponent* self) { return self->foliage_uuid; },
        [](FoliageLayerComponent* self, std::string value) { self->foliage_uuid = std::move(value); }
    );
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

TcShader FoliageLayerComponent::override_shader(
    const std::string& phase_mark,
    int geometry_id,
    TcShader original_shader
) {
    ShaderOverrideContext context;
    context.phase_mark = phase_mark;
    context.geometry_id = geometry_id;
    context.original_shader = original_shader;
    if (phase_mark == "shadow") {
        context.pass_contract = legacy_foliage_shadow_pass_contract();
    } else {
        context.pass_contract = legacy_foliage_material_pass_contract();
    }
    return override_shader_with_context(context);
}

TcShader FoliageLayerComponent::override_shader_with_context(
    const ShaderOverrideContext& context
) {
    const std::string& phase_mark = context.phase_mark;
    const int geometry_id = context.geometry_id;
    TcShader original_shader = context.original_shader;

    if (geometry_id != FOLIAGE_GEOMETRY_ID || !original_shader.is_valid()) {
        return original_shader;
    }
    if (!context.pass_contract.foliage_vertex_transform.has_value()) {
        return original_shader;
    }

    TcShader variant = get_foliage_instanced_shader(
        original_shader,
        context.pass_contract);
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
    TcShader variant = get_foliage_instanced_shader(
        original_shader,
        phase_mark == "shadow"
            ? legacy_foliage_shadow_pass_contract()
            : legacy_foliage_material_pass_contract());
    if (variant.is_valid()) {
        emit(variant);
    }
}

bool FoliageLayerComponent::collect_render_items(
    const tc_render_item_collect_context& context,
    tc_render_item_sink& sink
) {
    if (!sink.emit) {
        tc::Log::error("[FoliageLayerComponent] cannot emit render items: sink callback is null");
        return false;
    }
    if (!context.phase_mark || context.phase_mark[0] == '\0') {
        return true;
    }
    if (!enabled || foliage_uuid.empty() || !prototype_mesh.is_valid() || !material.is_valid()) {
        return true;
    }

    TcFoliageData foliage = TcFoliageData::from_uuid(foliage_uuid);
    if (!foliage.is_valid() || !foliage.ensure_loaded() || foliage.instance_count() == 0) {
        return true;
    }

    tc_mesh* mesh = prototype_mesh.get();
    if (!mesh) {
        tc::Log::error("[FoliageLayerComponent] cannot emit foliage RenderItem: prototype mesh is missing");
        return false;
    }
    tc_mesh_handle mesh_handle = tc_mesh_find(mesh->header.uuid);
    if (tc_mesh_handle_is_invalid(mesh_handle)) {
        tc::Log::error(
            "[FoliageLayerComponent] cannot emit foliage RenderItem: prototype mesh has no stable registry handle");
        return false;
    }

    tc_material* mat = material.get();
    if (!mat) {
        tc::Log::error("[FoliageLayerComponent] cannot emit foliage RenderItem: material is missing");
        return false;
    }

    tc_material_phase* phases[TC_MATERIAL_MAX_PHASES];
    size_t count = tc_material_get_phases_for_mark(
        mat,
        context.phase_mark,
        phases,
        TC_MATERIAL_MAX_PHASES);
    for (size_t i = 0; i < count; ++i) {
        tc_material_phase* phase = phases[i];
        if (!phase) {
            continue;
        }

        tc_render_item item{};
        item.kind = TC_RENDER_ITEM_KIND_FOLIAGE_BATCH;
        item.flags = TC_RENDER_ITEM_FLAG_HAS_MODEL_MATRIX | TC_RENDER_ITEM_FLAG_HAS_MATERIAL_PHASE;
        item.component = tc_component_ptr();
        item.geometry_id = FOLIAGE_GEOMETRY_ID;
        item.material_phase = phase;
        item.material = tc_material_handle_invalid();
        item.material_phase_index = SIZE_MAX;
        tc_material_find_phase_ref(phase, &item.material, &item.material_phase_index);

        Mat44f model = get_model_matrix(entity());
        std::memcpy(item.model_matrix, model.data, sizeof(float) * 16);

        item.payload.foliage_batch.prototype_mesh = mesh;
        item.payload.foliage_batch.prototype_mesh_handle = mesh_handle;
        item.payload.foliage_batch.foliage_uuid = foliage_uuid.c_str();

        if (!sink.emit(&item, sink.user_data)) {
            return false;
        }
    }
    return true;
}

bool FoliageLayerComponent::encode_render_item_tgfx2(
    tgfx::RenderContext2& ctx2,
    const tc_render_item& item,
    const RenderItemDrawSubmitRequest& request
) {
    if (item.kind != TC_RENDER_ITEM_KIND_FOLIAGE_BATCH) {
        tc::Log::error(
            "[FoliageLayerComponent] cannot encode item kind %u as foliage batch",
            item.kind);
        return false;
    }
    if (!request.draw_context) {
        tc::Log::error("[FoliageLayerComponent] cannot encode foliage batch without draw context");
        return false;
    }
    if (!enabled || item.geometry_id != FOLIAGE_GEOMETRY_ID) {
        return false;
    }

    const RenderContext& context = *request.draw_context;
    const char* item_foliage_uuid = item.payload.foliage_batch.foliage_uuid;
    if (!item_foliage_uuid || item_foliage_uuid[0] == '\0') {
        tc::Log::error("[FoliageLayerComponent] cannot draw foliage: RenderItem has empty foliage asset");
        return false;
    }

    tc_mesh* mesh = item.payload.foliage_batch.prototype_mesh;
    if (!mesh) {
        tc::Log::error("[FoliageLayerComponent] cannot draw foliage: prototype mesh is missing");
        return false;
    }

    tc_material_phase* phase = request.material_phase
        ? request.material_phase
        : item.material_phase;
    if (!phase) {
        tc::Log::error("[FoliageLayerComponent] cannot draw foliage: material phase is missing");
        return false;
    }

    TcFoliageData foliage = TcFoliageData::from_uuid(item_foliage_uuid);
    if (!foliage.is_valid()) {
        tc::Log::error(
            "[FoliageLayerComponent] cannot draw foliage: asset '%s' is not declared",
            item_foliage_uuid
        );
        return false;
    }
    if (!foliage.ensure_loaded()) {
        tc::Log::error(
            "[FoliageLayerComponent] cannot draw foliage: asset '%s' failed to load",
            item_foliage_uuid
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

    if (!mesh->indices || mesh->index_count == 0) {
        tc::Log::error("[FoliageLayerComponent] prototype mesh must be indexed for instanced foliage draw");
        return false;
    }
    if (mesh->index_count > static_cast<size_t>(std::numeric_limits<uint32_t>::max())) {
        tc::Log::error("[FoliageLayerComponent] prototype mesh index count exceeds uint32 draw limit");
        return false;
    }

    termin::Tgfx2MeshBinding mesh_binding = termin::wrap_mesh_as_tgfx2(ctx2.device(), mesh);
    MeshBindingReleaseGuard mesh_binding_guard{ctx2.device(), mesh_binding};
    if (mesh_binding.index_count == 0) {
        tc::Log::error("[FoliageLayerComponent] failed to upload prototype mesh for instanced draw");
        return false;
    }

    const MaterialPipelinePassContract& pass_contract = context.pass_contract;
    if (!pass_contract.foliage_vertex_transform.has_value()) {
        return false;
    }
    const bool shadow_variant =
        pass_contract.foliage_vertex_transform->kind == VertexTransformKind::FoliageShadow;
    tgfx::VertexLayoutDesc vertex_layout;
    if (!build_foliage_vertex_layout(mesh_binding, shadow_variant, vertex_layout)) {
        return false;
    }

    std::vector<FoliageGpuInstance> instances;
    instances.reserve(data->instances.size());
    for (const FoliageInstance& instance : data->instances) {
        instances.push_back(make_gpu_instance(instance));
    }

    UploadedBuffer instance_buffer = upload_storage_buffer(
        ctx2,
        instances.data(),
        static_cast<uint32_t>(instances.size() * sizeof(FoliageGpuInstance)),
        static_cast<uint32_t>(sizeof(FoliageGpuInstance))
    );
    if (!instance_buffer.buffer) {
        return false;
    }

    TcShader shader = context.current_tc_shader;
    if (!shader.is_valid()) {
        shader = get_foliage_instanced_shader(TcShader(phase->shader), pass_contract);
    } else if (!shader_contract_requires_foliage_instances(shader)) {
        shader = get_foliage_instanced_shader(shader, pass_contract);
    }
    if (!shader.is_valid()) {
        // Shader assembly reports and caches the actionable failure.  This
        // encoder runs for every submitted foliage batch, so logging the
        // cached invalid result here would repeat the same diagnostic every
        // frame until the shader contract changes.
        return false;
    }
    MaterialPipelineShaderBinding shader_binding{};
    if (!ensure_material_pipeline_shader(
            ctx2,
            ctx2.device(),
            shader.handle,
            "FoliageLayerComponent",
            shader_binding)) {
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

    ctx2.clear_resource_bindings();
    ctx2.use_shader_resource_layout(shader_binding.shader);

    if (!bind_render_item_common_resources(ctx2, shader_binding.shader, request)) {
        tc::Log::error("[FoliageLayerComponent] failed to bind common RenderItem resources");
        return false;
    }

    ctx2.bind_uniform_data("foliage_draw", &push, sizeof(push));
    ctx2.bind_storage_buffer(
        "foliage_instances",
        instance_buffer.buffer,
        instance_buffer.offset,
        static_cast<uint32_t>(instances.size() * sizeof(FoliageGpuInstance)));
    ctx2.set_topology(mesh_binding.topology);
    ctx2.set_vertex_layout(vertex_layout);
    ctx2.draw_indexed_instanced(tgfx::RenderContext2::IndexedInstancedDraw{
        mesh_binding.vertex_buffer,
        0,
        mesh_binding.index_buffer,
        0,
        {},
        0,
        mesh_binding.index_count,
        static_cast<uint32_t>(instances.size())
    });
    return true;
}

} // namespace termin
