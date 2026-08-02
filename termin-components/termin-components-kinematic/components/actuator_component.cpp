#include "tc_inspect_cpp.hpp"
#include <cmath>
#include <components/actuator_component.hpp>
#include <cstdlib>
#include <tcbase/tc_log.hpp>
#include <termin/geom/quat.hpp>

namespace termin
{

    namespace
    {

        void
        register_actuator_axis_scale_field(tc::InspectFacetBuilder& builder);

    } // namespace

    void ActuatorComponent::register_type()
    {
        auto descriptor =
            ComponentTypeDescriptorBuilder::native<ActuatorComponent>(
                "ActuatorComponent",
                "termin-components-kinematic",
                "KinematicUnitComponent");
        descriptor.category("Kinematic");
        register_actuator_axis_scale_field(descriptor.inspect());
        (void)descriptor.commit();
    }

    ActuatorComponent::ActuatorComponent()
        : KinematicUnitComponent("ActuatorComponent")
    {
        axis_x = 1.0; // Default: X axis
    }

    void ActuatorComponent::apply()
    {
        Entity ent = entity();
        if (!ent.valid())
        {
            tc::Log::warn("ActuatorComponent::apply() - entity not valid");
            return;
        }

        // local = origin * Translation(axis * coordinate)
        Vec3 raw_axis{axis_x, axis_y, axis_z};
        Vec3 origin_position_value{
            origin_position.x, origin_position.y, origin_position.z};
        Quat origin_rotation_value{origin_rotation.x,
                                   origin_rotation.y,
                                   origin_rotation.z,
                                   origin_rotation.w};

        // offset.position = axis * coordinate
        Vec3 offset_pos = raw_axis * coordinate;
        Vec3 new_position =
            origin_position_value + origin_rotation_value.rotate(offset_pos);

        // Set position
        double xyz[3] = {new_position.x, new_position.y, new_position.z};
        ent.set_local_position(xyz);

        // Rotation comes from the zero-coordinate frame. Scale remains
        // untouched.
        double rot[4] = {origin_rotation_value.x,
                         origin_rotation_value.y,
                         origin_rotation_value.z,
                         origin_rotation_value.w};
        ent.set_local_rotation(rot);
    }

    void ActuatorComponent::recalculate_origin()
    {
        double pos[3], rot[4];
        if (!read_entity_transform(pos, rot))
            return;

        // An actuator never changes its entity rotation.
        origin_rotation = {rot[0], rot[1], rot[2], rot[3]};

        // Reverse: origin_pos = current_pos - origin_rot.rotate(axis * coord)
        Quat origin_rotation_value{rot[0], rot[1], rot[2], rot[3]};
        Vec3 raw_axis{axis_x, axis_y, axis_z};
        Vec3 offset_pos = raw_axis * coordinate;
        Vec3 rotated = origin_rotation_value.rotate(offset_pos);

        origin_position = {
            pos[0] - rotated.x, pos[1] - rotated.y, pos[2] - rotated.z};
    }

    namespace
    {

        void
        register_actuator_axis_scale_field(tc::InspectFacetBuilder& builder)
        {
            tc::InspectFieldInfo info;
            info.type_name = "ActuatorComponent";
            info.path = "axis_scale";
            info.label = "Axis Scale";
            info.kind = "enum";
            info.is_serializable = false;
            info.choices = {
                {"1.0", "m (1.0)"},
                {"0.01", "cm (0.01)"},
                {"0.001", "mm (0.001)"},
            };

            info.getter = [](void* obj) -> tc_value
            {
                auto* c = static_cast<KinematicUnitComponent*>(obj);
                double len =
                    std::sqrt(c->axis_x * c->axis_x + c->axis_y * c->axis_y +
                              c->axis_z * c->axis_z);
                // Return closest preset as string
                if (std::abs(len - 1.0) < 1e-6)
                    return tc_value_string("1.0");
                if (std::abs(len - 0.01) < 1e-6)
                    return tc_value_string("0.01");
                if (std::abs(len - 0.001) < 1e-6)
                    return tc_value_string("0.001");
                return tc_value_string("1.0");
            };

            info.setter = [](void* obj, tc_value value, void*) -> bool
            {
                if (value.type != TC_VALUE_STRING || !value.data.s)
                    return false;
                double new_scale = std::atof(value.data.s);
                if (new_scale < 1e-12)
                    return false;

                auto* c = static_cast<KinematicUnitComponent*>(obj);
                double len =
                    std::sqrt(c->axis_x * c->axis_x + c->axis_y * c->axis_y +
                              c->axis_z * c->axis_z);
                if (len < 1e-12)
                    return false;

                double factor = new_scale / len;
                c->set_axis(
                    c->axis_x * factor, c->axis_y * factor, c->axis_z * factor);
                return true;
            };

            (void)builder.add_field(std::move(info));
        }

    } // namespace

} // namespace termin
