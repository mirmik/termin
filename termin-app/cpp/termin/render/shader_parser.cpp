#include "shader_parser.hpp"

#include <sstream>
#include <algorithm>
#include <cctype>
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
        "Float", "Int", "Bool", "Vec2", "Vec3", "Vec4", "Color", "Texture"
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
    return result;
}

} // namespace termin
