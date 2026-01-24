// tc_scene_lighting_bindings.cpp - Python bindings for tc_scene_lighting

#include <nanobind/nanobind.h>
#include <nanobind/stl/string.h>
#include <nanobind/stl/tuple.h>

#include "lighting/shadow_settings.hpp"
#include "../../core_c/include/tc_scene_lighting.h"

namespace nb = nanobind;

namespace termin {

// View class that wraps tc_scene_lighting* (non-owning)
class TcSceneLighting {
public:
    tc_scene_lighting* _ptr = nullptr;

    TcSceneLighting(tc_scene_lighting* ptr) : _ptr(ptr) {}
    TcSceneLighting(uintptr_t ptr) : _ptr(reinterpret_cast<tc_scene_lighting*>(ptr)) {}

    bool valid() const { return _ptr != nullptr; }

    // Ambient color
    std::tuple<float, float, float> ambient_color() const {
        if (!_ptr) return {1.0f, 1.0f, 1.0f};
        return {_ptr->ambient_color[0], _ptr->ambient_color[1], _ptr->ambient_color[2]};
    }

    void set_ambient_color(float r, float g, float b) {
        if (!_ptr) return;
        _ptr->ambient_color[0] = r;
        _ptr->ambient_color[1] = g;
        _ptr->ambient_color[2] = b;
    }

    // Ambient intensity
    float ambient_intensity() const {
        return _ptr ? _ptr->ambient_intensity : 0.1f;
    }

    void set_ambient_intensity(float intensity) {
        if (_ptr) _ptr->ambient_intensity = intensity;
    }

    // Shadow settings as ShadowSettings object
    ShadowSettings shadow_settings() const {
        if (!_ptr) return ShadowSettings();
        return ShadowSettings(_ptr->shadow_method, _ptr->shadow_softness, _ptr->shadow_bias);
    }

    void set_shadow_settings(const ShadowSettings& ss) {
        if (!_ptr) return;
        _ptr->shadow_method = ss.method;
        _ptr->shadow_softness = static_cast<float>(ss.softness);
        _ptr->shadow_bias = static_cast<float>(ss.bias);
    }
};

void bind_tc_scene_lighting(nb::module_& m) {
    nb::class_<TcSceneLighting>(m, "TcSceneLighting",
        "View on scene lighting properties (ambient, shadows)")
        .def(nb::init<uintptr_t>(), nb::arg("ptr"))

        .def_prop_rw("ambient_color",
            [](TcSceneLighting& self) { return self.ambient_color(); },
            [](TcSceneLighting& self, std::tuple<float, float, float> color) {
                self.set_ambient_color(std::get<0>(color), std::get<1>(color), std::get<2>(color));
            },
            "Ambient light color (r, g, b)")

        .def_prop_rw("ambient_intensity",
            &TcSceneLighting::ambient_intensity,
            &TcSceneLighting::set_ambient_intensity,
            "Ambient light intensity")

        .def_prop_rw("shadow_settings",
            &TcSceneLighting::shadow_settings,
            &TcSceneLighting::set_shadow_settings,
            "Shadow rendering settings")

        .def("valid", &TcSceneLighting::valid,
            "Check if this lighting view is valid")
        ;
}

} // namespace termin
