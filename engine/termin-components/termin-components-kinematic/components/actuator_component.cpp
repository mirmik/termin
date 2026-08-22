#include "tc_inspect_cpp.hpp"
#include <cmath>
#include <components/actuator_component.hpp>
#include <cstdlib>
#include <tcbase/tc_log.hpp>
#include <termin/geom/quat.hpp>

namespace termin {

    namespace {

        void register_actuator_coordinate_unit_field(tc::InspectFacetBuilder& builder);

    } // namespace

    void ActuatorComponent::register_type() {
        auto descriptor = ComponentTypeDescriptorBuilder::native<ActuatorComponent>(
            "ActuatorComponent", "termin-components-kinematic", "KinematicUnitComponent");
        descriptor.category("Kinematic");
        register_actuator_coordinate_unit_field(descriptor.inspect());
        (void)descriptor.commit();
    }

    ActuatorComponent::ActuatorComponent()
        : KinematicUnitComponent("ActuatorComponent", Vec3{1.0, 0.0, 0.0}, 1.0) {}

    void ActuatorComponent::apply() {
        Entity ent = entity();
        if (!ent.valid()) {
            tc::Log::warn("ActuatorComponent::apply() - entity not valid");
            return;
        }

        // local = origin * Translation(axis * coordinate)
        const Vec3 axis = get_axis();

        // offset.position = axis * coordinate
        const Vec3 offset_pos = axis * physical_coordinate();
        const Vec3 new_position = origin_position + origin_rotation.rotate(offset_pos);

        GeneralTransform3 transform = ent.transform();
        transform.set_local_position(new_position);
        // Rotation comes from the zero-coordinate frame. Scale remains untouched.
        transform.set_local_rotation(origin_rotation);
    }

    void ActuatorComponent::recalculate_origin() {
        const Entity ent = entity();
        if (!ent.valid()) {
            return;
        }
        const GeneralTransform3 transform = ent.transform();
        const Vec3 current_position = transform.local_position();

        // An actuator never changes its entity rotation.
        origin_rotation = transform.local_rotation();

        // Reverse: origin_pos = current_pos - origin_rot.rotate(axis * coord)
        const Vec3 offset_pos = get_axis() * physical_coordinate();
        const Vec3 rotated = origin_rotation.rotate(offset_pos);

        origin_position = current_position - rotated;
    }

    namespace {

        void register_actuator_coordinate_unit_field(tc::InspectFacetBuilder& builder) {
            tc::InspectFieldInfo info;
            info.type_name = "ActuatorComponent";
            info.path = "coordinate_scale";
            info.label = "Coordinate Unit";
            info.kind = "enum";
            info.is_serializable = true;
            info.choices = {
                {"1.0", "m (1.0)"},
                {"0.01", "cm (0.01)"},
                {"0.001", "mm (0.001)"},
            };

            info.getter = [](void* obj) -> tc_value {
                auto* c = static_cast<KinematicUnitComponent*>(obj);
                const double scale = c->get_coordinate_scale();
                // Return closest preset as string
                if (std::abs(scale - 1.0) < 1e-6)
                    return tc_value_string("1.0");
                if (std::abs(scale - 0.01) < 1e-6)
                    return tc_value_string("0.01");
                if (std::abs(scale - 0.001) < 1e-6)
                    return tc_value_string("0.001");
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
