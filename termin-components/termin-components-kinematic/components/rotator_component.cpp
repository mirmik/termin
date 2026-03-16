#include <components/rotator_component.hpp>
#include <termin/geom/quat.hpp>
#include "tc_inspect_cpp.hpp"
#include <cmath>

#ifndef M_PI
#define M_PI 3.14159265358979323846
#endif

namespace termin {

RotatorComponent::RotatorComponent() {
    link_type_entry("RotatorComponent");
    axis_z = 1.0;  // Default: Z axis
}

void RotatorComponent::apply() {
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

    Quat final_rotation = base * coord_rot;

    // Set rotation
    double xyzw[4] = {final_rotation.x, final_rotation.y, final_rotation.z, final_rotation.w};
    ent.set_local_rotation(xyzw);

    // Position and scale from base (rotator doesn't modify them)
    double xyz[3] = {base_position.x, base_position.y, base_position.z};
    ent.set_local_position(xyz);

    double scl[3] = {base_scale.x, base_scale.y, base_scale.z};
    ent.set_local_scale(scl);
}

void RotatorComponent::capture_base() {
    double pos[3], rot[4], scl[3];
    if (!read_entity_transform(pos, rot, scl)) return;

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

// axis_scale preset (enum, not serialized)
static struct _RotatorAxisScaleRegistrar {
    _RotatorAxisScaleRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "RotatorComponent";
        info.path = "axis_scale";
        info.label = "Axis Scale";
        info.kind = "enum";
        info.is_serializable = false;

        // π/180 ≈ 0.01745329 — coordinate in degrees
        // 1.0 — coordinate in radians
        std::string deg_str = std::to_string(M_PI / 180.0);
        info.choices = {
            {deg_str, "deg"},
            {"1.0",   "rad"},
        };

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            double len = std::sqrt(c->axis_x*c->axis_x + c->axis_y*c->axis_y + c->axis_z*c->axis_z);
            double deg_scale = M_PI / 180.0;
            if (std::abs(len - deg_scale) < 1e-6) return tc_value_string(std::to_string(deg_scale).c_str());
            if (std::abs(len - 1.0) < 1e-6) return tc_value_string("1.0");
            return tc_value_string(std::to_string(deg_scale).c_str());
        };

        info.setter = [](void* obj, tc_value value, void*) {
            if (value.type != TC_VALUE_STRING || !value.data.s) return;
            double new_scale = std::atof(value.data.s);
            if (new_scale < 1e-12) return;

            auto* c = static_cast<KinematicUnitComponent*>(obj);
            double len = std::sqrt(c->axis_x*c->axis_x + c->axis_y*c->axis_y + c->axis_z*c->axis_z);
            if (len < 1e-12) return;

            double factor = new_scale / len;
            c->set_axis(c->axis_x * factor, c->axis_y * factor, c->axis_z * factor);
        };

        tc::InspectRegistry::instance().add_field_with_choices("RotatorComponent", std::move(info));
    }
} _rotator_axis_scale_registrar;

} // namespace termin
