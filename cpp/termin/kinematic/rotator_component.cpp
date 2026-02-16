#include "rotator_component.hpp"
#include "../geom/quat.hpp"
#include <cmath>

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

} // namespace termin
