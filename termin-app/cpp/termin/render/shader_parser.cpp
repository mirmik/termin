#include "shader_parser.hpp"

#include <sstream>
#include <algorithm>
#include <cctype>
#include <cstring>
#include <regex>

namespace termin {

namespace {

// Trim whitespace from both ends
std::string trim(const std::string& s) {
    size_t start = s.find_first_not_of(" \t\r\n");
    if (start == std::string::npos) return "";
    size_t end = s.find_last_not_of(" \t\r\n");
    return s.substr(start, end - start + 1);
}

// Convert to lowercase
std::string to_lower(const std::string& s) {
    std::string result = s;
    std::transform(result.begin(), result.end(), result.begin(),
                   [](unsigned char c) { return std::tolower(c); });
    return result;
}

// Check if string starts with prefix
bool starts_with(const std::string& s, const std::string& prefix) {
    return s.size() >= prefix.size() &&
           s.compare(0, prefix.size(), prefix) == 0;
}

// Split string by whitespace
std::vector<std::string> split_whitespace(const std::string& s) {
    std::vector<std::string> result;
    std::istringstream iss(s);
    std::string word;
    while (iss >> word) {
        result.push_back(word);
    }
    return result;
}

// Parse property value from string
MaterialProperty::DefaultValue parse_property_value(
    const std::string& value_str,
    const std::string& property_type
) {
    std::string val = trim(value_str);

    if (property_type == "Float") {
        return std::stod(val);
    }
    else if (property_type == "Int") {
        return std::stoi(val);
    }
    else if (property_type == "Bool") {
        return parse_bool(val);
    }
    else if (property_type == "Vec2" || property_type == "Vec3" ||
             property_type == "Vec4" || property_type == "Color") {
        // Parse: Color(1.0, 0.5, 0.0, 1.0) or Vec3(1, 2, 3) or [1.0, 0.5, 0.0, 1.0] or "1.0 0.5 0.0"
        std::vector<double> values;

        // Try constructor format: Type(...)
        std::regex ctor_regex(R"(\w+\s*\(\s*([^)]+)\s*\))");
        std::smatch match;
        std::string inner;

        if (std::regex_search(val, match, ctor_regex)) {
            inner = match[1].str();
        } else {
            inner = val;
        }

        // Parse comma or space separated values, ignoring brackets
        std::string num;
        for (char c : inner) {
            if (c == ',' || c == ' ' || c == '\t' || c == '[' || c == ']') {
                if (!num.empty()) {
                    values.push_back(std::stod(trim(num)));
                    num.clear();
                }
            } else {
                num += c;
            }
        }
        if (!num.empty()) {
            values.push_back(std::stod(trim(num)));
        }

        // Ensure correct size
        size_t expected = 0;
        if (property_type == "Vec2") expected = 2;
        else if (property_type == "Vec3") expected = 3;
        else expected = 4;  // Vec4 or Color

        while (values.size() < expected) {
            values.push_back(property_type == "Color" ? 1.0 : 0.0);
        }

        return values;
    }
    else if (property_type == "Texture") {
        // Remove quotes if present
        if (val.size() >= 2 &&
            ((val.front() == '"' && val.back() == '"') ||
             (val.front() == '\'' && val.back() == '\''))) {
            return val.substr(1, val.size() - 2);
        }
        return val.empty() ? MaterialProperty::DefaultValue{std::monostate{}} :
                             MaterialProperty::DefaultValue{val};
    }

    throw std::runtime_error("Unknown property type: " + property_type);
}

// Get default value for property type
MaterialProperty::DefaultValue get_default_for_type(const std::string& type) {
    if (type == "Float") return 0.0;
    if (type == "Int") return 0;
    if (type == "Bool") return false;
    if (type == "Vec2") return std::vector<double>{0.0, 0.0};
    if (type == "Vec3") return std::vector<double>{0.0, 0.0, 0.0};
    if (type == "Vec4") return std::vector<double>{0.0, 0.0, 0.0, 0.0};
    if (type == "Color") return std::vector<double>{1.0, 1.0, 1.0, 1.0};
    if (type == "Mat4") {
        // 4x4 identity, column-major like Mat44f storage.
        return std::vector<double>{
            1.0, 0.0, 0.0, 0.0,
            0.0, 1.0, 0.0, 0.0,
            0.0, 0.0, 1.0, 0.0,
            0.0, 0.0, 0.0, 1.0,
        };
    }
    if (type == "Texture") return std::monostate{};
    throw std::runtime_error("Unknown property type: " + type);
}

} // anonymous namespace


bool parse_bool(const std::string& value) {
    std::string low = to_lower(trim(value));
    if (low == "true" || low == "1" || low == "yes" || low == "on") {
        return true;
    }
    if (low == "false" || low == "0" || low == "no" || low == "off") {
        return false;
    }
    throw std::runtime_error("Cannot parse as bool: " + value);
}


// ========== std140 Material UBO generator ==========

std::pair<uint32_t, uint32_t> std140_size_align(const std::string& property_type) {
    // Scalars.
    if (property_type == "Float" || property_type == "Int" || property_type == "Bool") {
        return {4u, 4u};
    }
    // Two-component vector.
    if (property_type == "Vec2") {
        return {8u, 8u};
    }
    // Three-component vector: data size 12, but base alignment is 16.
    if (property_type == "Vec3") {
        return {12u, 16u};
    }
    // Four-component vectors.
    if (property_type == "Vec4" || property_type == "Color") {
        return {16u, 16u};
    }
    // 4x4 matrix — four column vec4s, base alignment 16.
    if (property_type == "Mat4") {
        return {64u, 16u};
    }
    // Texture / anything else: not in UBO.
    return {0u, 0u};
}

static uint32_t round_up(uint32_t value, uint32_t align) {
    if (align == 0) return value;
    return (value + align - 1u) & ~(align - 1u);
}

MaterialUboLayout compute_std140_layout(const std::vector<MaterialProperty>& properties) {
    MaterialUboLayout layout;
    uint32_t cursor = 0;

    for (const auto& prop : properties) {
        auto [size, align] = std140_size_align(prop.property_type);
        if (size == 0) continue;  // Texture / unknown — skip.

        cursor = round_up(cursor, align);

        MaterialUboEntry entry;
        entry.name = prop.name;
        entry.property_type = prop.property_type;
        entry.offset = cursor;
        entry.size = size;
        layout.entries.push_back(std::move(entry));

        cursor += size;
    }

    // Whole block rounds up to 16-byte boundary per std140.
    layout.block_size = round_up(cursor, 16u);
    return layout;
}

std::string synthesize_material_ubo_glsl(const MaterialUboLayout& layout) {
    if (layout.empty()) return "";

    auto glsl_type = [](const std::string& prop_type) -> const char* {
        if (prop_type == "Float") return "float";
        if (prop_type == "Int")   return "int";
        if (prop_type == "Bool")  return "bool";
        if (prop_type == "Vec2")  return "vec2";
        if (prop_type == "Vec3")  return "vec3";
        if (prop_type == "Vec4")  return "vec4";
        if (prop_type == "Color") return "vec4";
        if (prop_type == "Mat4")  return "mat4";
        return nullptr;
    };

    std::ostringstream out;
    out << "layout(std140) uniform MaterialParams {\n";
    for (const auto& e : layout.entries) {
        const char* t = glsl_type(e.property_type);
        if (!t) continue;
        out << "    " << t << " " << e.name << ";\n";
    }
    out << "};\n";
    return out.str();
}

std::string strip_uniform_decls(const std::string& source,
                                const std::vector<std::string>& names) {
    if (names.empty()) return source;

    // Match simple top-level declarations: `uniform <type> <name>;` where
    // name is one of the provided. Use a per-name regex to avoid conflating
    // similarly-prefixed identifiers (u_strength / u_strength2).
    std::string result = source;
    for (const auto& name : names) {
        // Escape nothing — property names are simple identifiers.
        std::string pattern =
            std::string("^[ \\t]*uniform[ \\t]+[A-Za-z_][A-Za-z0-9_]*[ \\t]+") +
            name + "[ \\t]*;[ \\t]*\\n?";
        std::regex re(pattern, std::regex::multiline);
        result = std::regex_replace(result, re, "");
    }
    return result;
}

std::string inject_after_version(const std::string& source, const std::string& block) {
    if (block.empty()) return source;

    // Find the first `#version ...\n` line and insert block right after it.
    std::regex version_re(R"(^[ \t]*#version[^\n]*\n)", std::regex::multiline);
    std::smatch m;
    if (std::regex_search(source, m, version_re)) {
        size_t insert_at = m.position(0) + m.length(0);
        return source.substr(0, insert_at) + block + source.substr(insert_at);
    }
    // No #version — prepend.
    return block + source;
}

// ========== std140 value packer ==========

namespace {

// Scalar readers: convert the property's variant payload to a single float
// (std140 bool stores as 4-byte int-style 0/1, but since we read back as
// vec4 in shaders for bools it's safe to write as float 0.0/1.0 — the bit
// pattern matches for 0 and 1 in IEEE 754).

inline void write_float(uint8_t* dst, float v) {
    std::memcpy(dst, &v, sizeof(float));
}

inline void write_int(uint8_t* dst, int32_t v) {
    std::memcpy(dst, &v, sizeof(int32_t));
}

// Write up to `count` floats from a vector<double> source. Missing elements
// default to 0.0. Used for Vec2/Vec3/Vec4/Color.
inline void write_float_array(uint8_t* dst,
                               const std::vector<double>& src,
                               size_t count) {
    for (size_t i = 0; i < count; ++i) {
        float v = i < src.size() ? static_cast<float>(src[i]) : 0.0f;
        write_float(dst + i * sizeof(float), v);
    }
}

// Resolve a property-type string + variant payload into raw std140 bytes at
// the given destination. Returns true if a value was actually written.
bool pack_one(const std::string& property_type,
              const MaterialProperty::DefaultValue& value,
              uint8_t* dst) {
    if (property_type == "Float") {
        if (auto* d = std::get_if<double>(&value)) {
            write_float(dst, static_cast<float>(*d));
            return true;
        }
        if (auto* i = std::get_if<int>(&value)) {
            write_float(dst, static_cast<float>(*i));
            return true;
        }
        return false;
    }
    if (property_type == "Int") {
        if (auto* i = std::get_if<int>(&value)) {
            write_int(dst, *i);
            return true;
        }
        if (auto* d = std::get_if<double>(&value)) {
            write_int(dst, static_cast<int32_t>(*d));
            return true;
        }
        return false;
    }
    if (property_type == "Bool") {
        if (auto* b = std::get_if<bool>(&value)) {
            write_int(dst, *b ? 1 : 0);
            return true;
        }
        return false;
    }
    if (property_type == "Vec2" || property_type == "Vec3" ||
        property_type == "Vec4" || property_type == "Color") {
        auto* arr = std::get_if<std::vector<double>>(&value);
        if (!arr) return false;

        size_t count = 4;
        if (property_type == "Vec2") count = 2;
        else if (property_type == "Vec3") count = 3;
        // Vec4 / Color → 4.
        write_float_array(dst, *arr, count);
        return true;
    }
    if (property_type == "Mat4") {
        // 16 floats in column-major order, matching Mat44f storage and the
        // GLSL `mat4` default. std140 aligns each column to 16 bytes, which
        // for a tightly-packed mat4 means sequential 16-byte columns — so
        // the raw memcpy-style layout works.
        auto* arr = std::get_if<std::vector<double>>(&value);
        if (!arr) return false;
        write_float_array(dst, *arr, 16);
        return true;
    }
    // Texture or unknown — not in UBO.
    return false;
}

} // namespace

namespace {

// Two property_type strings are "compatible" for std140 packing if they
// pack to the same std140 slot layout. This is needed because the
// runtime value side (tc_uniform_value → MaterialProperty) doesn't know
// whether the original declaration was `Color` or `Vec4` — both round-
// trip through a vec4 of floats. Similarly, Float/Int can be written
// through the same 4-byte slot, and Bool packs identically to Int
// (std140 rule: Bool is stored as 32-bit uint).
bool property_types_compatible(const std::string& a, const std::string& b) {
    if (a == b) return true;
    // Color and Vec4 are the same std140 payload.
    if ((a == "Color" && b == "Vec4") || (a == "Vec4" && b == "Color")) return true;
    return false;
}

} // namespace

void std140_pack(const MaterialUboLayout& layout,
                 const std::vector<MaterialProperty>& values,
                 uint8_t* out_buffer) {
    if (!out_buffer || layout.empty()) return;

    // For each UBO entry, find a matching value by name. Linear scan is
    // fine — material UBOs have at most a handful of fields.
    for (const auto& entry : layout.entries) {
        const MaterialProperty* match = nullptr;
        for (const auto& v : values) {
            if (v.name == entry.name) {
                match = &v;
                break;
            }
        }
        if (!match) continue;  // leave the slot as-is (caller may have zeroed it).

        // Type must agree with what the layout expects. Mismatches are
        // skipped to avoid writing garbage into the wrong slot.
        if (!property_types_compatible(match->property_type, entry.property_type)) continue;

        // Always dispatch on the layout's declared type — pack_one reads
        // the layout type to know how many floats to write, and Color
        // packs as a 4-float Vec4.
        pack_one(entry.property_type, match->default_value,
                 out_buffer + entry.offset);
    }
}


MaterialProperty parse_property_directive(const std::string& line) {
    // Remove @property prefix
    std::string content = line.substr(9);  // len("@property") = 9
    content = trim(content);

    // Extract range(...) if present
    std::optional<double> range_min, range_max;
    std::regex range_regex(R"(\brange\s*\(\s*([^,]+)\s*,\s*([^)]+)\s*\))");
    std::smatch range_match;
    if (std::regex_search(content, range_match, range_regex)) {
        try {
            range_min = std::stod(trim(range_match[1].str()));
            range_max = std::stod(trim(range_match[2].str()));
        } catch (...) {
            // Ignore parse errors for range
        }
        // Remove range from content
        content = content.substr(0, range_match.position());
        content = trim(content);
    }

    // Parse: Type name = value
    std::string property_type, name, value_str;

    size_t eq_pos = content.find('=');
    if (eq_pos != std::string::npos) {
        // Has default value
        std::string left = trim(content.substr(0, eq_pos));
        value_str = trim(content.substr(eq_pos + 1));

        auto parts = split_whitespace(left);
        if (parts.size() < 2) {
            throw std::runtime_error("@property requires type and name: " + line);
        }
        property_type = parts[0];
        name = parts[1];
    } else {
        // No default value
        auto parts = split_whitespace(content);
        if (parts.size() < 2) {
            throw std::runtime_error("@property requires type and name: " + line);
        }
        property_type = parts[0];
        name = parts[1];
    }

    // Validate type (Texture2D is alias for Texture)
    if (property_type == "Texture2D") {
        property_type = "Texture";
    }
    static const std::vector<std::string> valid_types = {
        "Float", "Int", "Bool", "Vec2", "Vec3", "Vec4", "Color", "Mat4", "Texture"
    };
    bool type_valid = std::find(valid_types.begin(), valid_types.end(), property_type) != valid_types.end();
    if (!type_valid) {
        throw std::runtime_error("Unknown property type: " + property_type);
    }

    // Parse default value
    MaterialProperty::DefaultValue default_value;
    if (!value_str.empty()) {
        default_value = parse_property_value(value_str, property_type);
    } else {
        default_value = get_default_for_type(property_type);
    }

    return MaterialProperty(name, property_type, default_value, range_min, range_max);
}


ShaderMultyPhaseProgramm parse_shader_text(const std::string& text) {
    std::istringstream stream(text);
    std::string raw_line;

    std::string program_name;
    std::vector<ShaderPhase> phases;
    std::vector<std::string> features;  // From @features directive

    // For @phases mode (shared stages)
    std::vector<std::string> declared_phases;  // From @phases directive
    std::unordered_map<std::string, ShaderStage> shared_stages;
    std::vector<MaterialProperty> shared_uniforms;
    std::unordered_map<std::string, ShaderPhase> phase_settings;  // Per-phase overrides

    ShaderPhase* current_phase = nullptr;
    std::string current_settings_phase;  // Which phase @settings applies to
    std::string current_stage_name;
    std::vector<std::string> current_stage_lines;
    bool in_shared_stage = false;  // Stage outside @phase (for @phases mode)

    auto close_current_stage = [&]() {
        if (current_stage_name.empty()) return;

        std::string source;
        for (const auto& l : current_stage_lines) {
            source += l;
        }

        if (in_shared_stage) {
            // Shared stage (for @phases mode)
            shared_stages[current_stage_name] = ShaderStage(current_stage_name, source);
        } else if (current_phase) {
            // Traditional @phase mode
            current_phase->stages[current_stage_name] = ShaderStage(current_stage_name, source);
        }

        current_stage_name.clear();
        current_stage_lines.clear();
        in_shared_stage = false;
    };

    auto close_current_phase = [&]() {
        if (!current_phase) return;
        close_current_stage();
        phases.push_back(std::move(*current_phase));
        delete current_phase;
        current_phase = nullptr;
    };

    while (std::getline(stream, raw_line)) {
        // Keep newline for stage content
        std::string line_with_newline = raw_line + "\n";
        std::string line = trim(raw_line);

        // Inside @stage: collect lines until @endstage or another directive
        if (!current_stage_name.empty()) {
            if (starts_with(line, "@endstage")) {
                close_current_stage();
                continue;
            }
            else if (starts_with(line, "@stage ")) {
                close_current_stage();
                // Fall through to handle @stage below
            }
            else if (starts_with(line, "@phase ")) {
                close_current_stage();
                close_current_phase();
                // Fall through to handle @phase below
            }
            else if (starts_with(line, "@endphase")) {
                close_current_stage();
                // Fall through to handle @endphase below
            }
            else if (starts_with(line, "@settings ")) {
                close_current_stage();
                // Fall through to handle @settings below
            }
            else if (starts_with(line, "@endsettings")) {
                close_current_stage();
                // Fall through
            }
            else {
                current_stage_lines.push_back(line_with_newline);
                continue;
            }
        }

        // Outside @stage: process directives
        if (!starts_with(line, "@") || line == "@") {
            continue;
        }

        auto parts = split_whitespace(line);
        std::string directive = parts[0];

        if (directive == "@program") {
            if (parts.size() < 2) {
                throw std::runtime_error("@program without name");
            }
            program_name = parts[1];
            for (size_t i = 2; i < parts.size(); ++i) {
                program_name += " " + parts[i];
            }
        }
        else if (directive == "@features") {
            // Parse comma-separated feature names: @features lighting_ubo, instancing
            std::string rest = line.substr(9);  // len("@features") = 9
            std::string feature_name;
            for (char c : rest) {
                if (c == ',' || c == ' ' || c == '\t') {
                    std::string trimmed = trim(feature_name);
                    if (!trimmed.empty()) {
                        features.push_back(trimmed);
                        feature_name.clear();
                    }
                } else {
                    feature_name += c;
                }
            }
            std::string trimmed = trim(feature_name);
            if (!trimmed.empty()) {
                features.push_back(trimmed);
            }
        }
        else if (directive == "@phases") {
            // Parse comma-separated phase names: @phases opaque, transparent
            std::string rest = line.substr(7);  // len("@phases") = 7
            std::string phase_name;
            for (char c : rest) {
                if (c == ',' || c == ' ' || c == '\t') {
                    std::string trimmed = trim(phase_name);
                    if (!trimmed.empty()) {
                        declared_phases.push_back(trimmed);
                        phase_name.clear();
                    }
                } else {
                    phase_name += c;
                }
            }
            std::string trimmed = trim(phase_name);
            if (!trimmed.empty()) {
                declared_phases.push_back(trimmed);
            }
        }
        else if (directive == "@settings") {
            if (parts.size() < 2) {
                throw std::runtime_error("@settings without phase name");
            }
            current_settings_phase = parts[1];
            // Initialize settings for this phase if not exists
            if (phase_settings.find(current_settings_phase) == phase_settings.end()) {
                phase_settings[current_settings_phase] = ShaderPhase(current_settings_phase);
            }
        }
        else if (directive == "@endsettings") {
            current_settings_phase.clear();
        }
        else if (directive == "@phase") {
            if (parts.size() < 2) {
                throw std::runtime_error("@phase without mark");
            }
            close_current_phase();

            // Parse comma-separated marks: @phase mark1, mark2
            std::string rest = line.substr(6);  // len("@phase") = 6
            std::vector<std::string> marks;
            std::string mark_name;
            for (char c : rest) {
                if (c == ',' || c == ' ' || c == '\t') {
                    std::string trimmed = trim(mark_name);
                    if (!trimmed.empty()) {
                        marks.push_back(trimmed);
                        mark_name.clear();
                    }
                } else {
                    mark_name += c;
                }
            }
            std::string trimmed = trim(mark_name);
            if (!trimmed.empty()) {
                marks.push_back(trimmed);
            }

            current_phase = new ShaderPhase(std::move(marks));
        }
        else if (directive == "@endphase") {
            close_current_phase();
        }
        else if (directive == "@priority") {
            if (!current_settings_phase.empty()) {
                if (parts.size() < 2) throw std::runtime_error("@priority without value");
                phase_settings[current_settings_phase].priority = std::stoi(parts[1]);
            } else if (current_phase) {
                if (parts.size() < 2) throw std::runtime_error("@priority without value");
                current_phase->priority = std::stoi(parts[1]);
            } else {
                throw std::runtime_error("@priority outside @phase or @settings");
            }
        }
        else if (directive == "@glDepthMask") {
            if (parts.size() < 2) throw std::runtime_error("@glDepthMask without value");
            bool val = parse_bool(parts[1]);
            if (!current_settings_phase.empty()) {
                phase_settings[current_settings_phase].gl_depth_mask = val;
            } else if (current_phase) {
                current_phase->gl_depth_mask = val;
            } else {
                throw std::runtime_error("@glDepthMask outside @phase or @settings");
            }
        }
        else if (directive == "@glDepthTest") {
            if (parts.size() < 2) throw std::runtime_error("@glDepthTest without value");
            bool val = parse_bool(parts[1]);
            if (!current_settings_phase.empty()) {
                phase_settings[current_settings_phase].gl_depth_test = val;
            } else if (current_phase) {
                current_phase->gl_depth_test = val;
            } else {
                throw std::runtime_error("@glDepthTest outside @phase or @settings");
            }
        }
        else if (directive == "@glBlend") {
            if (parts.size() < 2) throw std::runtime_error("@glBlend without value");
            bool val = parse_bool(parts[1]);
            if (!current_settings_phase.empty()) {
                phase_settings[current_settings_phase].gl_blend = val;
            } else if (current_phase) {
                current_phase->gl_blend = val;
            } else {
                throw std::runtime_error("@glBlend outside @phase or @settings");
            }
        }
        else if (directive == "@glCull") {
            if (parts.size() < 2) throw std::runtime_error("@glCull without value");
            bool val = parse_bool(parts[1]);
            if (!current_settings_phase.empty()) {
                phase_settings[current_settings_phase].gl_cull = val;
            } else if (current_phase) {
                current_phase->gl_cull = val;
            } else {
                throw std::runtime_error("@glCull outside @phase or @settings");
            }
        }
        else if (directive == "@stage") {
            if (parts.size() < 2) {
                throw std::runtime_error("@stage without name");
            }
            if (!current_stage_name.empty()) {
                throw std::runtime_error("Nested @stage not supported");
            }
            current_stage_name = parts[1];
            current_stage_lines.clear();

            // If inside @phase, it's phase-specific; otherwise shared
            in_shared_stage = (current_phase == nullptr);
        }
        else if (directive == "@endstage") {
            close_current_stage();
        }
        else if (directive == "@property") {
            auto prop = parse_property_directive(line);
            if (current_phase) {
                current_phase->uniforms.push_back(std::move(prop));
            } else {
                // Shared property (for @phases mode)
                shared_uniforms.push_back(std::move(prop));
            }
        }
        else {
            throw std::runtime_error("Unknown directive: " + directive);
        }
    }

    // Close anything remaining
    close_current_stage();
    if (current_phase) {
        close_current_phase();
    }

    // If @phases was used, generate ONE phase with all marks as available choices
    if (!declared_phases.empty()) {
        ShaderPhase phase(declared_phases);  // Constructor sets phase_mark to first, available_marks to all

        // Copy shared stages
        phase.stages = shared_stages;

        // Copy shared uniforms
        phase.uniforms = shared_uniforms;

        // Apply default opaque settings
        phase.gl_depth_test = true;
        phase.gl_depth_mask = true;
        phase.gl_blend = false;
        phase.gl_cull = true;
        phase.priority = 0;

        // Store per-mark settings from @settings blocks
        for (const auto& mark : declared_phases) {
            PhaseRenderSettings settings;
            // Default opaque settings
            settings.gl_depth_test = true;
            settings.gl_depth_mask = true;
            settings.gl_blend = false;
            settings.gl_cull = true;
            settings.priority = 0;

            // Apply overrides from @settings
            auto it = phase_settings.find(mark);
            if (it != phase_settings.end()) {
                const auto& overrides = it->second;
                if (overrides.gl_depth_test.has_value())
                    settings.gl_depth_test = overrides.gl_depth_test;
                if (overrides.gl_depth_mask.has_value())
                    settings.gl_depth_mask = overrides.gl_depth_mask;
                if (overrides.gl_blend.has_value())
                    settings.gl_blend = overrides.gl_blend;
                if (overrides.gl_cull.has_value())
                    settings.gl_cull = overrides.gl_cull;
                if (overrides.priority != 0)
                    settings.priority = overrides.priority;
            }

            // Default priority for transparent
            if (mark == "transparent" && settings.priority == 0) {
                settings.priority = 1000;
            }

            phase.mark_settings[mark] = settings;
        }

        // Apply settings for the default (first) phase mark
        auto it = phase.mark_settings.find(phase.phase_mark);
        if (it != phase.mark_settings.end()) {
            const auto& s = it->second;
            phase.gl_depth_test = s.gl_depth_test;
            phase.gl_depth_mask = s.gl_depth_mask;
            phase.gl_blend = s.gl_blend;
            phase.gl_cull = s.gl_cull;
            phase.priority = s.priority;
        }

        phases.push_back(std::move(phase));
    }

    ShaderMultyPhaseProgramm result(program_name, std::move(phases), "", std::move(features));

    // Material UBO synthesis is unconditional: any phase that declares
    // scalar/vector @property entries gets a std140 MaterialParams block
    // auto-synthesized, injected into the stage sources, and the original
    // `uniform T name;` decls stripped from the raw GLSL. Texture
    // properties stay as plain samplers outside the block
    // (compute_std140_layout skips them).
    //
    // Phases without UBO-eligible properties get an empty layout and
    // their sources are left alone.
    //
    // The former `@features material_ubo` opt-in was temporary scaffolding
    // for the migration; see shadow/depth/normal/id pass pattern for the
    // same "two code paths converge into one" cleanup.
    for (auto& phase : result.phases) {
        MaterialUboLayout layout = compute_std140_layout(phase.uniforms);
        if (layout.empty()) continue;

        std::string block_glsl = synthesize_material_ubo_glsl(layout);

        std::vector<std::string> ubo_names;
        ubo_names.reserve(layout.entries.size());
        for (const auto& e : layout.entries) {
            ubo_names.push_back(e.name);
        }

        for (auto& kv : phase.stages) {
            std::string& src = kv.second.source;
            src = strip_uniform_decls(src, ubo_names);
            src = inject_after_version(src, block_glsl);
        }

        phase.material_ubo_layout = std::move(layout);
    }

    return result;
}

} // namespace termin
