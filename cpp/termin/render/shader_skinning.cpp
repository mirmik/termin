// shader_skinning.cpp - Shader skinning injection implementation

#include "shader_skinning.hpp"
#include "tc_log.hpp"
#include <regex>
#include <sstream>
#include <vector>

namespace termin {

// Skinning inputs to inject after existing layout declarations
static const char* SKINNING_INPUTS = R"(
// === Skinning inputs (injected) ===
layout(location = 3) in vec4 a_joints;
layout(location = 4) in vec4 a_weights;

const int MAX_BONES = 128;
uniform mat4 u_bone_matrices[MAX_BONES];
uniform int u_bone_count;
)";

// Skinning function - full version with normals
static const char* SKINNING_FUNCTION = R"(
// === Skinning function (injected) ===
void _applySkinning(inout vec3 position, inout vec3 normal) {
    if (u_bone_count <= 0) return;

    vec4 skinned_pos = vec4(0.0);
    vec3 skinned_norm = vec3(0.0);
    float total_weight = 0.0;

    for (int i = 0; i < 4; ++i) {
        int idx = int(a_joints[i]);
        float w = a_weights[i];
        if (w > 0.0 && idx < u_bone_count) {
            mat4 bone = u_bone_matrices[idx];
            skinned_pos += w * (bone * vec4(position, 1.0));
            skinned_norm += w * (mat3(bone) * normal);
            total_weight += w;
        }
    }

    if (total_weight > 0.0) {
        position = skinned_pos.xyz;
        normal = skinned_norm;
    }
}
)";

// Skinning function - position only (for shaders without normals)
static const char* SKINNING_FUNCTION_POS_ONLY = R"(
// === Skinning function (injected, position only) ===
void _applySkinning(inout vec3 position) {
    if (u_bone_count <= 0) return;

    vec4 skinned_pos = vec4(0.0);
    float total_weight = 0.0;

    for (int i = 0; i < 4; ++i) {
        int idx = int(a_joints[i]);
        float w = a_weights[i];
        if (w > 0.0 && idx < u_bone_count) {
            mat4 bone = u_bone_matrices[idx];
            skinned_pos += w * (bone * vec4(position, 1.0));
            total_weight += w;
        }
    }

    if (total_weight > 0.0) {
        position = skinned_pos.xyz;
    }
}
)";

// Call to add at the beginning of main() - full version
static const char* SKINNING_CALL = R"(    // === Apply skinning (injected) ===
    vec3 _skinned_position = a_position;
    vec3 _skinned_normal = a_normal;
    _applySkinning(_skinned_position, _skinned_normal);
)";

// Call - position only version
static const char* SKINNING_CALL_POS_ONLY = R"(    // === Apply skinning (injected, position only) ===
    vec3 _skinned_position = a_position;
    _applySkinning(_skinned_position);
)";

// Split string by newlines
static std::vector<std::string> split_lines(const std::string& s) {
    std::vector<std::string> lines;
    std::istringstream iss(s);
    std::string line;
    while (std::getline(iss, line)) {
        lines.push_back(line);
    }
    return lines;
}

// Join lines with newlines
static std::string join_lines(const std::vector<std::string>& lines) {
    std::ostringstream oss;
    for (size_t i = 0; i < lines.size(); ++i) {
        if (i > 0) oss << '\n';
        oss << lines[i];
    }
    return oss.str();
}

// Find line number after last layout(...) declaration
static int find_last_layout_line(const std::vector<std::string>& lines) {
    int last_layout = -1;
    std::regex layout_re(R"(\s*layout\s*\()");
    for (size_t i = 0; i < lines.size(); ++i) {
        if (std::regex_search(lines[i], layout_re)) {
            last_layout = static_cast<int>(i);
        }
    }
    return last_layout;
}

// Find void main() function - returns (main_decl_line, opening_brace_line)
static std::pair<int, int> find_main_function(const std::vector<std::string>& lines) {
    std::regex main_re(R"(\s*void\s+main\s*\(\s*\))");
    for (size_t i = 0; i < lines.size(); ++i) {
        if (std::regex_search(lines[i], main_re)) {
            if (lines[i].find('{') != std::string::npos) {
                return {static_cast<int>(i), static_cast<int>(i)};
            } else if (i + 1 < lines.size() && lines[i + 1].find('{') != std::string::npos) {
                return {static_cast<int>(i), static_cast<int>(i + 1)};
            }
        }
    }
    return {-1, -1};
}

std::string inject_skinning_into_vertex_shader(const std::string& vertex_source) {
    // Check if already has skinning
    if (vertex_source.find("u_bone_matrices") != std::string::npos) {
        return vertex_source;
    }

    std::vector<std::string> lines = split_lines(vertex_source);

    // Check if shader has a_normal
    bool has_normal = vertex_source.find("a_normal") != std::string::npos;

    // Find insertion points
    int last_layout = find_last_layout_line(lines);
    auto [main_decl, main_brace] = find_main_function(lines);

    if (main_decl < 0) {
        tc::Log::error("[inject_skinning] Could not find void main() in vertex shader");
        return vertex_source;
    }

    // Determine where to insert inputs
    int insert_inputs_at;
    if (last_layout >= 0) {
        insert_inputs_at = last_layout + 1;
    } else {
        // Find #version line
        insert_inputs_at = 0;
        for (size_t i = 0; i < lines.size(); ++i) {
            if (lines[i].find("#version") != std::string::npos) {
                insert_inputs_at = static_cast<int>(i) + 1;
                break;
            }
        }
    }

    // Choose skinning code based on whether shader uses normals
    const char* skinning_func = has_normal ? SKINNING_FUNCTION : SKINNING_FUNCTION_POS_ONLY;
    const char* skinning_call = has_normal ? SKINNING_CALL : SKINNING_CALL_POS_ONLY;

    std::vector<std::string> input_lines = split_lines(SKINNING_INPUTS);
    std::vector<std::string> func_lines = split_lines(skinning_func);
    std::vector<std::string> call_lines = split_lines(skinning_call);

    // Build new source
    std::vector<std::string> new_lines;

    for (size_t i = 0; i < lines.size(); ++i) {
        // Add inputs after last layout
        if (static_cast<int>(i) == insert_inputs_at) {
            new_lines.insert(new_lines.end(), input_lines.begin(), input_lines.end());
            new_lines.push_back("");
        }

        // Add function before main
        if (static_cast<int>(i) == main_decl) {
            new_lines.push_back("");
            new_lines.insert(new_lines.end(), func_lines.begin(), func_lines.end());
            new_lines.push_back("");
        }

        new_lines.push_back(lines[i]);

        // Add call after opening brace
        if (static_cast<int>(i) == main_brace) {
            new_lines.insert(new_lines.end(), call_lines.begin(), call_lines.end());
        }
    }

    std::string result = join_lines(new_lines);

    // Replace a_position and a_normal with skinned versions in main() body
    auto [new_main_decl, new_main_brace] = find_main_function(split_lines(result));
    if (new_main_brace < 0) {
        return result;
    }

    new_lines = split_lines(result);

    // Find closing brace of main
    int brace_count = 0;
    int main_end = static_cast<int>(new_lines.size());
    for (size_t i = new_main_brace; i < new_lines.size(); ++i) {
        for (char c : new_lines[i]) {
            if (c == '{') brace_count++;
            else if (c == '}') brace_count--;
        }
        if (brace_count == 0 && static_cast<int>(i) > new_main_brace) {
            main_end = static_cast<int>(i);
            break;
        }
    }

    // Replace only within main() body, skip skinning call lines
    int skinning_call_end = new_main_brace + static_cast<int>(call_lines.size()) + 1;

    std::regex pos_re(R"(\ba_position\b)");
    std::regex norm_re(R"(\ba_normal\b)");

    for (int i = skinning_call_end; i <= main_end && i < static_cast<int>(new_lines.size()); ++i) {
        new_lines[i] = std::regex_replace(new_lines[i], pos_re, "_skinned_position");
        new_lines[i] = std::regex_replace(new_lines[i], norm_re, "_skinned_normal");
    }

    return join_lines(new_lines);
}

TcShader get_skinned_shader(TcShader original_shader) {
    if (!original_shader.is_valid()) {
        return TcShader();
    }

    // Check if already has skinning
    const char* vert_src = original_shader.vertex_source();
    if (vert_src && std::strstr(vert_src, "u_bone_matrices") != nullptr) {
        return original_shader;
    }

    // Get sources
    std::string vertex_source = vert_src ? vert_src : "";
    const char* frag_src = original_shader.fragment_source();
    std::string fragment_source = frag_src ? frag_src : "";
    const char* geom_src = original_shader.geometry_source();
    std::string geometry_source = geom_src ? geom_src : "";

    if (vertex_source.empty()) {
        tc::Log::error("[get_skinned_shader] Original shader has no vertex source");
        return TcShader();
    }

    // Inject skinning
    std::string skinned_vertex = inject_skinning_into_vertex_shader(vertex_source);

    // Create skinned variant
    std::string orig_name = original_shader.name();
    std::string skinned_name = orig_name.empty()
        ? std::string("Skinned_") + original_shader.uuid()
        : orig_name + "_Skinned";

    tc_shader_handle h = tc_shader_from_sources(
        skinned_vertex.c_str(),
        fragment_source.c_str(),
        geometry_source.empty() ? nullptr : geometry_source.c_str(),
        skinned_name.c_str(),
        original_shader.source_path(),
        nullptr  // auto-generate uuid
    );

    if (tc_shader_handle_is_invalid(h)) {
        tc::Log::error("[get_skinned_shader] Failed to create skinned shader for '%s'", orig_name.c_str());
        return TcShader();
    }

    TcShader skinned(h);

    // Copy features from original
    skinned.set_features(original_shader.features());

    // Mark as variant
    skinned.set_variant_info(original_shader, TC_SHADER_VARIANT_SKINNING);

    return skinned;
}

} // namespace termin
