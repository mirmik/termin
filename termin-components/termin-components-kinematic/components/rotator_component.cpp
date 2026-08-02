#include "tc_inspect_cpp.hpp"
#include <cmath>
#include <components/rotator_component.hpp>
#include <cstdlib>
#include <numbers>
#include <termin/geom/quat.hpp>

namespace termin
{

    namespace
    {

        void
        register_rotator_axis_scale_field(tc::InspectFacetBuilder& builder);

    } // namespace

    RotatorComponent::RotatorComponent()
        : KinematicUnitComponent("RotatorComponent")
    {
        axis_z = 1.0; // Default: Z axis
    }

    void RotatorComponent::register_type()
    {
        auto descriptor =
            ComponentTypeDescriptorBuilder::native<RotatorComponent>(
                "RotatorComponent",
                "termin-components-kinematic",
                "KinematicUnitComponent");
        descriptor.category("Kinematic");
        register_rotator_axis_scale_field(descriptor.inspect());
        (void)descriptor.commit();
    }

    void RotatorComponent::apply()
    {
        Entity ent = entity();
        if (!ent.valid())
            return;

        Vec3 raw_axis{axis_x, axis_y, axis_z};
        double len =
            std::sqrt(raw_axis.x * raw_axis.x + raw_axis.y * raw_axis.y +
                      raw_axis.z * raw_axis.z);
        if (len < 1e-9)
            return;

        Vec3 dir{raw_axis.x / len, raw_axis.y / len, raw_axis.z / len};
        double angle = coordinate * len;

        // local = origin * Rotation(axis, angle)
        Quat coord_rot = Quat::from_axis_angle(dir, angle);
        Quat origin{origin_rotation.x,
                    origin_rotation.y,
                    origin_rotation.z,
                    origin_rotation.w};

        Quat final_rotation = origin * coord_rot;

        // Set rotation
        double xyzw[4] = {final_rotation.x,
                          final_rotation.y,
                          final_rotation.z,
                          final_rotation.w};
        ent.set_local_rotation(xyzw);

        // Position comes from the zero-coordinate frame. Scale is not part of
        // the kinematic transform and remains untouched.
        double xyz[3] = {
            origin_position.x, origin_position.y, origin_position.z};
        ent.set_local_position(xyz);
    }

    void RotatorComponent::recalculate_origin()
    {
        double pos[3], rot[4];
        if (!read_entity_transform(pos, rot))
            return;

        // A rotator never changes its entity origin.
        origin_position = {pos[0], pos[1], pos[2]};

        // Reverse: origin_rot = current_rot * coord_rot.inverse()
        // Since current_rot = origin_rot * coord_rot
        Vec3 raw_axis{axis_x, axis_y, axis_z};
        double len =
            std::sqrt(raw_axis.x * raw_axis.x + raw_axis.y * raw_axis.y +
                      raw_axis.z * raw_axis.z);

        Quat coord_rot = Quat::identity();
        if (len > 1e-9)
        {
            Vec3 dir{raw_axis.x / len, raw_axis.y / len, raw_axis.z / len};
            coord_rot = Quat::from_axis_angle(dir, coordinate * len);
        }

        Quat current_rot{rot[0], rot[1], rot[2], rot[3]};
        Quat origin = current_rot * coord_rot.inverse();
        origin_rotation = {origin.x, origin.y, origin.z, origin.w};
    }

    namespace
    {

        void register_rotator_axis_scale_field(tc::InspectFacetBuilder& builder)
        {
            tc::InspectFieldInfo info;
            info.type_name = "RotatorComponent";
            info.path = "axis_scale";
            info.label = "Axis Scale";
            info.kind = "enum";
            info.is_serializable = false;

            // π/180 ≈ 0.01745329 — coordinate in degrees
            // 1.0 — coordinate in radians
            std::string deg_str =
                std::to_string(std::numbers::pi_v<double> / 180.0);
            info.choices = {
                {deg_str, "deg"},
                {"1.0", "rad"},
            };

            info.getter = [](void* obj) -> tc_value
            {
                auto* c = static_cast<KinematicUnitComponent*>(obj);
                double len =
                    std::sqrt(c->axis_x * c->axis_x + c->axis_y * c->axis_y +
                              c->axis_z * c->axis_z);
                double deg_scale = std::numbers::pi_v<double> / 180.0;
                if (std::abs(len - deg_scale) < 1e-6)
                    return tc_value_string(std::to_string(deg_scale).c_str());
                if (std::abs(len - 1.0) < 1e-6)
                    return tc_value_string("1.0");
                return tc_value_string(std::to_string(deg_scale).c_str());
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
