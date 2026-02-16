#include "actuator_component.hpp"
#include "../geom/quat.hpp"
#include <cmath>

namespace termin {

ActuatorComponent::ActuatorComponent() {
    link_type_entry("ActuatorComponent");
    axis_x = 1.0;  // Default: X axis
}

void ActuatorComponent::apply() {
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

    // Set position
    double xyz[3] = {new_position.x, new_position.y, new_position.z};
    ent.set_local_position(xyz);

    // Rotation and scale from base (actuator doesn't modify them)
    double rot[4] = {br.x, br.y, br.z, br.w};
    ent.set_local_rotation(rot);

    double scl[3] = {bs.x, bs.y, bs.z};
    ent.set_local_scale(scl);
}

void ActuatorComponent::capture_base() {
    double pos[3], rot[4], scl[3];
    if (!read_entity_transform(pos, rot, scl)) return;

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
