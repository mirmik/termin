#include <nanobind/nanobind.h>
#include <nanobind/ndarray.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/optional.h>
#include <nanobind/operators.h>

#include "termin/lighting/lighting.hpp"
#include "termin/geom/vec3.hpp"

namespace nb = nanobind;
using namespace termin;

// Helper: Vec3 to numpy array
static nb::ndarray<nb::numpy, double, nb::shape<3>> vec3_to_numpy(const Vec3& v) {
    double* data = new double[3]{v.x, v.y, v.z};
    nb::capsule owner(data, [](void* p) noexcept { delete[] static_cast<double*>(p); });
    return nb::ndarray<nb::numpy, double, nb::shape<3>>(data, {3}, owner);
}

// Helper: numpy array to Vec3
static Vec3 numpy_to_vec3(nb::object obj) {
    if (nb::isinstance<Vec3>(obj)) {
        return nb::cast<Vec3>(obj);
    }
    try {
        auto arr = nb::cast<nb::ndarray<double, nb::c_contig, nb::device::cpu>>(obj);
        double* ptr = arr.data();
        return Vec3{ptr[0], ptr[1], ptr[2]};
    } catch (...) {}
    nb::sequence seq = nb::cast<nb::sequence>(obj);
    return Vec3{nb::cast<double>(seq[0]), nb::cast<double>(seq[1]), nb::cast<double>(seq[2])};
}

NB_MODULE(_lighting_native, m) {
    m.doc() = "Native C++ lighting module for termin";

    // Import geom module to register Vec3 type
    nb::module_::import_("termin.geombase._geom_native");

    // ShadowSettings - scene-wide shadow rendering settings
    nb::class_<ShadowSettings>(m, "ShadowSettings")
        .def(nb::init<>())
        .def(nb::init<int, double, double>(),
             nb::arg("method") = ShadowSettings::METHOD_PCF,
             nb::arg("softness") = 1.0,
             nb::arg("bias") = 0.005)
        .def_rw("method", &ShadowSettings::method)
        .def_rw("softness", &ShadowSettings::softness)
        .def_rw("bias", &ShadowSettings::bias)
        .def_ro_static("METHOD_HARD", &ShadowSettings::METHOD_HARD)
        .def_ro_static("METHOD_PCF", &ShadowSettings::METHOD_PCF)
        .def_ro_static("METHOD_POISSON", &ShadowSettings::METHOD_POISSON)
        .def("serialize", [](const ShadowSettings& s) {
            nb::dict d;
            d["method"] = s.method;
            d["softness"] = s.softness;
            d["bias"] = s.bias;
            return d;
        })
        .def("load_from_data", [](ShadowSettings& s, nb::dict data) {
            if (data.contains("method")) s.method = nb::cast<int>(data["method"]);
            if (data.contains("softness")) s.softness = nb::cast<double>(data["softness"]);
            if (data.contains("bias")) s.bias = nb::cast<double>(data["bias"]);
        }, nb::arg("data"))
        .def("__repr__", [](const ShadowSettings& s) {
            const char* method_names[] = {"Hard", "PCF 5x5", "Poisson"};
            const char* method_name = (s.method >= 0 && s.method <= 2) ? method_names[s.method] : "Unknown";
            return "ShadowSettings(method=" + std::string(method_name) +
                   ", softness=" + std::to_string(s.softness) +
                   ", bias=" + std::to_string(s.bias) + ")";
        });

    // AttenuationCoefficients
    nb::class_<AttenuationCoefficients>(m, "AttenuationCoefficients")
        .def(nb::init<>())
        .def(nb::init<double, double, double>(),
             nb::arg("constant") = 1.0,
             nb::arg("linear") = 0.0,
             nb::arg("quadratic") = 0.0)
        .def_rw("constant", &AttenuationCoefficients::constant)
        .def_rw("linear", &AttenuationCoefficients::linear)
        .def_rw("quadratic", &AttenuationCoefficients::quadratic)
        .def("evaluate", &AttenuationCoefficients::evaluate,
             nb::arg("distance"),
             "Compute attenuation weight for a given distance")
        .def_static("match_range", &AttenuationCoefficients::match_range,
                    nb::arg("falloff_range"),
                    nb::arg("cutoff") = 0.01,
                    "Create coefficients that attenuate to cutoff at range")
        .def_static("inverse_square", &AttenuationCoefficients::inverse_square,
                    "Physical inverse-square attenuation: w(d) = 1/d^2")
        .def("__repr__", [](const AttenuationCoefficients& a) {
            return "AttenuationCoefficients(constant=" + std::to_string(a.constant) +
                   ", linear=" + std::to_string(a.linear) +
                   ", quadratic=" + std::to_string(a.quadratic) + ")";
        });

    // LightType enum
    nb::enum_<LightType>(m, "LightType")
        .value("DIRECTIONAL", LightType::Directional)
        .value("POINT", LightType::Point)
        .value("SPOT", LightType::Spot);

    // Helper to create LightType from string or int
    m.def("light_type_from_value", [](nb::object value) -> LightType {
        if (nb::isinstance<nb::str>(value)) {
            return light_type_from_string(nb::cast<std::string>(value));
        }
        if (nb::isinstance<LightType>(value)) {
            return nb::cast<LightType>(value);
        }
        return static_cast<LightType>(nb::cast<int>(value));
    }, nb::arg("value"), "Create LightType from string, int, or LightType");

    // LightShadowParams
    nb::class_<LightShadowParams>(m, "LightShadowParams")
        .def(nb::init<>())
        .def(nb::init<bool, double, double, int>(),
             nb::arg("enabled") = false,
             nb::arg("bias") = 0.001,
             nb::arg("normal_bias") = 0.0,
             nb::arg("map_resolution") = 1024)
        .def_rw("enabled", &LightShadowParams::enabled)
        .def_rw("bias", &LightShadowParams::bias)
        .def_rw("normal_bias", &LightShadowParams::normal_bias)
        .def_rw("map_resolution", &LightShadowParams::map_resolution)
        .def("__repr__", [](const LightShadowParams& s) {
            return "LightShadowParams(enabled=" + std::string(s.enabled ? "True" : "False") +
                   ", bias=" + std::to_string(s.bias) + ")";
        });

    // LightSample
    nb::class_<LightSample>(m, "LightSample")
        .def(nb::init<>())
        .def_prop_rw("L",
            [](const LightSample& s) { return vec3_to_numpy(s.L); },
            [](LightSample& s, nb::object v) { s.L = numpy_to_vec3(v); })
        .def_rw("distance", &LightSample::distance)
        .def_rw("attenuation", &LightSample::attenuation)
        .def_prop_rw("radiance",
            [](const LightSample& s) { return vec3_to_numpy(s.radiance); },
            [](LightSample& s, nb::object v) { s.radiance = numpy_to_vec3(v); });

    // Light
    nb::class_<Light>(m, "Light")
        .def(nb::init<>())
        .def("__init__", [](Light* self, LightType type, nb::object color, double intensity,
                         nb::object direction, nb::object position,
                         nb::object range, double inner_angle, double outer_angle,
                         nb::object attenuation, nb::object shadows, const std::string& name) {
            new (self) Light();
            self->type = type;
            if (!color.is_none()) self->color = numpy_to_vec3(color);
            self->intensity = intensity;
            if (!direction.is_none()) self->direction = numpy_to_vec3(direction).normalized();
            if (!position.is_none()) self->position = numpy_to_vec3(position);
            if (!range.is_none()) self->range = nb::cast<double>(range);
            self->inner_angle = inner_angle;
            self->outer_angle = outer_angle;
            if (!attenuation.is_none()) {
                self->attenuation = nb::cast<AttenuationCoefficients>(attenuation);
            }
            if (!shadows.is_none()) {
                self->shadows = nb::cast<LightShadowParams>(shadows);
            }
            self->name = name;
        },
             nb::arg("type") = LightType::Directional,
             nb::arg("color") = nb::none(),
             nb::arg("intensity") = 1.0,
             nb::arg("direction") = nb::none(),
             nb::arg("position") = nb::none(),
             nb::arg("range") = nb::none(),
             nb::arg("inner_angle") = 15.0 * M_PI / 180.0,
             nb::arg("outer_angle") = 30.0 * M_PI / 180.0,
             nb::arg("attenuation") = nb::none(),
             nb::arg("shadows") = nb::none(),
             nb::arg("name") = "")
        .def_rw("type", &Light::type)
        .def_prop_rw("color",
            [](const Light& l) { return vec3_to_numpy(l.color); },
            [](Light& l, nb::object v) { l.color = numpy_to_vec3(v); })
        .def_rw("intensity", &Light::intensity)
        .def_prop_rw("direction",
            [](const Light& l) { return vec3_to_numpy(l.direction); },
            [](Light& l, nb::object v) { l.direction = numpy_to_vec3(v).normalized(); })
        .def_prop_rw("position",
            [](const Light& l) { return vec3_to_numpy(l.position); },
            [](Light& l, nb::object v) { l.position = numpy_to_vec3(v); })
        .def_prop_rw("range",
            [](const Light& l) -> nb::object {
                if (l.range.has_value()) return nb::float_(l.range.value());
                return nb::none();
            },
            [](Light& l, nb::object v) {
                if (v.is_none()) l.range = std::nullopt;
                else l.range = nb::cast<double>(v);
            })
        .def_rw("inner_angle", &Light::inner_angle)
        .def_rw("outer_angle", &Light::outer_angle)
        .def_rw("attenuation", &Light::attenuation)
        .def_rw("shadows", &Light::shadows)
        .def_rw("name", &Light::name)
        .def_prop_ro("intensity_rgb", [](const Light& l) {
            return vec3_to_numpy(l.intensity_rgb());
        })
        .def("sample", [](const Light& l, nb::object point) {
            return l.sample(numpy_to_vec3(point));
        }, nb::arg("point"), "Evaluate light contribution at a surface point")
        .def("to_uniform_dict", [](const Light& l) {
            nb::dict d;
            d["type"] = light_type_to_string(l.type);
            nb::list color_list;
            color_list.append(l.color.x);
            color_list.append(l.color.y);
            color_list.append(l.color.z);
            d["color"] = color_list;
            d["intensity"] = l.intensity;
            Vec3 dir = l.direction.normalized();
            nb::list dir_list;
            dir_list.append(dir.x);
            dir_list.append(dir.y);
            dir_list.append(dir.z);
            d["direction"] = dir_list;
            nb::list pos_list;
            pos_list.append(l.position.x);
            pos_list.append(l.position.y);
            pos_list.append(l.position.z);
            d["position"] = pos_list;
            d["range"] = l.range.has_value() ? nb::cast(l.range.value()) : nb::none();
            d["inner_angle"] = l.inner_angle;
            d["outer_angle"] = l.outer_angle;
            nb::dict atten;
            atten["constant"] = l.attenuation.constant;
            atten["linear"] = l.attenuation.linear;
            atten["quadratic"] = l.attenuation.quadratic;
            d["attenuation"] = atten;
            nb::dict shad;
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
