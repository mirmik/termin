#include "skinned_mesh_renderer.hpp"
#include <termin/render/skeleton_controller.hpp>
#include "shader_skinning.hpp"
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
#include <unordered_map>
#include <vector>

extern "C" {
#include "tgfx/tgfx2_interop.h"
}

namespace termin {

// Must match `layout(std140, binding = 12) uniform BoneBlock` in
// shader_skinning.cpp SKINNING_INPUTS. std140: mat4[] is tightly packed
// as 4 vec4 per matrix (no padding between), the int after the array
// needs vec4 alignment → 16-byte stride. Total 128*64 + 16 = 8208.
static constexpr uint32_t BONE_BLOCK_MAX_BONES = 128;
static constexpr uint64_t BONE_BLOCK_SIZE =
    BONE_BLOCK_MAX_BONES * 16u * sizeof(float) + 16u;
static constexpr uint32_t BONE_BLOCK_BINDING = 12;

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

// Static cache: original shader -> skinned shader
static std::unordered_map<TcShader, TcShader, TcShaderHash, TcShaderEqual> s_skinned_shader_cache;

SkinnedMeshRenderer::SkinnedMeshRenderer()
    : MeshRenderer()
{
    // type_entry is set by registry when component is created via factory
}

SkinnedMeshRenderer::~SkinnedMeshRenderer() {
    // Skip destroy if the cached device is no longer live — Python
    // interpreter shutdown tears down the BackendWindow (and its
    // IRenderDevice) before components are destructed. Borrow-mode
    // shutdown safety pattern: only talk to the device if it still
    // matches tgfx2_interop_get_device().
    if (_bone_ubo.id != 0 && _bone_ubo_device) {
        void* live = tgfx2_interop_get_device();
        if (live == _bone_ubo_device) {
            _bone_ubo_device->destroy(_bone_ubo);
        }
    }
    _bone_ubo = tgfx::BufferHandle{};
    _bone_ubo_device = nullptr;
}

void SkinnedMeshRenderer::set_skeleton_controller(SkeletonController* controller) {
    _skeleton_controller.reset(controller);
}

SkeletonInstance* SkinnedMeshRenderer::skeleton_instance() {
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

    // Get bone count (skeleton was already updated in SkeletonController::before_render)
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
    if (!_skeleton_controller.valid()) return;

    update_bone_matrices();
    if (_bone_count <= 0 || _bone_matrices_flat.empty()) return;

    tgfx::IRenderDevice& device = ctx2.device();

    // Lazy-create (or re-create if the device changed) the per-instance
    // BoneBlock UBO. One buffer per SkinnedMeshRenderer is needed because
    // Vulkan's deferred command buffer reads the UBO at submit time — a
    // shared buffer would see the last caller's data for every skinned
    // draw in the frame (vulkan_ubo_reuse_pitfall).
    if (_bone_ubo.id == 0 || _bone_ubo_device != &device) {
        if (_bone_ubo.id != 0 && _bone_ubo_device) {
            _bone_ubo_device->destroy(_bone_ubo);
        }
        tgfx::BufferDesc desc;
        desc.size = BONE_BLOCK_SIZE;
        desc.usage = tgfx::BufferUsage::Uniform | tgfx::BufferUsage::CopyDst;
        _bone_ubo = device.create_buffer(desc);
        _bone_ubo_device = &device;
    }

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

    device.upload_buffer(_bone_ubo,
                         std::span<const uint8_t>(staging.data(), staging.size()),
                         0);

    ctx2.bind_uniform_buffer(BONE_BLOCK_BINDING, _bone_ubo);
    // Redundant on Vulkan (binding is baked into the SPIR-V) but needed on
    // GL when the driver doesn't honour explicit `layout(binding=N)` on
    // the UBO block — glUniformBlockBinding makes the lookup match.
    ctx2.set_block_binding("BoneBlock", BONE_BLOCK_BINDING);
}

TcShader SkinnedMeshRenderer::override_shader(
    const std::string& phase_mark,
    int geometry_id,
    TcShader original_shader
) {
    if (!_skeleton_controller.valid() || !original_shader.is_valid()) {
        return original_shader;
    }

    // Check if shader already has skinning
    const char* vert_source = original_shader.vertex_source();
    if (vert_source && std::strstr(vert_source, "u_bone_matrices") != nullptr) {
        return original_shader;
    }

    // Check C++ cache first
    auto it = s_skinned_shader_cache.find(original_shader);
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
    TcShader skinned = get_skinned_shader(original_shader);
    if (skinned.is_valid()) {
        s_skinned_shader_cache[original_shader] = skinned;
        return skinned;
    }

    return original_shader;
}

std::vector<GeometryDrawCall> SkinnedMeshRenderer::get_geometry_draws(const std::string* phase_mark) {
    // Use parent implementation - shader override happens in override_shader()
    return MeshRenderer::get_geometry_draws(phase_mark);
}

void SkinnedMeshRenderer::start() {
    Component::start();

    // After deserialization, skeleton_controller may be null - try to find it
    if (!_skeleton_controller.valid() && entity().valid()) {
        // Look for SkeletonController by type name
        // Check parent entity first (typical for GLB structure)
        Entity parent_entity = entity().parent();

        if (parent_entity.valid()) {
            Component* controller = parent_entity.get_component_by_type("SkeletonController");
            if (controller != nullptr) {
                _skeleton_controller.reset(dynamic_cast<SkeletonController*>(controller));
            }
        }

        // Also check current entity
        if (!_skeleton_controller.valid()) {
            Component* controller = entity().get_component_by_type("SkeletonController");
            if (controller != nullptr) {
                _skeleton_controller.reset(dynamic_cast<SkeletonController*>(controller));
            }
        }
    }
}

} // namespace termin
