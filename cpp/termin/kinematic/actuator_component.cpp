#include "actuator_component.hpp"
#include "tc_log.hpp"
#include "tc_inspect_cpp.hpp"
#include "../geom/quat.hpp"
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

// Register base_position field (vec3)
static struct _ActuatorBasePositionRegistrar {
    _ActuatorBasePositionRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "ActuatorComponent";
        info.path = "base_position";
        info.label = "Base Position";
        info.kind = "vec3";
        info.min = -100000.0;
        info.max = 100000.0;
        info.step = 0.001;

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<ActuatorComponent*>(obj);
            return tc_value_vec3(c->base_position);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            auto* c = static_cast<ActuatorComponent*>(obj);
            if (value.type == TC_VALUE_VEC3) {
                c->base_position = value.data.v3;
                c->_apply_movement();
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("ActuatorComponent", std::move(info));
    }
} _actuator_base_position_registrar;

// Register base_rotation field (quat)
static struct _ActuatorBaseRotationRegistrar {
    _ActuatorBaseRotationRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "ActuatorComponent";
        info.path = "base_rotation";
        info.label = "Base Rotation";
        info.kind = "quat";

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<ActuatorComponent*>(obj);
            return tc_value_quat(c->base_rotation);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            auto* c = static_cast<ActuatorComponent*>(obj);
            if (value.type == TC_VALUE_QUAT) {
                c->base_rotation = value.data.q;
                c->_apply_movement();
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("ActuatorComponent", std::move(info));
    }
} _actuator_base_rotation_registrar;

// Register base_scale field (vec3)
static struct _ActuatorBaseScaleRegistrar {
    _ActuatorBaseScaleRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "ActuatorComponent";
        info.path = "base_scale";
        info.label = "Base Scale";
        info.kind = "vec3";
        info.min = -100000.0;
        info.max = 100000.0;
        info.step = 0.001;

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<ActuatorComponent*>(obj);
            return tc_value_vec3(c->base_scale);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            auto* c = static_cast<ActuatorComponent*>(obj);
            if (value.type == TC_VALUE_VEC3) {
                c->base_scale = value.data.v3;
                c->_apply_movement();
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("ActuatorComponent", std::move(info));
    }
} _actuator_base_scale_registrar;

// Register capture_base trigger (bool: set true to capture)
static struct _ActuatorCaptureBaseRegistrar {
    _ActuatorCaptureBaseRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "ActuatorComponent";
        info.path = "capture_base";
        info.label = "Capture Base";
        info.kind = "bool";

        info.getter = [](void* obj) -> tc_value {
            return tc_value_bool(false);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            if (value.type == TC_VALUE_BOOL && value.data.b) {
                auto* c = static_cast<ActuatorComponent*>(obj);
                c->capture_base();
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("ActuatorComponent", std::move(info));
    }
} _actuator_capture_base_registrar;

ActuatorComponent::ActuatorComponent() {
    link_type_entry("ActuatorComponent");
}

void ActuatorComponent::on_added() {
    CxxComponent::on_added();
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

    // local = base * Translation(axis * coordinate)
    Vec3 raw_axis{axis_x, axis_y, axis_z};
    Vec3 bp{base_position.x, base_position.y, base_position.z};
    Quat br{base_rotation.x, base_rotation.y, base_rotation.z, base_rotation.w};
    Vec3 bs{base_scale.x, base_scale.y, base_scale.z};

    // offset.position = axis * coordinate
    Vec3 offset_pos = raw_axis * coordinate;
    // base_scale ⊙ offset_pos (component-wise)
    Vec3 scaled{bs.x * offset_pos.x, bs.y * offset_pos.y, bs.z * offset_pos.z};
    Vec3 new_position = bp + br.rotate(scaled);

    // Set full local transform
    double xyz[3] = {new_position.x, new_position.y, new_position.z};
    ent.set_local_position(xyz);

    double rot[4] = {br.x, br.y, br.z, br.w};
    ent.set_local_rotation(rot);

    double scl[3] = {bs.x, bs.y, bs.z};
    ent.set_local_scale(scl);
}

void ActuatorComponent::capture_base() {
    Entity ent = entity();
    if (!ent.valid()) return;

    double pos[3], rot[4], scl[3];
    ent.get_local_position(pos);
    ent.get_local_rotation(rot);
    ent.get_local_scale(scl);

    // base_rotation = current_rot, base_scale = current_scale
    base_rotation = {rot[0], rot[1], rot[2], rot[3]};
    base_scale = {scl[0], scl[1], scl[2]};

    // Reverse: base_pos = current_pos - base_rot.rotate(base_scale ⊙ (axis * coord))
    Quat br{rot[0], rot[1], rot[2], rot[3]};
    Vec3 raw_axis{axis_x, axis_y, axis_z};
    Vec3 offset_pos = raw_axis * coordinate;
    Vec3 scaled{scl[0] * offset_pos.x, scl[1] * offset_pos.y, scl[2] * offset_pos.z};
    Vec3 rotated = br.rotate(scaled);

    base_position = {pos[0] - rotated.x, pos[1] - rotated.y, pos[2] - rotated.z};
}

} // namespace termin
