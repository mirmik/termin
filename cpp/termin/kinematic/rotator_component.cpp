#include "rotator_component.hpp"
#include "tc_log.hpp"
#include "tc_inspect_cpp.hpp"
#include <cmath>

namespace termin {

// Register axis field as vec3
static struct _RotatorAxisFieldRegistrar {
    _RotatorAxisFieldRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "RotatorComponent";
        info.path = "axis";
        info.label = "Axis";
        info.kind = "vec3";
        info.min = -100000.0;
        info.max = 100000.0;
        info.step = 0.001;

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<RotatorComponent*>(obj);
            tc_vec3 v = {c->axis_x, c->axis_y, c->axis_z};
            return tc_value_vec3(v);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            auto* c = static_cast<RotatorComponent*>(obj);
            if (value.type == TC_VALUE_VEC3) {
                c->set_axis(value.data.v3.x, value.data.v3.y, value.data.v3.z);
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("RotatorComponent", std::move(info));
    }
} _rotator_axis_registrar;

// Register coordinate field
static struct _RotatorCoordinateFieldRegistrar {
    _RotatorCoordinateFieldRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "RotatorComponent";
        info.path = "coordinate";
        info.label = "Coordinate";
        info.kind = "double";
        info.min = -100.0;
        info.max = 100.0;
        info.step = 0.01;

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<RotatorComponent*>(obj);
            return tc_value_double(c->coordinate);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            auto* c = static_cast<RotatorComponent*>(obj);
            double v = 0.0;
            if (value.type == TC_VALUE_DOUBLE) v = value.data.d;
            else if (value.type == TC_VALUE_FLOAT) v = value.data.f;
            else if (value.type == TC_VALUE_INT) v = static_cast<double>(value.data.i);
            c->set_coordinate(v);
        };

        tc::InspectRegistry::instance().add_field_with_choices("RotatorComponent", std::move(info));
    }
} _rotator_coordinate_registrar;

RotatorComponent::RotatorComponent() {
    link_type_entry("RotatorComponent");
}

void RotatorComponent::on_added() {
    CxxComponent::on_added();

    Entity ent = entity();
    if (!ent.valid()) {
        tc::Log::error("RotatorComponent::on_added: entity is invalid");
        return;
    }

    // Store base rotation
    double xyzw[4];
    ent.get_local_rotation(xyzw);
    _base_rotation = Quat(xyzw[0], xyzw[1], xyzw[2], xyzw[3]);
}

void RotatorComponent::set_axis(double x, double y, double z) {
    axis_x = x;
    axis_y = y;
    axis_z = z;
    _apply_rotation();
}

void RotatorComponent::set_coordinate(double value) {
    coordinate = value;
    _apply_rotation();
}

Vec3 RotatorComponent::_normalized_axis() const {
    double len = std::sqrt(axis_x*axis_x + axis_y*axis_y + axis_z*axis_z);
    if (len < 1e-9) {
        return Vec3{0.0, 0.0, 1.0};  // Default to Z axis
    }
    return Vec3{axis_x / len, axis_y / len, axis_z / len};
}

void RotatorComponent::_apply_rotation() {
    Entity ent = entity();
    if (!ent.valid()) return;

    Vec3 raw_axis{axis_x, axis_y, axis_z};
    double len = std::sqrt(raw_axis.x*raw_axis.x + raw_axis.y*raw_axis.y + raw_axis.z*raw_axis.z);
    if (len < 1e-9) return;

    // Normalize axis for quaternion, but use axis length as scale factor for coordinate
    Vec3 dir{raw_axis.x / len, raw_axis.y / len, raw_axis.z / len};
    double angle = coordinate * len;

    // Create rotation quaternion from axis-angle
    Quat rotation = Quat::from_axis_angle(dir, angle);

    // Apply: final = rotation * base
    Quat final_rotation = rotation * _base_rotation;

    // Set rotation via Entity API
    double xyzw[4] = {final_rotation.x, final_rotation.y, final_rotation.z, final_rotation.w};
    ent.set_local_rotation(xyzw);
}

} // namespace termin
