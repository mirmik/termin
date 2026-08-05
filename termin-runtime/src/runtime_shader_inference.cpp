#include "runtime_shader_inference.hpp"

#include <cctype>
#include <cstdint>
#include <cstdio>
#include <sstream>
#include <utility>
#include <vector>

#include <tcbase/tc_log.h>

namespace termin::runtime::detail
{
struct RuntimeMaterialUboEntry {
    std::string name;
    std::string property_type;
    uint32_t offset = 0;
    uint32_t size = 0;
};

struct RuntimeMaterialUboLayout {
    std::vector<RuntimeMaterialUboEntry> entries;
    uint32_t block_size = 0;

    bool empty() const {
        return entries.empty();
    }
};

std::string trim_copy(const std::string& s) {
    size_t begin = 0;
    while (begin < s.size() && std::isspace(static_cast<unsigned char>(s[begin]))) {
        ++begin;
    }
    size_t end = s.size();
    while (end > begin && std::isspace(static_cast<unsigned char>(s[end - 1]))) {
        --end;
    }
    return s.substr(begin, end - begin);
}

std::string glsl_material_property_type(const std::string& glsl_type) {
    if (glsl_type == "float") {
        return "Float";
    }
    if (glsl_type == "int") {
        return "Int";
    }
    if (glsl_type == "bool") {
        return "Bool";
    }
    if (glsl_type == "vec2") {
        return "Vec2";
    }
    if (glsl_type == "vec3") {
        return "Vec3";
    }
    if (glsl_type == "vec4") {
        return "Vec4";
    }
    if (glsl_type == "mat4") {
        return "Mat4";
    }
    return "";
}

std::pair<uint32_t, uint32_t> runtime_std140_size_align(const std::string& property_type) {
    if (property_type == "Float" || property_type == "Int" || property_type == "Bool") {
        return {4u, 4u};
    }
    if (property_type == "Vec2") {
        return {8u, 8u};
    }
    if (property_type == "Vec3") {
        return {12u, 16u};
    }
    if (property_type == "Vec4") {
        return {16u, 16u};
    }
    if (property_type == "Mat4") {
        return {64u, 16u};
    }
    return {0u, 0u};
}

uint32_t runtime_round_up(uint32_t value, uint32_t align) {
    if (align == 0) {
        return value;
    }
    return (value + align - 1u) & ~(align - 1u);
}

RuntimeMaterialUboLayout compute_runtime_std140_layout(
    const std::vector<RuntimeMaterialUboEntry>& declarations
) {
    RuntimeMaterialUboLayout layout;
    uint32_t cursor = 0;
    for (const RuntimeMaterialUboEntry& decl : declarations) {
        auto [size, align] = runtime_std140_size_align(decl.property_type);
        if (size == 0) {
            continue;
        }
        cursor = runtime_round_up(cursor, align);
        RuntimeMaterialUboEntry entry = decl;
        entry.offset = cursor;
        entry.size = size;
        layout.entries.push_back(std::move(entry));
        cursor += size;
    }
    layout.block_size = runtime_round_up(cursor, 16u);
    return layout;
}

RuntimeMaterialUboLayout infer_material_ubo_layout_from_glsl(const std::string& source) {
    RuntimeMaterialUboLayout empty;
    const size_t uniform_pos = source.find("uniform MaterialParams");
    if (uniform_pos == std::string::npos) {
        return empty;
    }
    const size_t block_begin = source.find('{', uniform_pos);
    if (block_begin == std::string::npos) {
        return empty;
    }
    const size_t block_end = source.find('}', block_begin + 1);
    if (block_end == std::string::npos || block_end <= block_begin) {
        return empty;
    }

    std::vector<RuntimeMaterialUboEntry> declarations;
    std::istringstream lines(source.substr(block_begin + 1, block_end - block_begin - 1));
    std::string line;
    while (std::getline(lines, line)) {
        const size_t comment = line.find("//");
        if (comment != std::string::npos) {
            line.resize(comment);
        }
        line = trim_copy(line);
        if (line.empty() || line.back() != ';') {
            continue;
        }
        line.pop_back();
        line = trim_copy(line);
        std::istringstream decl(line);
        std::string glsl_type;
        std::string name;
        decl >> glsl_type >> name;
        if (glsl_type.empty() || name.empty()) {
            continue;
        }
        const size_t array_pos = name.find('[');
        if (array_pos != std::string::npos) {
            name.resize(array_pos);
        }
        std::string property_type = glsl_material_property_type(glsl_type);
        if (property_type.empty()) {
            continue;
        }
        RuntimeMaterialUboEntry entry;
        entry.name = std::move(name);
        entry.property_type = std::move(property_type);
        declarations.push_back(std::move(entry));
    }

    return compute_runtime_std140_layout(declarations);
}

void set_shader_material_ubo_layout_from_glsl(
    tc_shader* shader,
    const std::string& fragment_source
) {
    if (!shader) {
        return;
    }
    RuntimeMaterialUboLayout layout = infer_material_ubo_layout_from_glsl(fragment_source);
    if (layout.empty()) {
        return;
    }

    std::vector<tc_material_ubo_entry> entries;
    entries.reserve(layout.entries.size());
    for (const RuntimeMaterialUboEntry& src : layout.entries) {
        tc_material_ubo_entry dst{};
        std::snprintf(dst.name, sizeof(dst.name), "%s", src.name.c_str());
        std::snprintf(
            dst.property_type,
            sizeof(dst.property_type),
            "%s",
            src.property_type.c_str()
        );
        dst.offset = src.offset;
        dst.size = src.size;
        entries.push_back(dst);
    }
    tc_shader_set_material_ubo_layout(
        shader,
        entries.data(),
        static_cast<uint32_t>(entries.size()),
        layout.block_size
    );
    tc_log_info(
        "RuntimePackageLoader: inferred material UBO layout for shader '%s' entries=%zu size=%u",
        shader->name ? shader->name : shader->uuid,
        entries.size(),
        layout.block_size
    );
}

void set_shader_features_from_glsl(tc_shader* shader, const std::string& fragment_source) {
    if (!shader) {
        return;
    }
    if (fragment_source.find("uniform LightingBlock") != std::string::npos) {
        tc_shader_set_feature(shader, TC_SHADER_FEATURE_LIGHTING_UBO);
        tc_log_info(
            "RuntimePackageLoader: inferred lighting UBO feature for shader '%s'",
            shader->name ? shader->name : shader->uuid
        );
    }
}
}
