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

// Register base_position field (vec3)
static struct _RotatorBasePositionRegistrar {
    _RotatorBasePositionRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "RotatorComponent";
        info.path = "base_position";
        info.label = "Base Position";
        info.kind = "vec3";
        info.min = -100000.0;
        info.max = 100000.0;
        info.step = 0.001;

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<RotatorComponent*>(obj);
            return tc_value_vec3(c->base_position);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            auto* c = static_cast<RotatorComponent*>(obj);
            if (value.type == TC_VALUE_VEC3) {
                c->base_position = value.data.v3;
                c->_apply_rotation();
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("RotatorComponent", std::move(info));
    }
} _rotator_base_position_registrar;

// Register base_rotation field (quat)
static struct _RotatorBaseRotationRegistrar {
    _RotatorBaseRotationRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "RotatorComponent";
        info.path = "base_rotation";
        info.label = "Base Rotation";
        info.kind = "quat";

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<RotatorComponent*>(obj);
            return tc_value_quat(c->base_rotation);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            auto* c = static_cast<RotatorComponent*>(obj);
            if (value.type == TC_VALUE_QUAT) {
                c->base_rotation = value.data.q;
                c->_apply_rotation();
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("RotatorComponent", std::move(info));
    }
} _rotator_base_rotation_registrar;

// Register base_scale field (vec3)
static struct _RotatorBaseScaleRegistrar {
    _RotatorBaseScaleRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "RotatorComponent";
        info.path = "base_scale";
        info.label = "Base Scale";
        info.kind = "vec3";
        info.min = -100000.0;
        info.max = 100000.0;
        info.step = 0.001;

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<RotatorComponent*>(obj);
            return tc_value_vec3(c->base_scale);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            auto* c = static_cast<RotatorComponent*>(obj);
            if (value.type == TC_VALUE_VEC3) {
                c->base_scale = value.data.v3;
                c->_apply_rotation();
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("RotatorComponent", std::move(info));
    }
} _rotator_base_scale_registrar;

// Register capture_base trigger (bool: set true to capture)
static struct _RotatorCaptureBaseRegistrar {
    _RotatorCaptureBaseRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "RotatorComponent";
        info.path = "capture_base";
        info.label = "Capture Base";
        info.kind = "bool";

        info.getter = [](void* obj) -> tc_value {
            return tc_value_bool(false);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            if (value.type == TC_VALUE_BOOL && value.data.b) {
                auto* c = static_cast<RotatorComponent*>(obj);
                c->capture_base();
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("RotatorComponent", std::move(info));
    }
} _rotator_capture_base_registrar;

RotatorComponent::RotatorComponent() {
    link_type_entry("RotatorComponent");
}

void RotatorComponent::on_added() {
    CxxComponent::on_added();
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

    Vec3 dir{raw_axis.x / len, raw_axis.y / len, raw_axis.z / len};
    double angle = coordinate * len;

    // local = base * Rotation(axis, angle)
    Quat coord_rot = Quat::from_axis_angle(dir, angle);
    Quat base{base_rotation.x, base_rotation.y, base_rotation.z, base_rotation.w};
    Vec3 bp{base_position.x, base_position.y, base_position.z};
    Vec3 bs{base_scale.x, base_scale.y, base_scale.z};

    Quat final_rotation = base * coord_rot;

    // Set full local transform
    double xyzw[4] = {final_rotation.x, final_rotation.y, final_rotation.z, final_rotation.w};
    ent.set_local_rotation(xyzw);

    double xyz[3] = {bp.x, bp.y, bp.z};
    ent.set_local_position(xyz);

    double scl[3] = {bs.x, bs.y, bs.z};
    ent.set_local_scale(scl);
}

void RotatorComponent::capture_base() {
    Entity ent = entity();
    if (!ent.valid()) return;

    double pos[3], rot[4], scl[3];
    ent.get_local_position(pos);
    ent.get_local_rotation(rot);
    ent.get_local_scale(scl);

    // base_position = current_pos, base_scale = current_scale
    base_position = {pos[0], pos[1], pos[2]};
    base_scale = {scl[0], scl[1], scl[2]};

    // Reverse: base_rot = current_rot * coord_rot.inverse()
    // Since current_rot = base_rot * coord_rot
    Vec3 raw_axis{axis_x, axis_y, axis_z};
    double len = std::sqrt(raw_axis.x*raw_axis.x + raw_axis.y*raw_axis.y + raw_axis.z*raw_axis.z);

    Quat coord_rot = Quat::identity();
    if (len > 1e-9) {
        Vec3 dir{raw_axis.x / len, raw_axis.y / len, raw_axis.z / len};
        coord_rot = Quat::from_axis_angle(dir, coordinate * len);
    }

    Quat current_rot{rot[0], rot[1], rot[2], rot[3]};
    Quat base = current_rot * coord_rot.inverse();
    base_rotation = {base.x, base.y, base.z, base.w};
}

} // namespace termin
