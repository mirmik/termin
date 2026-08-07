#include "tc_inspect_cpp.hpp"
#include <cmath>
#include <components/rotator_component.hpp>
#include <cstdlib>
#include <numbers>
#include <termin/geom/quat.hpp>

namespace termin {

    namespace {

        void register_rotator_coordinate_unit_field(tc::InspectFacetBuilder& builder);

    } // namespace

    RotatorComponent::RotatorComponent()
        : KinematicUnitComponent("RotatorComponent", Vec3{0.0, 0.0, 1.0}, std::numbers::pi_v<double> / 180.0) {}

    void RotatorComponent::register_type() {
        auto descriptor = ComponentTypeDescriptorBuilder::native<RotatorComponent>(
            "RotatorComponent", "termin-components-kinematic", "KinematicUnitComponent");
        descriptor.category("Kinematic");
        register_rotator_coordinate_unit_field(descriptor.inspect());
        (void)descriptor.commit();
    }

    void RotatorComponent::apply() {
        Entity ent = entity();
        if (!ent.valid())
            return;

        const Vec3 axis = get_axis();
        const double angle = physical_coordinate();

        // local = origin * Rotation(axis, angle)
        Quat coord_rot = Quat::from_axis_angle(axis, angle);
        Quat origin{origin_rotation.x, origin_rotation.y, origin_rotation.z, origin_rotation.w};

        Quat final_rotation = origin * coord_rot;

        // Set rotation
        double xyzw[4] = {final_rotation.x, final_rotation.y, final_rotation.z, final_rotation.w};
        ent.set_local_rotation(xyzw);

        // Position comes from the zero-coordinate frame. Scale is not part of
        // the kinematic transform and remains untouched.
        double xyz[3] = {origin_position.x, origin_position.y, origin_position.z};
        ent.set_local_position(xyz);
    }

    void RotatorComponent::recalculate_origin() {
        double pos[3], rot[4];
        if (!read_entity_transform(pos, rot))
            return;

        // A rotator never changes its entity origin.
        origin_position = {pos[0], pos[1], pos[2]};

        // Reverse: origin_rot = current_rot * coord_rot.inverse()
        // Since current_rot = origin_rot * coord_rot
        const Quat coord_rot = Quat::from_axis_angle(get_axis(), physical_coordinate());

        Quat current_rot{rot[0], rot[1], rot[2], rot[3]};
        Quat origin = current_rot * coord_rot.inverse();
        origin_rotation = {origin.x, origin.y, origin.z, origin.w};
    }

    namespace {

        void register_rotator_coordinate_unit_field(tc::InspectFacetBuilder& builder) {
            tc::InspectFieldInfo info;
            info.type_name = "RotatorComponent";
            info.path = "coordinate_scale";
            info.label = "Coordinate Unit";
            info.kind = "enum";
            info.is_serializable = true;

            // Keep enough decimal digits to round-trip the double conversion
            // instead of baking std::to_string's six-decimal approximation
            // into every serialized scene.
            constexpr const char* degree_scale = "0.017453292519943295";
            info.choices = {
                {degree_scale, "deg"},
                {"1.0", "rad"},
            };

            info.getter = [](void* obj) -> tc_value {
                auto* c = static_cast<KinematicUnitComponent*>(obj);
                constexpr double deg_scale = std::numbers::pi_v<double> / 180.0;
                const double scale = c->get_coordinate_scale();
                if (std::abs(scale - deg_scale) < 1e-6)
                    return tc_value_string(degree_scale);
                if (std::abs(scale - 1.0) < 1e-6)
                    return tc_value_string("1.0");
                return tc_value_string(std::to_string(scale).c_str());
            };

            info.setter = [](void* obj, tc_value value, void*) -> bool {
                if (value.type != TC_VALUE_STRING || !value.data.s)
                    return false;
                double new_scale = std::atof(value.data.s);
                if (new_scale < 1e-12)
                    return false;

                auto* c = static_cast<KinematicUnitComponent*>(obj);
                c->set_coordinate_scale(new_scale);
                return true;
            };

            (void)builder.add_field(std::move(info));
        }

    } // namespace

} // namespace termin
