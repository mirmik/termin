#include "actuator_component.hpp"
#include "tc_log.hpp"
#include "tc_inspect_cpp.hpp"
#include <cmath>

namespace termin {

// Register axis field as vec3
static struct _ActuatorAxisFieldRegistrar {
    _ActuatorAxisFieldRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "ActuatorComponent";
        info.path = "axis";
        info.label = "Axis";
        info.kind = "vec3";
        info.min = -100000.0;
        info.max = 100000.0;
        info.step = 0.001;

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<ActuatorComponent*>(obj);
            tc_vec3 v = {c->axis_x, c->axis_y, c->axis_z};
            return tc_value_vec3(v);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            auto* c = static_cast<ActuatorComponent*>(obj);
            if (value.type == TC_VALUE_VEC3) {
                c->set_axis(value.data.v3.x, value.data.v3.y, value.data.v3.z);
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("ActuatorComponent", std::move(info));
    }
} _actuator_axis_registrar;

// Register coordinate field
static struct _ActuatorCoordinateFieldRegistrar {
    _ActuatorCoordinateFieldRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "ActuatorComponent";
        info.path = "coordinate";
        info.label = "Coordinate";
        info.kind = "double";
        info.min = -1000.0;
        info.max = 1000.0;
        info.step = 0.01;

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<ActuatorComponent*>(obj);
            return tc_value_double(c->coordinate);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            auto* c = static_cast<ActuatorComponent*>(obj);
            double v = 0.0;
            if (value.type == TC_VALUE_DOUBLE) v = value.data.d;
            else if (value.type == TC_VALUE_FLOAT) v = value.data.f;
            else if (value.type == TC_VALUE_INT) v = static_cast<double>(value.data.i);
            c->set_coordinate(v);
        };

        tc::InspectRegistry::instance().add_field_with_choices("ActuatorComponent", std::move(info));
    }
} _actuator_coordinate_registrar;

ActuatorComponent::ActuatorComponent() {
    link_type_entry("ActuatorComponent");
}

void ActuatorComponent::on_added() {
    CxxComponent::on_added();

    Entity ent = entity();
    if (!ent.valid()) {
        tc::Log::error("ActuatorComponent::on_added: entity is invalid");
        return;
    }

    // Store base position
    double xyz[3];
    ent.get_local_position(xyz);
    // _base_position = Vec3{xyz[0], xyz[1], xyz[2]};
}

void ActuatorComponent::set_axis(double x, double y, double z) {
    axis_x = x;
    axis_y = y;
    axis_z = z;
    _apply_movement();
}

void ActuatorComponent::set_coordinate(double value) {
    coordinate = value;
    _apply_movement();
}

Vec3 ActuatorComponent::_normalized_axis() const {
    double len = std::sqrt(axis_x*axis_x + axis_y*axis_y + axis_z*axis_z);
    if (len < 1e-9) {
        return Vec3{1.0, 0.0, 0.0};  // Default to X axis
    }
    return Vec3{axis_x / len, axis_y / len, axis_z / len};
}

void ActuatorComponent::_apply_movement() {
    Entity ent = entity();
    if (!ent.valid()) return;

    // Axis vector length serves as scale factor:
    // displacement = axis * coordinate (no normalization)
    Vec3 raw_axis{axis_x, axis_y, axis_z};
    //Vec3 new_position = _base_position + raw_axis * coordinate;
    Vec3 new_position = raw_axis * coordinate;  // Move relative to origin, not base position

    // Set position via Entity API
    double xyz[3] = {new_position.x, new_position.y, new_position.z};
    ent.set_local_position(xyz);
}

} // namespace termin
