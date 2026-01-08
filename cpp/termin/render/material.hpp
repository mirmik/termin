#pragma once

#include <string>
#include <vector>
#include <unordered_map>
#include <memory>
#include <variant>
#include <optional>

#include "termin/render/shader_program.hpp"
#include "termin/render/render_state.hpp"
#include "termin/render/handles.hpp"
#include "termin/assets/handles.hpp"
#include "termin/geom/mat44.hpp"
#include "termin/geom/vec3.hpp"
#include "termin/geom/vec4.hpp"

namespace termin {

// Forward declarations
class GraphicsBackend;

/**
 * Uniform value types supported by materials.
 */
using MaterialUniformValue = std::variant<
    bool,
    int,
    float,
    Vec3,
    Vec4,
    Mat44f,
    std::vector<float>  // For arrays
>;

/**
 * Material phase: shader + render state + uniforms for one render pass.
 *
 * A material can have multiple phases for different render passes:
 * - "opaque" for main color pass
 * - "shadow" for shadow map pass
 * - "transparent" for alpha-blended objects
 */
// Forward declaration
struct PhaseRenderSettings;

class MaterialPhase {
public:
    // Shader program for this phase (shared - compiled once, used by many phases)
    std::shared_ptr<ShaderProgram> shader;

    // Render state (depth, blend, cull, etc.)
    RenderState render_state;

    // Phase identifier ("opaque", "shadow", "transparent", etc.)
    std::string phase_mark = "opaque";

    // Available marks for user choice (if >1, user can select in inspector)
    std::vector<std::string> available_marks;

    // Per-mark render settings (for switching between marks)
    std::unordered_map<std::string, RenderState> mark_render_states;

    // Priority within phase (lower = rendered earlier)
    int priority = 0;

    // Texture bindings: uniform_name -> texture handle (asset-based)
    std::unordered_map<std::string, TextureHandle> textures;

    // Uniform values: name -> value
    std::unordered_map<std::string, MaterialUniformValue> uniforms;

    MaterialPhase() = default;

    MaterialPhase(
        std::shared_ptr<ShaderProgram> shader_,
        RenderState render_state_ = RenderState::opaque(),
        std::string phase_mark_ = "opaque",
        int priority_ = 0
    ) : shader(std::move(shader_)),
        render_state(std::move(render_state_)),
        phase_mark(std::move(phase_mark_)),
        priority(priority_) {}

    /**
     * Set a uniform parameter.
     */
    void set_param(const std::string& name, const MaterialUniformValue& value) {
        uniforms[name] = value;
    }

    /**
     * Get color from u_color uniform.
     */
    std::optional<Vec4> color() const {
        auto it = uniforms.find("u_color");
        if (it != uniforms.end()) {
            if (auto* v = std::get_if<Vec4>(&it->second)) {
                return *v;
            }
        }
        return std::nullopt;
    }

    /**
     * Set color (u_color uniform).
     */
    void set_color(const Vec4& rgba) {
        uniforms["u_color"] = rgba;
    }

    /**
     * Apply this material phase to graphics backend.
     *
     * Uploads MVP matrices, binds textures, and sets all uniforms.
     *
     * @param model Model matrix
     * @param view View matrix
     * @param projection Projection matrix
     * @param graphics Graphics backend
     * @param context_key Context key for caching
     */
    void apply(
        const Mat44f& model,
        const Mat44f& view,
        const Mat44f& projection,
        GraphicsBackend* graphics,
        int64_t context_key = 0
    );

    /**
     * Apply uniforms to a specific shader (for shader override scenarios).
     *
     * Like apply(), but uses the provided shader instead of this->shader.
     * Used when drawable overrides shader (e.g., for skinning injection).
     *
     * @param target_shader Shader to upload uniforms to
     * @param model Model matrix
     * @param view View matrix
     * @param projection Projection matrix
     * @param graphics Graphics backend
     * @param context_key Context key for caching
     */
    void apply_to_shader(
        ShaderProgram* target_shader,
        const Mat44f& model,
        const Mat44f& view,
        const Mat44f& projection,
        GraphicsBackend* graphics,
        int64_t context_key = 0
    );

    /**
     * Apply render state to graphics backend.
     */
    void apply_state(GraphicsBackend* graphics);

    /**
     * Create a copy of this phase.
     * Shader is shared, uniforms are deep-copied.
     */
    MaterialPhase copy() const;
};

/**
 * Material: collection of phases for rendering an object.
 *
 * Each phase corresponds to a different render pass (color, shadow, etc.).
 * Materials can be created from parsed shader files or constructed manually.
 */
class Material {
public:
    // Material name (for debugging and serialization)
    std::string name;

    // Source path (if loaded from file)
    std::string source_path;

    // Shader name (for editor display)
    std::string shader_name = "DefaultShader";

    // Active phase mark (empty = use all phases, non-empty = use only this phase)
    // Used when shader has multiple phases (e.g., opaque, transparent) and user
    // wants to force a specific rendering mode.
    std::string active_phase_mark;

    // All phases of this material
    std::vector<MaterialPhase> phases;

    Material() = default;

    /**
     * Create material with a single phase.
     */
    Material(
        std::shared_ptr<ShaderProgram> shader,
        RenderState render_state = RenderState::opaque(),
        std::string phase_mark = "opaque",
        int priority = 0
    ) {
        phases.emplace_back(std::move(shader), std::move(render_state), std::move(phase_mark), priority);
    }

    /**
     * Get the default (first) phase.
     */
    MaterialPhase& default_phase() {
        return phases[0];
    }

    const MaterialPhase& default_phase() const {
        return phases[0];
    }

    /**
     * Get all phases matching a phase mark, sorted by priority.
     */
    std::vector<MaterialPhase*> get_phases_for_mark(const std::string& mark);

    /**
     * Set a uniform on all phases.
     */
    void set_param(const std::string& name, const MaterialUniformValue& value) {
        for (auto& phase : phases) {
            phase.set_param(name, value);
        }
    }

    /**
     * Get color from default phase.
     */
    Vec4 color() const {
        if (phases.empty()) {
            return Vec4{0, 0, 0, 1};
        }
        auto c = phases[0].color();
        return c.value_or(Vec4{0, 0, 0, 1});
    }

    /**
     * Set color on all phases.
     */
    void set_color(const Vec4& rgba) {
        for (auto& phase : phases) {
            phase.set_color(rgba);
        }
    }

    /**
     * Apply default phase.
     */
    void apply(
        const Mat44f& model,
        const Mat44f& view,
        const Mat44f& projection,
        GraphicsBackend* graphics,
        int64_t context_key = 0
    ) {
        if (!phases.empty()) {
            phases[0].apply(model, view, projection, graphics, context_key);
        }
    }

    /**
     * Create a copy of this material.
     */
    Material copy() const;
};

using MaterialPtr = std::shared_ptr<Material>;

} // namespace termin
