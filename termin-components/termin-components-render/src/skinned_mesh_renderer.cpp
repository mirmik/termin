#include <termin/render/skinned_mesh_renderer.hpp>
#include <termin/render/skeleton_controller.hpp>
#include <termin/render/shader_skinning.hpp>
#include <termin/render/material_pipeline.hpp>
#include <termin/entity/entity.hpp>
#include <tgfx/tgfx_shader_handle.hpp>
#include <tgfx2/render_context.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/enums.hpp>
#include <tcbase/tc_log.hpp>
#include <algorithm>
#include <cstdint>
#include <cstring>
#include <string>
#include <unordered_map>
#include <vector>

extern "C" {
#include "tgfx/resources/tc_shader.h"
#include "tgfx/tgfx2_interop.h"
}

namespace termin {

// Must match TerminBoneBlock in termin-engine-skinned-common.slang.
// The descriptor set layout is built from shader reflection. std140 mat4[]
// is tightly packed (4 vec4 per matrix), the int after the array needs
// vec4 alignment. Total 128*64 + 16 = 8208.
static constexpr uint32_t BONE_BLOCK_MAX_BONES = 128;
static constexpr uint64_t BONE_BLOCK_SIZE =
    BONE_BLOCK_MAX_BONES * 16u * sizeof(float) + 16u;

// Hash for TcShader (uses handle.index)
struct TcShaderHash {
    size_t operator()(const TcShader& s) const {
        return std::hash<uint32_t>()(s.handle.index);
    }
};

struct TcShaderEqual {
    bool operator()(const TcShader& a, const TcShader& b) const {
        return a.handle.index == b.handle.index && a.handle.generation == b.handle.generation;
    }
};

struct SkinnedShaderCacheKey {
    TcShader shader;
    std::string intent_key;
};

struct SkinnedShaderCacheKeyHash {
    size_t operator()(const SkinnedShaderCacheKey& key) const {
        TcShaderHash shader_hash;
        return shader_hash(key.shader)
            ^ (std::hash<std::string>()(key.intent_key) << 1);
    }
};

struct SkinnedShaderCacheKeyEqual {
    bool operator()(const SkinnedShaderCacheKey& a, const SkinnedShaderCacheKey& b) const {
        TcShaderEqual shader_equal;
        return shader_equal(a.shader, b.shader)
            && a.intent_key == b.intent_key;
    }
};

// Static cache: (original shader, shader intent signature) -> skinned shader
static std::unordered_map<
    SkinnedShaderCacheKey,
    TcShader,
    SkinnedShaderCacheKeyHash,
SkinnedShaderCacheKeyEqual> s_skinned_shader_cache;

void SkinnedMeshRenderer::register_type() {
    MeshRenderer::register_type();
    register_component_type<SkinnedMeshRenderer>("SkinnedMeshRenderer", "MeshRenderer");
    register_component_requirement("SkinnedMeshRenderer", "MeshComponent");
}

static const tc_shader_resource_binding* find_bone_block_resource(const tc_shader* shader) {
    if (!shader) {
        return nullptr;
    }
    static constexpr const char* kNames[] = {
        TC_SHADER_RESOURCE_BONE_BLOCK,
        "BoneBlock",
    };
    for (const char* name : kNames) {
        const tc_shader_resource_binding* rb =
            tc_shader_find_resource_binding(shader, name);
        if (rb && rb->kind == TC_SHADER_RESOURCE_CONSTANT_BUFFER) {
            return rb;
        }
    }
    return nullptr;
}

static bool shader_contract_uses_skinning(const tc_shader* shader) {
    if (!shader) {
        return false;
    }
    tc_shader_contract_view contract{};
    if (!tc_shader_get_contract_view(shader, &contract)) {
        return false;
    }

    bool has_joints = false;
    bool has_weights = false;
    for (uint32_t i = 0; i < contract.vertex_input_count; ++i) {
        if (std::strncmp(
                contract.vertex_inputs[i].semantic,
                "joints",
                TC_SHADER_RESOURCE_NAME_MAX) == 0) {
            has_joints = true;
        }
        if (std::strncmp(
                contract.vertex_inputs[i].semantic,
                "weights",
                TC_SHADER_RESOURCE_NAME_MAX) == 0) {
            has_weights = true;
        }
    }
    return has_joints && has_weights;
}

static bool shader_uses_skinning(TcShader shader) {
    return shader_contract_uses_skinning(shader.get());
}

SkinnedMeshRenderer::SkinnedMeshRenderer()
    : MeshRenderer("SkinnedMeshRenderer")
{
}

SkinnedMeshRenderer::~SkinnedMeshRenderer() = default;

void SkinnedMeshRenderer::set_skeleton_controller(SkeletonController* controller) {
    _skeleton_controller.reset(controller);
}

void SkinnedMeshRenderer::resolve_skeleton_controller() {
    if (_skeleton_controller.valid() || !entity().valid()) {
        return;
    }

    Entity owner = entity();

    auto try_resolve_on_entity = [this](Entity candidate) -> bool {
        if (!candidate.valid()) {
            return false;
        }
        Component* controller = candidate.get_component_by_type("SkeletonController");
        if (controller != nullptr) {
            _skeleton_controller.reset(dynamic_cast<SkeletonController*>(controller));
            return _skeleton_controller.valid();
        }
        return false;
    };

    if (try_resolve_on_entity(owner)) {
        return;
    }

    // Scene copy/deserialization does not preserve transient CmpRef values.
    // Imported GLB meshes may be nested below Armature or intermediate nodes,
    // while the SkeletonController lives on the model root.
    Entity ancestor = owner.parent();
    while (ancestor.valid()) {
        if (try_resolve_on_entity(ancestor)) {
            return;
        }
        ancestor = ancestor.parent();
    }
}

SkeletonInstance* SkinnedMeshRenderer::skeleton_instance() {
    resolve_skeleton_controller();
    SkeletonController* ctrl = _skeleton_controller.get();
    if (!ctrl) {
        return nullptr;
    }
    return ctrl->skeleton_instance();
}

void SkinnedMeshRenderer::update_bone_matrices() {
    SkeletonInstance* si = skeleton_instance();
    if (si == nullptr) {
        _bone_count = 0;
        _bone_matrices_flat.clear();
        return;
    }

    // Skinning shader applies this renderer's u_model after bone matrices.
    // Compute bones in renderer-local space to avoid mixing Armature/root space
    // with per-mesh draw space.
    if (entity().valid()) {
        si->update(entity());
    } else {
        si->update();
    }

    // Get bone count
    _bone_count = si->bone_count();
    if (_bone_count == 0) {
        _bone_matrices_flat.clear();
        return;
    }

    // Resize buffer
    _bone_matrices_flat.resize(_bone_count * 16);

    // Copy matrices (column-major for OpenGL)
    for (int i = 0; i < _bone_count; ++i) {
        const Mat44& m = si->get_bone_matrix(i);
        // Mat44 is column-major, copy directly
        for (int j = 0; j < 16; ++j) {
            _bone_matrices_flat[i * 16 + j] = static_cast<float>(m.data[j]);
        }
    }
}

void SkinnedMeshRenderer::upload_per_draw_uniforms_tgfx2(
    tgfx::RenderContext2& ctx2,
    int geometry_id
) {
    (void)geometry_id;
    resolve_skeleton_controller();
    if (!_skeleton_controller.valid()) return;

    update_bone_matrices();
    if (_bone_count <= 0 || _bone_matrices_flat.empty()) return;

    // Pack std140 BoneBlock: [mat4 u_bone_matrices[128]; int u_bone_count;].
    // Matrices fill the first MAX_BONES*64 bytes; unused slots stay zeroed.
    // The trailing int sits at offset MAX_BONES*64 (vec4-aligned by std140).
    std::vector<uint8_t> staging(BONE_BLOCK_SIZE, 0);
    const uint32_t used_bones =
        std::min<uint32_t>(static_cast<uint32_t>(_bone_count), BONE_BLOCK_MAX_BONES);
    std::memcpy(staging.data(),
                _bone_matrices_flat.data(),
                used_bones * 16u * sizeof(float));
    int32_t count = static_cast<int32_t>(used_bones);
    std::memcpy(staging.data() + BONE_BLOCK_MAX_BONES * 16u * sizeof(float),
                &count, sizeof(int32_t));

    // Route BoneBlock through shader metadata. Layout-only shaders must
    // declare the draw-scope bone block explicitly.
    const tc_shader* active_shader = ctx2.active_shader_resource_layout();
    if (const tc_shader_resource_binding* rb = find_bone_block_resource(active_shader)) {
        ctx2.bind_uniform_data(rb, staging.data(), static_cast<uint32_t>(staging.size()));
        return;
    }

    tc::Log::error(
        "[SkinnedMeshRenderer] shader '%s' has no '%s' resource; fixed binding "
        "fallback has been removed",
        active_shader && active_shader->name ? active_shader->name : "<unnamed>",
        TC_SHADER_RESOURCE_BONE_BLOCK);
}

TcShader SkinnedMeshRenderer::override_shader(
    const std::string& phase_mark,
    int geometry_id,
    TcShader original_shader
) {
    ShaderOverrideContext context;
    context.phase_mark = phase_mark;
    context.geometry_id = geometry_id;
    context.original_shader = original_shader;
    context.pass_contract = legacy_full_material_pass_contract();
    return override_shader_with_context(context);
}

TcShader SkinnedMeshRenderer::override_shader_with_context(
    const ShaderOverrideContext& context
) {
    const std::string& phase_mark = context.phase_mark;
    const int geometry_id = context.geometry_id;
    TcShader original_shader = context.original_shader;

    resolve_skeleton_controller();
    if (!_skeleton_controller.valid() || !original_shader.is_valid()) {
        return original_shader;
    }
    if (shader_uses_skinning(original_shader)) {
        return original_shader;
    }

    // Check if shader already has skinning
    const char* vert_source = original_shader.vertex_source();
    if (vert_source && std::strstr(vert_source, "u_bone_matrices") != nullptr) {
        return original_shader;
    }

    // Check C++ cache first
    const tc_shader_variant_op variant_op = TC_SHADER_VARIANT_SKINNING;
    const std::string intent_key =
        context.pass_contract.skinned_vertex_transform.has_value()
            ? material_pipeline_shader_intent_fingerprint(
                original_shader,
                variant_op,
                *context.pass_contract.skinned_vertex_transform,
                context.pass_contract)
            : context.pass_contract.debug_name;
    SkinnedShaderCacheKey cache_key{original_shader, intent_key};
    auto it = s_skinned_shader_cache.find(cache_key);
    if (it != s_skinned_shader_cache.end()) {
        TcShader& cached = it->second;
        // Check if variant is stale (original shader was modified)
        if (!cached.variant_is_stale()) {
            return cached;
        }
        // Stale - need to recreate
        s_skinned_shader_cache.erase(it);
    }

    // Use C++ skinning injection
    TcShader skinned = get_skinned_shader_for_pass(
        context.pass_contract,
        original_shader);
    if (skinned.is_valid()) {
        s_skinned_shader_cache[cache_key] = skinned;
        return skinned;
    }

    return original_shader;
}

void SkinnedMeshRenderer::collect_shader_usages(
    const std::string& phase_mark,
    int geometry_id,
    TcShader original_shader,
    const std::function<void(TcShader)>& emit
) {
    ShaderOverrideContext context;
    context.phase_mark = phase_mark;
    context.geometry_id = geometry_id;
    context.original_shader = original_shader;
    context.pass_contract = legacy_full_material_pass_contract();
    collect_shader_usages_with_context(context, emit);
}

void SkinnedMeshRenderer::populate_mesh_render_item(tc_render_item& item) {
    update_bone_matrices();
    if (_bone_count <= 0 || _bone_matrices_flat.empty()) {
        return;
    }

    item.flags |= TC_RENDER_ITEM_FLAG_HAS_SKINNING_MATRICES;
    item.payload.mesh.skinning_matrices = _bone_matrices_flat.data();
    item.payload.mesh.skinning_matrix_count = static_cast<uint32_t>(_bone_count);
}

void SkinnedMeshRenderer::start() {
    Component::start();
    resolve_skeleton_controller();
}

} // namespace termin
