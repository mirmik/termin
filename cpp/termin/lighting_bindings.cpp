#include <pybind11/pybind11.h>
#include <pybind11/numpy.h>
#include <pybind11/stl.h>
#include <pybind11/operators.h>

#include "termin/lighting/lighting.hpp"
#include "termin/geom/vec3.hpp"

namespace py = pybind11;
using namespace termin;

// Helper: Vec3 to numpy array
static py::array_t<double> vec3_to_numpy(const Vec3& v) {
    auto result = py::array_t<double>(3);
    auto buf = result.mutable_unchecked<1>();
    buf(0) = v.x;
    buf(1) = v.y;
    buf(2) = v.z;
    return result;
}

// Helper: numpy array to Vec3
static Vec3 numpy_to_vec3(py::object obj) {
    if (py::isinstance<Vec3>(obj)) {
        return obj.cast<Vec3>();
    }
    auto arr = py::array_t<double>::ensure(obj);
    if (arr && arr.size() >= 3) {
        auto buf = arr.unchecked<1>();
        return Vec3{buf(0), buf(1), buf(2)};
    }
    auto seq = obj.cast<py::sequence>();
    return Vec3{seq[0].cast<double>(), seq[1].cast<double>(), seq[2].cast<double>()};
}

PYBIND11_MODULE(_lighting_native, m) {
    m.doc() = "Native C++ lighting module for termin";

    // Import geom module to register Vec3 type
    py::module_::import("termin.geombase._geom_native");

    // ShadowSettings - scene-wide shadow rendering settings
    py::class_<ShadowSettings>(m, "ShadowSettings")
        .def(py::init<>())
        .def(py::init<int, double, double>(),
             py::arg("method") = ShadowSettings::METHOD_PCF,
             py::arg("softness") = 1.0,
             py::arg("bias") = 0.005)
        .def_readwrite("method", &ShadowSettings::method)
        .def_readwrite("softness", &ShadowSettings::softness)
        .def_readwrite("bias", &ShadowSettings::bias)
        .def_readonly_static("METHOD_HARD", &ShadowSettings::METHOD_HARD)
        .def_readonly_static("METHOD_PCF", &ShadowSettings::METHOD_PCF)
        .def_readonly_static("METHOD_POISSON", &ShadowSettings::METHOD_POISSON)
        .def("serialize", [](const ShadowSettings& s) {
            py::dict d;
            d["method"] = s.method;
            d["softness"] = s.softness;
            d["bias"] = s.bias;
            return d;
        })
        .def("load_from_data", [](ShadowSettings& s, py::dict data) {
            if (data.contains("method")) s.method = data["method"].cast<int>();
            if (data.contains("softness")) s.softness = data["softness"].cast<double>();
            if (data.contains("bias")) s.bias = data["bias"].cast<double>();
        }, py::arg("data"))
        .def("__repr__", [](const ShadowSettings& s) {
            const char* method_names[] = {"Hard", "PCF 5x5", "Poisson"};
            const char* method_name = (s.method >= 0 && s.method <= 2) ? method_names[s.method] : "Unknown";
            return "ShadowSettings(method=" + std::string(method_name) +
                   ", softness=" + std::to_string(s.softness) +
                   ", bias=" + std::to_string(s.bias) + ")";
        });

    // AttenuationCoefficients
    py::class_<AttenuationCoefficients>(m, "AttenuationCoefficients")
        .def(py::init<>())
        .def(py::init<double, double, double>(),
             py::arg("constant") = 1.0,
             py::arg("linear") = 0.0,
             py::arg("quadratic") = 0.0)
        .def_readwrite("constant", &AttenuationCoefficients::constant)
        .def_readwrite("linear", &AttenuationCoefficients::linear)
        .def_readwrite("quadratic", &AttenuationCoefficients::quadratic)
        .def("evaluate", &AttenuationCoefficients::evaluate,
             py::arg("distance"),
             "Compute attenuation weight for a given distance")
        .def_static("match_range", &AttenuationCoefficients::match_range,
                    py::arg("falloff_range"),
                    py::arg("cutoff") = 0.01,
                    "Create coefficients that attenuate to cutoff at range")
        .def_static("inverse_square", &AttenuationCoefficients::inverse_square,
                    "Physical inverse-square attenuation: w(d) = 1/d^2")
        .def("__repr__", [](const AttenuationCoefficients& a) {
            return "AttenuationCoefficients(constant=" + std::to_string(a.constant) +
                   ", linear=" + std::to_string(a.linear) +
                   ", quadratic=" + std::to_string(a.quadratic) + ")";
        });

    // LightType enum
    py::enum_<LightType>(m, "LightType")
        .value("DIRECTIONAL", LightType::Directional)
        .value("POINT", LightType::Point)
        .value("SPOT", LightType::Spot);

    // Helper to create LightType from string or int
    m.def("light_type_from_value", [](py::object value) -> LightType {
        if (py::isinstance<py::str>(value)) {
            return light_type_from_string(value.cast<std::string>());
        }
        if (py::isinstance<LightType>(value)) {
            return value.cast<LightType>();
        }
        return static_cast<LightType>(value.cast<int>());
    }, py::arg("value"), "Create LightType from string, int, or LightType");

    // LightShadowParams
    py::class_<LightShadowParams>(m, "LightShadowParams")
        .def(py::init<>())
        .def(py::init<bool, double, double, int>(),
             py::arg("enabled") = false,
             py::arg("bias") = 0.001,
             py::arg("normal_bias") = 0.0,
             py::arg("map_resolution") = 1024)
        .def_readwrite("enabled", &LightShadowParams::enabled)
        .def_readwrite("bias", &LightShadowParams::bias)
        .def_readwrite("normal_bias", &LightShadowParams::normal_bias)
        .def_readwrite("map_resolution", &LightShadowParams::map_resolution)
        .def("__repr__", [](const LightShadowParams& s) {
            return "LightShadowParams(enabled=" + std::string(s.enabled ? "True" : "False") +
                   ", bias=" + std::to_string(s.bias) + ")";
        });

    // LightSample
    py::class_<LightSample>(m, "LightSample")
        .def(py::init<>())
        .def_property("L",
            [](const LightSample& s) { return vec3_to_numpy(s.L); },
            [](LightSample& s, py::object v) { s.L = numpy_to_vec3(v); })
        .def_readwrite("distance", &LightSample::distance)
        .def_readwrite("attenuation", &LightSample::attenuation)
        .def_property("radiance",
            [](const LightSample& s) { return vec3_to_numpy(s.radiance); },
            [](LightSample& s, py::object v) { s.radiance = numpy_to_vec3(v); });

    // Light
    py::class_<Light>(m, "Light")
        .def(py::init<>())
        .def(py::init([](LightType type, py::object color, double intensity,
                         py::object direction, py::object position,
                         py::object range, double inner_angle, double outer_angle,
                         const AttenuationCoefficients& attenuation,
                         const LightShadowParams& shadows, const std::string& name) {
            Light l;
            l.type = type;
            if (!color.is_none()) l.color = numpy_to_vec3(color);
            l.intensity = intensity;
            if (!direction.is_none()) l.direction = numpy_to_vec3(direction).normalized();
            if (!position.is_none()) l.position = numpy_to_vec3(position);
            if (!range.is_none()) l.range = range.cast<double>();
            l.inner_angle = inner_angle;
            l.outer_angle = outer_angle;
            l.attenuation = attenuation;
            l.shadows = shadows;
            l.name = name;
            return l;
        }),
             py::arg("type") = LightType::Directional,
             py::arg("color") = py::none(),
             py::arg("intensity") = 1.0,
             py::arg("direction") = py::none(),
             py::arg("position") = py::none(),
             py::arg("range") = py::none(),
             py::arg("inner_angle") = 15.0 * M_PI / 180.0,
             py::arg("outer_angle") = 30.0 * M_PI / 180.0,
             py::arg("attenuation") = AttenuationCoefficients(),
             py::arg("shadows") = LightShadowParams(),
             py::arg("name") = "")
        .def_readwrite("type", &Light::type)
        .def_property("color",
            [](const Light& l) { return vec3_to_numpy(l.color); },
            [](Light& l, py::object v) { l.color = numpy_to_vec3(v); })
        .def_readwrite("intensity", &Light::intensity)
        .def_property("direction",
            [](const Light& l) { return vec3_to_numpy(l.direction); },
            [](Light& l, py::object v) { l.direction = numpy_to_vec3(v).normalized(); })
        .def_property("position",
            [](const Light& l) { return vec3_to_numpy(l.position); },
            [](Light& l, py::object v) { l.position = numpy_to_vec3(v); })
        .def_property("range",
            [](const Light& l) -> py::object {
                if (l.range.has_value()) return py::float_(l.range.value());
                return py::none();
            },
            [](Light& l, py::object v) {
                if (v.is_none()) l.range = std::nullopt;
                else l.range = v.cast<double>();
            })
        .def_readwrite("inner_angle", &Light::inner_angle)
        .def_readwrite("outer_angle", &Light::outer_angle)
        .def_readwrite("attenuation", &Light::attenuation)
        .def_readwrite("shadows", &Light::shadows)
        .def_readwrite("name", &Light::name)
        .def_property_readonly("intensity_rgb", [](const Light& l) {
            return vec3_to_numpy(l.intensity_rgb());
        })
        .def("sample", [](const Light& l, py::object point) {
            return l.sample(numpy_to_vec3(point));
        }, py::arg("point"), "Evaluate light contribution at a surface point")
        .def("to_uniform_dict", [](const Light& l) {
            py::dict d;
            d["type"] = light_type_to_string(l.type);
            d["color"] = py::list(py::make_tuple(l.color.x, l.color.y, l.color.z));
            d["intensity"] = l.intensity;
            Vec3 dir = l.direction.normalized();
            d["direction"] = py::list(py::make_tuple(dir.x, dir.y, dir.z));
            d["position"] = py::list(py::make_tuple(l.position.x, l.position.y, l.position.z));
            d["range"] = l.range.has_value() ? py::cast(l.range.value()) : py::none();
            d["inner_angle"] = l.inner_angle;
            d["outer_angle"] = l.outer_angle;
            py::dict atten;
            atten["constant"] = l.attenuation.constant;
            atten["linear"] = l.attenuation.linear;
            atten["quadratic"] = l.attenuation.quadratic;
            d["attenuation"] = atten;
            py::dict shad;
            shad["enabled"] = l.shadows.enabled;
            shad["bias"] = l.shadows.bias;
            shad["normal_bias"] = l.shadows.normal_bias;
            shad["map_resolution"] = l.shadows.map_resolution;
            d["shadows"] = shad;
            d["name"] = l.name;
            return d;
        }, "Pack parameters into dict for uniform uploads")
        .def("__repr__", [](const Light& l) {
            return "Light(type=" + std::string(light_type_to_string(l.type)) +
                   ", intensity=" + std::to_string(l.intensity) +
                   ", name='" + l.name + "')";
        });
}
