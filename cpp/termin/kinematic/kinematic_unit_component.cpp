#include "kinematic_unit_component.hpp"
#include "tc_inspect_cpp.hpp"
#include <cmath>

namespace termin {

// ============================================================================
// Inspect field registrars (inherited by all subclasses via parent chain)
// ============================================================================

// axis (vec3)
static struct _KinematicAxisRegistrar {
    _KinematicAxisRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "KinematicUnitComponent";
        info.path = "axis";
        info.label = "Axis";
        info.kind = "vec3";
        info.min = -100000.0;
        info.max = 100000.0;
        info.step = 0.001;

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            tc_vec3 v = {c->axis_x, c->axis_y, c->axis_z};
            return tc_value_vec3(v);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            if (value.type == TC_VALUE_VEC3) {
                c->set_axis(value.data.v3.x, value.data.v3.y, value.data.v3.z);
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("KinematicUnitComponent", std::move(info));
    }
} _kinematic_axis_registrar;

// coordinate (double)
static struct _KinematicCoordinateRegistrar {
    _KinematicCoordinateRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "KinematicUnitComponent";
        info.path = "coordinate";
        info.label = "Coordinate";
        info.kind = "double";
        info.min = -100000.0;
        info.max = 100000.0;
        info.step = 0.01;

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            return tc_value_double(c->coordinate);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            double v = 0.0;
            if (value.type == TC_VALUE_DOUBLE) v = value.data.d;
            else if (value.type == TC_VALUE_FLOAT) v = value.data.f;
            else if (value.type == TC_VALUE_INT) v = static_cast<double>(value.data.i);
            c->set_coordinate(v);
        };

        tc::InspectRegistry::instance().add_field_with_choices("KinematicUnitComponent", std::move(info));
    }
} _kinematic_coordinate_registrar;

// base_position (vec3)
static struct _KinematicBasePositionRegistrar {
    _KinematicBasePositionRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "KinematicUnitComponent";
        info.path = "base_position";
        info.label = "Base Position";
        info.kind = "vec3";
        info.min = -100000.0;
        info.max = 100000.0;
        info.step = 0.001;

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            return tc_value_vec3(c->base_position);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            if (value.type == TC_VALUE_VEC3) {
                c->base_position = value.data.v3;
                c->apply();
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("KinematicUnitComponent", std::move(info));
    }
} _kinematic_base_position_registrar;

// base_rotation (quat)
static struct _KinematicBaseRotationRegistrar {
    _KinematicBaseRotationRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "KinematicUnitComponent";
        info.path = "base_rotation";
        info.label = "Base Rotation";
        info.kind = "quat";

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            return tc_value_quat(c->base_rotation);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            if (value.type == TC_VALUE_QUAT) {
                c->base_rotation = value.data.q;
                c->apply();
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("KinematicUnitComponent", std::move(info));
    }
} _kinematic_base_rotation_registrar;

// base_scale (vec3)
static struct _KinematicBaseScaleRegistrar {
    _KinematicBaseScaleRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "KinematicUnitComponent";
        info.path = "base_scale";
        info.label = "Base Scale";
        info.kind = "vec3";
        info.min = -100000.0;
        info.max = 100000.0;
        info.step = 0.001;

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            return tc_value_vec3(c->base_scale);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            if (value.type == TC_VALUE_VEC3) {
                c->base_scale = value.data.v3;
                c->apply();
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("KinematicUnitComponent", std::move(info));
    }
} _kinematic_base_scale_registrar;

// capture_base (bool trigger — set true to capture)
static struct _KinematicCaptureBaseRegistrar {
    _KinematicCaptureBaseRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "KinematicUnitComponent";
        info.path = "capture_base";
        info.label = "Capture Base";
        info.kind = "bool";

        info.getter = [](void* obj) -> tc_value {
            return tc_value_bool(false);
        };

        info.setter = [](void* obj, tc_value value, tc_scene_handle) {
            if (value.type == TC_VALUE_BOOL && value.data.b) {
                auto* c = static_cast<KinematicUnitComponent*>(obj);
                c->capture_base();
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("KinematicUnitComponent", std::move(info));
    }
} _kinematic_capture_base_registrar;

// ============================================================================
// KinematicUnitComponent implementation
// ============================================================================

void KinematicUnitComponent::on_added() {
    CxxComponent::on_added();
}

void KinematicUnitComponent::set_axis(double x, double y, double z) {
    axis_x = x;
    axis_y = y;
    axis_z = z;
    apply();
}

void KinematicUnitComponent::set_coordinate(double value) {
    coordinate = value;
    apply();
}

void KinematicUnitComponent::apply() {
    // Default: no-op. Subclasses override.
}

void KinematicUnitComponent::capture_base() {
    // Default: capture current transform directly as base
    double pos[3], rot[4], scl[3];
    if (!read_entity_transform(pos, rot, scl)) return;

    base_position = {pos[0], pos[1], pos[2]};
    base_rotation = {rot[0], rot[1], rot[2], rot[3]};
    base_scale = {scl[0], scl[1], scl[2]};
}

Vec3 KinematicUnitComponent::normalized_axis(Vec3 fallback) const {
    double len = std::sqrt(axis_x*axis_x + axis_y*axis_y + axis_z*axis_z);
    if (len < 1e-9) {
        return fallback;
    }
    return Vec3{axis_x / len, axis_y / len, axis_z / len};
}

bool KinematicUnitComponent::read_entity_transform(double pos[3], double rot[4], double scl[3]) const {
    Entity ent = entity();
    if (!ent.valid()) return false;

    ent.get_local_position(pos);
    ent.get_local_rotation(rot);
    ent.get_local_scale(scl);
    return true;
}

void KinematicUnitComponent::write_base_transform(Entity& ent) const {
    double xyz[3] = {base_position.x, base_position.y, base_position.z};
    ent.set_local_position(xyz);

    double rot[4] = {base_rotation.x, base_rotation.y, base_rotation.z, base_rotation.w};
    ent.set_local_rotation(rot);

    double scl[3] = {base_scale.x, base_scale.y, base_scale.z};
    ent.set_local_scale(scl);
}

} // namespace termin
