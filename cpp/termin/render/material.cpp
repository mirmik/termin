#include "material.hpp"
#include "graphics_backend.hpp"

#include <algorithm>

namespace termin {

void MaterialPhase::apply(
    const Mat44f& model,
    const Mat44f& view,
    const Mat44f& projection,
    GraphicsBackend* graphics,
    int64_t context_key
) {
    if (!shader) return;

    // Ensure shader is compiled
    shader->ensure_ready([graphics](const char* v, const char* f, const char* g) {
        return graphics->create_shader(v, f, g);
    });

    // Use shader
    shader->use();

    // Upload MVP matrices
    shader->set_uniform_matrix4("u_model", model);
    shader->set_uniform_matrix4("u_view", view);
    shader->set_uniform_matrix4("u_projection", projection);

    // Bind textures
    // Note: TextureGPU::bind() requires graphics backend and texture data,
    // which we don't have here. For now, skip texture binding in C++ Material.
    // Python Material handles texture binding correctly.
    // TODO: Pass TextureData through MaterialPhase for proper binding

    // Upload uniforms
    for (const auto& [name, value] : uniforms) {
        std::visit([this, &name](auto&& val) {
            using T = std::decay_t<decltype(val)>;

            if constexpr (std::is_same_v<T, bool>) {
                shader->set_uniform_int(name.c_str(), val ? 1 : 0);
            } else if constexpr (std::is_same_v<T, int>) {
                shader->set_uniform_int(name.c_str(), val);
            } else if constexpr (std::is_same_v<T, float>) {
                shader->set_uniform_float(name.c_str(), val);
            } else if constexpr (std::is_same_v<T, Vec3>) {
                shader->set_uniform_vec3(name.c_str(), val);
            } else if constexpr (std::is_same_v<T, Vec4>) {
                shader->set_uniform_vec4(name.c_str(),
                    static_cast<float>(val.x),
                    static_cast<float>(val.y),
                    static_cast<float>(val.z),
                    static_cast<float>(val.w));
            } else if constexpr (std::is_same_v<T, Mat44f>) {
                shader->set_uniform_matrix4(name.c_str(), val);
            } else if constexpr (std::is_same_v<T, std::vector<float>>) {
                // Arrays - handled based on size
                if (val.size() == 2) {
                    shader->set_uniform_vec2(name.c_str(), val[0], val[1]);
                } else if (val.size() == 3) {
                    shader->set_uniform_vec3(name.c_str(), val[0], val[1], val[2]);
                } else if (val.size() == 4) {
                    shader->set_uniform_vec4(name.c_str(), val[0], val[1], val[2], val[3]);
                }
            }
        }, value);
    }
}

void MaterialPhase::apply_state(GraphicsBackend* graphics) {
    graphics->apply_render_state(render_state);
}

MaterialPhase MaterialPhase::copy() const {
    MaterialPhase result;
    result.shader = shader;  // Shader is shared (compiled once)
    result.render_state = render_state;
    result.phase_mark = phase_mark;
    result.priority = priority;
    result.color = color;
    result.textures = textures;  // Texture handles are shared
    result.uniforms = uniforms;  // Deep copy of variant map
    return result;
}

std::vector<MaterialPhase*> Material::get_phases_for_mark(const std::string& mark) {
    std::vector<MaterialPhase*> result;
    for (auto& phase : phases) {
        if (phase.phase_mark == mark) {
            result.push_back(&phase);
        }
    }

    // Sort by priority
    std::sort(result.begin(), result.end(), [](MaterialPhase* a, MaterialPhase* b) {
        return a->priority < b->priority;
    });

    return result;
}

Material Material::copy() const {
    Material result;
    result.name = name + "_copy";
    result.source_path.clear();  // Copy is not linked to file
    result.shader_name = shader_name;

    result.phases.reserve(phases.size());
    for (const auto& phase : phases) {
        result.phases.push_back(phase.copy());
    }

    return result;
}

} // namespace termin
