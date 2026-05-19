#include "common.hpp"

namespace termin {

void bind_shader_parser(nb::module_& m) {
    nb::module_ materials = nb::module_::import_("termin.materials._materials_native");

    m.attr("GlslPreprocessor") = materials.attr("GlslPreprocessor");
    m.attr("glsl_preprocessor") = materials.attr("glsl_preprocessor");
    m.attr("register_glsl_preprocessor") = materials.attr("register_glsl_preprocessor");

    m.attr("MaterialProperty") = materials.attr("MaterialProperty");
    m.attr("UniformProperty") = materials.attr("UniformProperty");
    m.attr("ShaderStage") = materials.attr("ShaderStage");
    m.attr("ShasderStage") = materials.attr("ShasderStage");
    m.attr("PhaseRenderSettings") = materials.attr("PhaseRenderSettings");
    m.attr("MaterialUboEntry") = materials.attr("MaterialUboEntry");
    m.attr("MaterialUboLayout") = materials.attr("MaterialUboLayout");
    m.attr("ShaderPhase") = materials.attr("ShaderPhase");
    m.attr("ShaderMultyPhaseProgramm") = materials.attr("ShaderMultyPhaseProgramm");
    m.attr("parse_shader_text") = materials.attr("parse_shader_text");
    m.attr("parse_property_directive") = materials.attr("parse_property_directive");
}

} // namespace termin
