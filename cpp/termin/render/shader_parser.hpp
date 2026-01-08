#pragma once

#include <string>
#include <vector>
#include <unordered_map>
#include <optional>
#include <variant>
#include <stdexcept>

namespace termin {

/**
 * Material property for inspector.
 *
 * Types: Float, Int, Bool, Vec2, Vec3, Vec4, Color, Texture
 */
struct MaterialProperty {
    std::string name;
    std::string property_type;  // "Float", "Int", "Bool", "Vec2", etc.

    // Default value as variant
    using DefaultValue = std::variant<
        std::monostate,         // None/Texture
        bool,                   // Bool
        int,                    // Int
        double,                 // Float
        std::vector<double>,    // Vec2, Vec3, Vec4, Color
        std::string             // Texture path
    >;
    DefaultValue default_value;

    std::optional<double> range_min;
    std::optional<double> range_max;
    std::optional<std::string> label;

    MaterialProperty() = default;
    MaterialProperty(
        std::string name_,
        std::string type_,
        DefaultValue default_ = std::monostate{},
        std::optional<double> min_ = std::nullopt,
        std::optional<double> max_ = std::nullopt,
        std::optional<std::string> label_ = std::nullopt
    ) : name(std::move(name_)),
        property_type(std::move(type_)),
        default_value(std::move(default_)),
        range_min(min_),
        range_max(max_),
        label(std::move(label_)) {}
};

// Alias for backward compatibility
using UniformProperty = MaterialProperty;


/**
 * Single shader stage (vertex, fragment, geometry).
 */
struct ShaderStage {
    std::string name;
    std::string source;

    ShaderStage() = default;
    ShaderStage(std::string name_, std::string source_)
        : name(std::move(name_)), source(std::move(source_)) {}
};


/**
 * Shader phase: stages + render state flags + uniform properties.
 */
struct ShaderPhase {
    std::string phase_mark;  // Primary/default mark
    std::vector<std::string> available_marks;  // All available marks (for user choice)
    int priority = 0;

    // Render state flags (null = not specified, use default)
    std::optional<bool> gl_depth_mask;
    std::optional<bool> gl_depth_test;
    std::optional<bool> gl_blend;
    std::optional<bool> gl_cull;

    // Stages by name (vertex, fragment, geometry)
    std::unordered_map<std::string, ShaderStage> stages;

    // Uniform properties for material inspector
    std::vector<MaterialProperty> uniforms;

    ShaderPhase() = default;
    ShaderPhase(std::string mark) : phase_mark(std::move(mark)) {
        available_marks.push_back(phase_mark);
    }
    ShaderPhase(std::vector<std::string> marks)
        : phase_mark(marks.empty() ? "" : marks[0]),
          available_marks(std::move(marks)) {}
};


/**
 * Multi-phase shader program.
 */
class ShaderMultyPhaseProgramm {
public:
    std::string program;  // Program name
    std::vector<ShaderPhase> phases;
    std::string source_path;

    ShaderMultyPhaseProgramm() = default;
    ShaderMultyPhaseProgramm(
        std::string program_,
        std::vector<ShaderPhase> phases_,
        std::string source_path_ = ""
    ) : program(std::move(program_)),
        phases(std::move(phases_)),
        source_path(std::move(source_path_)) {}

    /**
     * Get phase by mark.
     */
    const ShaderPhase* get_phase(const std::string& mark) const {
        for (const auto& phase : phases) {
            if (phase.phase_mark == mark) {
                return &phase;
            }
        }
        return nullptr;
    }
};


// ========== Parser Functions ==========

/**
 * Parse shader text in custom format.
 *
 * Supported directives:
 *   @program <name>
 *
 *   // Traditional multi-phase (explicit):
 *   @phase <mark>
 *   @priority <int>
 *   @glDepthMask <bool>
 *   @glDepthTest <bool>
 *   @glBlend <bool>
 *   @glCull <bool>
 *   @property <Type> <name> [= DefaultValue] [range(min, max)]
 *   @stage <stage_name>
 *   @endstage
 *   @endphase
 *
 *   // Shared stages multi-phase (new syntax):
 *   @phases <mark1>, <mark2>, ...     // Declares phases with shared code
 *   @settings <mark>                  // Per-phase render state overrides
 *   @endsettings                      // Optional end of settings block
 *   @property ...                     // Shared properties (outside @phase)
 *   @stage vertex / @stage fragment   // Shared stages (outside @phase)
 */
ShaderMultyPhaseProgramm parse_shader_text(const std::string& text);

/**
 * Parse bool from string.
 */
bool parse_bool(const std::string& value);

/**
 * Parse @property directive.
 */
MaterialProperty parse_property_directive(const std::string& line);

} // namespace termin
