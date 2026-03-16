#include <components/kinematic_unit_component.hpp>
#include "tc_inspect_cpp.hpp"
#include <termin/geom/pose3.hpp>
#include <cmath>

namespace termin {

static double degrees(double rad) { return rad * (180.0 / M_PI); }
static double radians(double deg) { return deg * (M_PI / 180.0); }

static bool tc_value_to_vec3(const tc_value& v, tc_vec3& out) {
    if (v.type == TC_VALUE_LIST && v.data.list.count >= 3) {
        out.x = tc::tc_value_to_double(&v.data.list.items[0]);
        out.y = tc::tc_value_to_double(&v.data.list.items[1]);
        out.z = tc::tc_value_to_double(&v.data.list.items[2]);
        return true;
    }
    return false;
}

static bool tc_value_to_quat(const tc_value& v, tc_quat& out) {
    if (v.type == TC_VALUE_LIST && v.data.list.count >= 4) {
        out.x = tc::tc_value_to_double(&v.data.list.items[0]);
        out.y = tc::tc_value_to_double(&v.data.list.items[1]);
        out.z = tc::tc_value_to_double(&v.data.list.items[2]);
        out.w = tc::tc_value_to_double(&v.data.list.items[3]);
        return true;
    }
    return false;
}

void KinematicUnitComponent::register_type() {
    auto& component_registry = ComponentRegistry::instance();
    if (!component_registry.has("KinematicUnitComponent")) {
        component_registry.register_abstract("KinematicUnitComponent", "Component");
    }

    auto& inspect = tc::InspectRegistry::instance();
    inspect.set_type_parent("KinematicUnitComponent", "Component");

    if (!inspect.find_field("KinematicUnitComponent", "axis")) {
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
            tc_value list = tc_value_list_new();
            tc_value_list_push(&list, tc_value_double(c->axis_x));
            tc_value_list_push(&list, tc_value_double(c->axis_y));
            tc_value_list_push(&list, tc_value_double(c->axis_z));
            return list;
        };
        info.setter = [](void* obj, tc_value value, void*) {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            tc_vec3 v;
            if (tc_value_to_vec3(value, v)) {
                c->set_axis(v.x, v.y, v.z);
            }
        };
        inspect.add_field_with_choices("KinematicUnitComponent", std::move(info));
    }

    if (!inspect.find_field("KinematicUnitComponent", "coordinate")) {
        tc::InspectFieldInfo info;
        info.type_name = "KinematicUnitComponent";
        info.path = "coordinate";
        info.label = "Coordinate";
        info.kind = "interval_slider";
        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            tc_value list = tc_value_list_new();
            tc_value_list_push(&list, tc_value_double(c->coordinate));
            tc_value_list_push(&list, tc_value_double(c->min_coordinate));
            tc_value_list_push(&list, tc_value_double(c->max_coordinate));
            return list;
        };
        info.setter = [](void* obj, tc_value value, void*) {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            if (value.type == TC_VALUE_LIST && value.data.list.count >= 3) {
                c->min_coordinate = tc::tc_value_to_double(&value.data.list.items[1]);
                c->max_coordinate = tc::tc_value_to_double(&value.data.list.items[2]);
                c->set_coordinate(tc::tc_value_to_double(&value.data.list.items[0]));
            } else {
                // Backward compat: plain scalar (e.g. from rfmeas scenes)
                double v = 0.0;
                if (value.type == TC_VALUE_DOUBLE) v = value.data.d;
                else if (value.type == TC_VALUE_FLOAT) v = value.data.f;
                else if (value.type == TC_VALUE_INT) v = static_cast<double>(value.data.i);
                c->set_coordinate(v);
            }
        };
        inspect.add_field_with_choices("KinematicUnitComponent", std::move(info));
    }

    if (!inspect.find_field("KinematicUnitComponent", "base_position")) {
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
            tc_value list = tc_value_list_new();
            tc_value_list_push(&list, tc_value_double(c->base_position.x));
            tc_value_list_push(&list, tc_value_double(c->base_position.y));
            tc_value_list_push(&list, tc_value_double(c->base_position.z));
            return list;
        };
        info.setter = [](void* obj, tc_value value, void*) {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            tc_vec3 v;
            if (tc_value_to_vec3(value, v)) {
                c->base_position = v;
                c->apply();
            }
        };
        inspect.add_field_with_choices("KinematicUnitComponent", std::move(info));
    }

    if (!inspect.find_field("KinematicUnitComponent", "base_rotation")) {
        tc::InspectFieldInfo info;
        info.type_name = "KinematicUnitComponent";
        info.path = "base_rotation";
        info.label = "Base Rotation";
        info.kind = "vec3";
        info.min = -360.0;
        info.max = 360.0;
        info.step = 0.1;
        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            Quat q{c->base_rotation.x, c->base_rotation.y, c->base_rotation.z, c->base_rotation.w};
            Pose3 p{q, Vec3::zero()};
            Vec3 euler = p.to_euler();
            tc_value list = tc_value_list_new();
            tc_value_list_push(&list, tc_value_double(degrees(euler.x)));
            tc_value_list_push(&list, tc_value_double(degrees(euler.y)));
            tc_value_list_push(&list, tc_value_double(degrees(euler.z)));
            return list;
        };
        info.setter = [](void* obj, tc_value value, void*) {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            tc_vec3 v;
            if (tc_value_to_vec3(value, v)) {
                Pose3 p = Pose3::from_euler(radians(v.x), radians(v.y), radians(v.z));
                c->base_rotation = {p.ang.x, p.ang.y, p.ang.z, p.ang.w};
                c->apply();
            }
        };
        inspect.add_field_with_choices("KinematicUnitComponent", std::move(info));
    }

    if (!inspect.find_field("KinematicUnitComponent", "base_scale")) {
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
            tc_value list = tc_value_list_new();
            tc_value_list_push(&list, tc_value_double(c->base_scale.x));
            tc_value_list_push(&list, tc_value_double(c->base_scale.y));
            tc_value_list_push(&list, tc_value_double(c->base_scale.z));
            return list;
        };
        info.setter = [](void* obj, tc_value value, void*) {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            tc_vec3 v;
            if (tc_value_to_vec3(value, v)) {
                c->base_scale = v;
                c->apply();
            }
        };
        inspect.add_field_with_choices("KinematicUnitComponent", std::move(info));
    }

    if (!inspect.find_field("KinematicUnitComponent", "capture_base")) {
        tc::InspectFieldInfo info;
        info.type_name = "KinematicUnitComponent";
        info.path = "capture_base";
        info.label = "Capture Base";
        info.kind = "bool";
        info.getter = [](void*) -> tc_value {
            return tc_value_bool(false);
        };
        info.setter = [](void* obj, tc_value value, void*) {
            if (value.type == TC_VALUE_BOOL && value.data.b) {
                auto* c = static_cast<KinematicUnitComponent*>(obj);
                c->capture_base();
            }
        };
        inspect.add_field_with_choices("KinematicUnitComponent", std::move(info));
    }
}

// Inspect field registrars (inherited by all subclasses via parent chain)

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
            tc_value list = tc_value_list_new();
            tc_value_list_push(&list, tc_value_double(c->axis_x));
            tc_value_list_push(&list, tc_value_double(c->axis_y));
            tc_value_list_push(&list, tc_value_double(c->axis_z));
            return list;
        };

        info.setter = [](void* obj, tc_value value, void*) {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            tc_vec3 v;
            if (tc_value_to_vec3(value, v)) {
                c->set_axis(v.x, v.y, v.z);
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("KinematicUnitComponent", std::move(info));
    }
} _kinematic_axis_registrar;

// coordinate (interval_slider: [value, min, max])
static struct _KinematicCoordinateRegistrar {
    _KinematicCoordinateRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "KinematicUnitComponent";
        info.path = "coordinate";
        info.label = "Coordinate";
        info.kind = "interval_slider";

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            tc_value list = tc_value_list_new();
            tc_value_list_push(&list, tc_value_double(c->coordinate));
            tc_value_list_push(&list, tc_value_double(c->min_coordinate));
            tc_value_list_push(&list, tc_value_double(c->max_coordinate));
            return list;
        };

        info.setter = [](void* obj, tc_value value, void*) {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            if (value.type == TC_VALUE_LIST && value.data.list.count >= 3) {
                c->min_coordinate = tc::tc_value_to_double(&value.data.list.items[1]);
                c->max_coordinate = tc::tc_value_to_double(&value.data.list.items[2]);
                c->set_coordinate(tc::tc_value_to_double(&value.data.list.items[0]));
            } else {
                double v = 0.0;
                if (value.type == TC_VALUE_DOUBLE) v = value.data.d;
                else if (value.type == TC_VALUE_FLOAT) v = value.data.f;
                else if (value.type == TC_VALUE_INT) v = static_cast<double>(value.data.i);
                c->set_coordinate(v);
            }
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
            tc_value list = tc_value_list_new();
            tc_value_list_push(&list, tc_value_double(c->base_position.x));
            tc_value_list_push(&list, tc_value_double(c->base_position.y));
            tc_value_list_push(&list, tc_value_double(c->base_position.z));
            return list;
        };

        info.setter = [](void* obj, tc_value value, void*) {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            tc_vec3 v;
            if (tc_value_to_vec3(value, v)) {
                c->base_position = v;
                c->apply();
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("KinematicUnitComponent", std::move(info));
    }
} _kinematic_base_position_registrar;

// base_rotation (displayed as euler degrees)
static struct _KinematicBaseRotationRegistrar {
    _KinematicBaseRotationRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "KinematicUnitComponent";
        info.path = "base_rotation";
        info.label = "Base Rotation";
        info.kind = "vec3";
        info.min = -360.0;
        info.max = 360.0;
        info.step = 0.1;

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            Quat q{c->base_rotation.x, c->base_rotation.y, c->base_rotation.z, c->base_rotation.w};
            Pose3 p{q, Vec3::zero()};
            Vec3 euler = p.to_euler();
            tc_value list = tc_value_list_new();
            tc_value_list_push(&list, tc_value_double(degrees(euler.x)));
            tc_value_list_push(&list, tc_value_double(degrees(euler.y)));
            tc_value_list_push(&list, tc_value_double(degrees(euler.z)));
            return list;
        };

        info.setter = [](void* obj, tc_value value, void*) {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            tc_vec3 v;
            if (tc_value_to_vec3(value, v)) {
                Pose3 p = Pose3::from_euler(radians(v.x), radians(v.y), radians(v.z));
                c->base_rotation = {p.ang.x, p.ang.y, p.ang.z, p.ang.w};
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
            tc_value list = tc_value_list_new();
            tc_value_list_push(&list, tc_value_double(c->base_scale.x));
            tc_value_list_push(&list, tc_value_double(c->base_scale.y));
            tc_value_list_push(&list, tc_value_double(c->base_scale.z));
            return list;
        };

        info.setter = [](void* obj, tc_value value, void*) {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            tc_vec3 v;
            if (tc_value_to_vec3(value, v)) {
                c->base_scale = v;
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

        info.setter = [](void* obj, tc_value value, void*) {
            if (value.type == TC_VALUE_BOOL && value.data.b) {
                auto* c = static_cast<KinematicUnitComponent*>(obj);
                c->capture_base();
            }
        };

        tc::InspectRegistry::instance().add_field_with_choices("KinematicUnitComponent", std::move(info));
    }
} _kinematic_capture_base_registrar;

// KinematicUnitComponent implementation

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
