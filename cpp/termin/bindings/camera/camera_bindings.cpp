// camera_bindings.cpp - Python bindings for CameraComponent
// DISABLED - Using Python implementation in termin/visualization/core/camera.py

#include <nanobind/nanobind.h>

namespace nb = nanobind;

namespace termin {

// CameraComponent bindings are disabled - using Python implementation
void bind_camera_component(nb::module_& m) {
    // No-op: CameraComponent is now implemented in Python
    (void)m;
}

} // namespace termin
