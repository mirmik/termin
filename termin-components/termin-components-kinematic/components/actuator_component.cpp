#include <components/actuator_component.hpp>
#include <termin/geom/quat.hpp>
#include "tc_inspect_cpp.hpp"
#include <tcbase/tc_log.hpp>
#include <cmath>

namespace termin {

void ActuatorComponent::register_type() {
    KinematicUnitComponent::register_type();

    auto& component_registry = ComponentRegistry::instance();
    if (!component_registry.has("ActuatorComponent")) {
        component_registry.register_native(
            "ActuatorComponent",
            &CxxComponentFactoryData<ActuatorComponent>::create,
            nullptr,
            "KinematicUnitComponent"
        );
    }

    tc::InspectRegistry::instance().set_type_parent(
        "ActuatorComponent", "KinematicUnitComponent");
}

ActuatorComponent::ActuatorComponent() {
    link_type_entry("ActuatorComponent");
    axis_x = 1.0;  // Default: X axis
}

void ActuatorComponent::apply() {
    Entity ent = entity();
    if (!ent.valid()) {
        tc::Log::warn("ActuatorComponent::apply() - entity not valid");
        return;
    }

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

// axis_scale preset (enum, not serialized)
static struct _ActuatorAxisScaleRegistrar {
    _ActuatorAxisScaleRegistrar() {
        tc::InspectFieldInfo info;
        info.type_name = "ActuatorComponent";
        info.path = "axis_scale";
        info.label = "Axis Scale";
        info.kind = "enum";
        info.is_serializable = false;
        info.choices = {
            {"1.0",   "m (1.0)"},
            {"0.01",  "cm (0.01)"},
            {"0.001", "mm (0.001)"},
        };

        info.getter = [](void* obj) -> tc_value {
            auto* c = static_cast<KinematicUnitComponent*>(obj);
            double len = std::sqrt(c->axis_x*c->axis_x + c->axis_y*c->axis_y + c->axis_z*c->axis_z);
            // Return closest preset as string
            if (std::abs(len - 1.0) < 1e-6) return tc_value_string("1.0");
            if (std::abs(len - 0.01) < 1e-6) return tc_value_string("0.01");
            if (std::abs(len - 0.001) < 1e-6) return tc_value_string("0.001");
            return tc_value_string("1.0");
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

        tc::InspectRegistry::instance().add_field_with_choices("ActuatorComponent", std::move(info));
    }
} _actuator_axis_scale_registrar;

} // namespace termin
