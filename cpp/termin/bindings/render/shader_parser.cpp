#include "common.hpp"
#include "termin/render/shader_parser.hpp"
#include "termin/render/glsl_preprocessor.hpp"

namespace termin {

void bind_shader_parser(py::module_& m) {
    // --- GLSL preprocessor ---
    py::class_<GlslPreprocessor>(m, "GlslPreprocessor")
        .def(py::init<>())
        .def("register_include", &GlslPreprocessor::register_include,
            py::arg("name"), py::arg("source"),
            "Register an include file")
        .def("has_include", &GlslPreprocessor::has_include)
        .def("get_include", [](const GlslPreprocessor& pp, const std::string& name) -> py::object {
            const std::string* src = pp.get_include(name);
            return src ? py::cast(*src) : py::none();
        })
        .def("clear", &GlslPreprocessor::clear)
        .def("size", &GlslPreprocessor::size)
        .def_static("has_includes", &GlslPreprocessor::has_includes)
        .def("preprocess", &GlslPreprocessor::preprocess,
            py::arg("source"), py::arg("source_name") = "<unknown>",
            "Preprocess GLSL source, resolving #include directives");

    m.def("glsl_preprocessor", &glsl_preprocessor, py::return_value_policy::reference,
        "Get the global GLSL preprocessor instance");

    // --- MaterialProperty (UniformProperty) ---
    py::class_<MaterialProperty>(m, "MaterialProperty")
        .def(py::init<>())
        .def(py::init<std::string, std::string>(),
             py::arg("name"), py::arg("property_type"))
        // Full constructor with default value and range
        .def(py::init([](
            const std::string& name,
            const std::string& property_type,
            py::object default_val,
            std::optional<double> range_min,
            std::optional<double> range_max
        ) {
            MaterialProperty prop;
            prop.name = name;
            prop.property_type = property_type;
            prop.range_min = range_min;
            prop.range_max = range_max;

            // Convert Python default value to C++ variant
            if (default_val.is_none()) {
                prop.default_value = std::monostate{};
            } else if (py::isinstance<py::bool_>(default_val)) {
                prop.default_value = default_val.cast<bool>();
            } else if (py::isinstance<py::int_>(default_val)) {
                prop.default_value = default_val.cast<int>();
            } else if (py::isinstance<py::float_>(default_val)) {
                prop.default_value = default_val.cast<double>();
            } else if (py::isinstance<py::str>(default_val)) {
                prop.default_value = default_val.cast<std::string>();
            } else if (py::isinstance<py::tuple>(default_val) || py::isinstance<py::list>(default_val)) {
                std::vector<double> vec;
                for (auto item : default_val) {
                    vec.push_back(item.cast<double>());
                }
                prop.default_value = vec;
            }
            return prop;
        }),
            py::arg("name"),
            py::arg("property_type"),
            py::arg("default") = py::none(),
            py::arg("range_min") = std::nullopt,
            py::arg("range_max") = std::nullopt
        )
        .def_readwrite("name", &MaterialProperty::name)
        .def_readwrite("property_type", &MaterialProperty::property_type)
        .def_readwrite("range_min", &MaterialProperty::range_min)
        .def_readwrite("range_max", &MaterialProperty::range_max)
        .def_readwrite("label", &MaterialProperty::label)
        .def_property("default",
            [](const MaterialProperty& self) -> py::object {
                return std::visit([](auto&& arg) -> py::object {
                    using T = std::decay_t<decltype(arg)>;
                    if constexpr (std::is_same_v<T, std::monostate>) {
                        return py::none();
                    } else if constexpr (std::is_same_v<T, std::vector<double>>) {
                        py::tuple t(arg.size());
                        for (size_t i = 0; i < arg.size(); ++i) {
                            t[i] = arg[i];
                        }
                        return t;
                    } else {
                        return py::cast(arg);
                    }
                }, self.default_value);
            },
            [](MaterialProperty& self, py::object val) {
                if (val.is_none()) {
                    self.default_value = std::monostate{};
                } else if (py::isinstance<py::bool_>(val)) {
                    self.default_value = val.cast<bool>();
                } else if (py::isinstance<py::int_>(val)) {
                    self.default_value = val.cast<int>();
                } else if (py::isinstance<py::float_>(val)) {
                    self.default_value = val.cast<double>();
                } else if (py::isinstance<py::str>(val)) {
                    self.default_value = val.cast<std::string>();
                } else if (py::isinstance<py::tuple>(val) || py::isinstance<py::list>(val)) {
                    std::vector<double> vec;
                    for (auto item : val) {
                        vec.push_back(item.cast<double>());
                    }
                    self.default_value = vec;
                }
            }
        );

    // Alias for backward compatibility
    m.attr("UniformProperty") = m.attr("MaterialProperty");

    // --- ShaderStage ---
    py::class_<ShaderStage>(m, "ShaderStage")
        .def(py::init<>())
        .def(py::init<std::string, std::string>(),
             py::arg("name"), py::arg("source"))
        .def_readwrite("name", &ShaderStage::name)
        .def_readwrite("source", &ShaderStage::source);

    // Alias for typo compatibility
    m.attr("ShasderStage") = m.attr("ShaderStage");

    // --- ShaderPhase ---
    py::class_<ShaderPhase>(m, "ShaderPhase")
        .def(py::init<>())
        .def(py::init<std::string>(), py::arg("phase_mark"))
        // Full constructor with all parameters
        .def(py::init([](
            const std::string& phase_mark,
            int priority,
            std::optional<bool> gl_depth_mask,
            std::optional<bool> gl_depth_test,
            std::optional<bool> gl_blend,
            std::optional<bool> gl_cull,
            const std::unordered_map<std::string, ShaderStage>& stages,
            const std::vector<MaterialProperty>& uniforms
        ) {
            ShaderPhase phase;
            phase.phase_mark = phase_mark;
            phase.priority = priority;
            phase.gl_depth_mask = gl_depth_mask;
            phase.gl_depth_test = gl_depth_test;
            phase.gl_blend = gl_blend;
            phase.gl_cull = gl_cull;
            phase.stages = stages;
            phase.uniforms = uniforms;
            return phase;
        }),
            py::arg("phase_mark"),
            py::arg("priority") = 0,
            py::arg("gl_depth_mask") = std::nullopt,
            py::arg("gl_depth_test") = std::nullopt,
            py::arg("gl_blend") = std::nullopt,
            py::arg("gl_cull") = std::nullopt,
            py::arg("stages") = std::unordered_map<std::string, ShaderStage>{},
            py::arg("uniforms") = std::vector<MaterialProperty>{}
        )
        .def_readwrite("phase_mark", &ShaderPhase::phase_mark)
        .def_readwrite("priority", &ShaderPhase::priority)
        .def_readwrite("gl_depth_mask", &ShaderPhase::gl_depth_mask)
        .def_readwrite("gl_depth_test", &ShaderPhase::gl_depth_test)
        .def_readwrite("gl_blend", &ShaderPhase::gl_blend)
        .def_readwrite("gl_cull", &ShaderPhase::gl_cull)
        .def_readwrite("stages", &ShaderPhase::stages)
        .def_readwrite("uniforms", &ShaderPhase::uniforms)
        // Backward compatibility: identity transform
        .def_static("from_tree", [](const ShaderPhase& phase) {
            return phase;
        }, py::arg("tree"), "Backward compatibility: returns the object as-is");

    // --- ShaderMultyPhaseProgramm ---
    py::class_<ShaderMultyPhaseProgramm>(m, "ShaderMultyPhaseProgramm")
        .def(py::init<>())
        .def(py::init<std::string, std::vector<ShaderPhase>, std::string>(),
             py::arg("program"), py::arg("phases"), py::arg("source_path") = "")
        .def_readwrite("program", &ShaderMultyPhaseProgramm::program)
        .def_readwrite("phases", &ShaderMultyPhaseProgramm::phases)
        .def_readwrite("source_path", &ShaderMultyPhaseProgramm::source_path)
        .def("get_phase", &ShaderMultyPhaseProgramm::get_phase,
             py::arg("mark"), py::return_value_policy::reference)
        // Backward compatibility: parse_shader_text now returns ShaderMultyPhaseProgramm directly
        .def_static("from_tree", [](const ShaderMultyPhaseProgramm& prog) {
            return prog;  // Identity - already parsed
        }, py::arg("tree"), "Backward compatibility: returns the object as-is");

    // Parser functions
    m.def("parse_shader_text", &parse_shader_text,
          py::arg("text"),
          "Parse shader text in custom format");

    m.def("parse_property_directive", &parse_property_directive,
          py::arg("line"),
          "Parse @property directive line");
}

} // namespace termin
