#include "tc_inspect_cpp.hpp"
#include <cmath>
#include <components/kinematic_unit_component.hpp>
#include <limits>
#include <numbers>
#include <tcbase/tc_log.hpp>
#include <termin/geom/pose3.hpp>

namespace termin {

    static double degrees(double rad) {
        return rad * (180.0 / std::numbers::pi_v<double>);
    }
    static double radians(double deg) {
        return deg * (std::numbers::pi_v<double> / 180.0);
    }

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
        auto descriptor = ComponentTypeDescriptorBuilder::abstract_native(
            "KinematicUnitComponent", "termin-components-kinematic", "Component");
        descriptor.category("Kinematic");
        auto& inspect = descriptor.inspect();

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
                const Vec3 axis = c->get_axis();
                tc_value list = tc_value_list_new();
                tc_value_list_push(&list, tc_value_double(axis.x));
                tc_value_list_push(&list, tc_value_double(axis.y));
                tc_value_list_push(&list, tc_value_double(axis.z));
                return list;
            };
            info.setter = [](void* obj, tc_value value, void*) -> bool {
                auto* c = static_cast<KinematicUnitComponent*>(obj);
                tc_vec3 v;
                if (tc_value_to_vec3(value, v)) {
                    c->set_axis(v);
                    return true;
                }
                return false;
            };
            (void)inspect.add_field(std::move(info));
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
            info.setter = [](void* obj, tc_value value, void*) -> bool {
                auto* c = static_cast<KinematicUnitComponent*>(obj);
                if (value.type == TC_VALUE_LIST && value.data.list.count >= 3) {
                    c->min_coordinate = tc::tc_value_to_double(&value.data.list.items[1]);
                    c->max_coordinate = tc::tc_value_to_double(&value.data.list.items[2]);
                    c->set_coordinate(tc::tc_value_to_double(&value.data.list.items[0]));
                } else {
                    // Backward compat: plain scalar serialized values.
                    double v = 0.0;
                    if (value.type == TC_VALUE_DOUBLE)
                        v = value.data.d;
                    else if (value.type == TC_VALUE_FLOAT)
                        v = value.data.f;
                    else if (value.type == TC_VALUE_INT)
                        v = static_cast<double>(value.data.i);
                    else
                        return false;
                    c->set_coordinate(v);
                }
                return true;
            };
            (void)inspect.add_field(std::move(info));
        }

        if (!inspect.find_field("KinematicUnitComponent", "origin_position")) {
            tc::InspectFieldInfo info;
            info.type_name = "KinematicUnitComponent";
            info.path = "origin_position";
            info.label = "Origin Position";
            info.kind = "vec3";
            info.min = -100000.0;
            info.max = 100000.0;
            info.step = 0.001;
            info.getter = [](void* obj) -> tc_value {
                auto* c = static_cast<KinematicUnitComponent*>(obj);
                tc_value list = tc_value_list_new();
                tc_value_list_push(&list, tc_value_double(c->origin_position.x));
                tc_value_list_push(&list, tc_value_double(c->origin_position.y));
                tc_value_list_push(&list, tc_value_double(c->origin_position.z));
                return list;
            };
            info.setter = [](void* obj, tc_value value, void*) -> bool {
                auto* c = static_cast<KinematicUnitComponent*>(obj);
                tc_vec3 v;
                if (tc_value_to_vec3(value, v)) {
                    c->origin_position = v;
                    c->apply();
                    return true;
                }
                return false;
            };
            (void)inspect.add_field(std::move(info));
        }

        if (!inspect.find_field("KinematicUnitComponent", "origin_rotation")) {
            tc::InspectFieldInfo info;
            info.type_name = "KinematicUnitComponent";
            info.path = "origin_rotation";
            info.label = "Origin Rotation";
            info.kind = "vec3";
            info.min = -360.0;
            info.max = 360.0;
            info.step = 0.1;
            info.getter = [](void* obj) -> tc_value {
                auto* c = static_cast<KinematicUnitComponent*>(obj);
                Pose3 p{c->origin_rotation, Vec3::zero()};
                Vec3 euler = p.to_euler();
                tc_value list = tc_value_list_new();
                tc_value_list_push(&list, tc_value_double(degrees(euler.x)));
                tc_value_list_push(&list, tc_value_double(degrees(euler.y)));
                tc_value_list_push(&list, tc_value_double(degrees(euler.z)));
                return list;
            };
            info.setter = [](void* obj, tc_value value, void*) -> bool {
                auto* c = static_cast<KinematicUnitComponent*>(obj);
                tc_vec3 v;
                if (tc_value_to_vec3(value, v)) {
                    Pose3 p = Pose3::from_euler(radians(v.x), radians(v.y), radians(v.z));
                    c->origin_rotation = p.ang;
                    c->apply();
                    return true;
                }
                return false;
            };
            (void)inspect.add_field(std::move(info));
        }

        if (!inspect.find_field("KinematicUnitComponent", "mass")) {
            (void)tc::stage_inspect_field(
                inspect, &KinematicUnitComponent::mass, "KinematicUnitComponent", "mass", "Mass", "double");
        }
        if (!inspect.find_field("KinematicUnitComponent", "inertia_diagonal")) {
            (void)tc::stage_inspect_field(inspect,
                                          &KinematicUnitComponent::inertia_diagonal,
                                          "KinematicUnitComponent",
                                          "inertia_diagonal",
                                          "Inertia (diagonal)",
                                          "vec3");
        }
        if (!inspect.find_field("KinematicUnitComponent", "center_of_mass")) {
            (void)tc::stage_inspect_field(inspect,
                                          &KinematicUnitComponent::center_of_mass,
                                          "KinematicUnitComponent",
                                          "center_of_mass",
                                          "Center of Mass",
                                          "vec3");
        }

        if (!inspect.find_field("KinematicUnitComponent", "recalculate_origin")) {
            (void)inspect.add_button(
                "recalculate_origin", "Recalculate Origin", [](void* obj, const tc::InspectContext&) {
                    auto* component = static_cast<KinematicUnitComponent*>(obj);
                    component->recalculate_origin();
                });
        }
        (void)descriptor.commit();
    }

    // KinematicUnitComponent implementation

    KinematicUnitComponent::KinematicUnitComponent(const char* type_name,
                                                   Vec3 default_axis,
                                                   double default_coordinate_scale)
        : CxxComponent(type_name) {
        Vec3 normalized_axis;
        if (default_axis.try_normalized(normalized_axis, 1.0e-12)) {
            axis_ = normalized_axis;
        }
        if (std::isfinite(default_coordinate_scale) && default_coordinate_scale > 0.0) {
            coordinate_scale_ = default_coordinate_scale;
        }
    }

    void KinematicUnitComponent::on_added() {
        CxxComponent::on_added();
        if (deserialized_state_) {
            apply();
        } else {
            recalculate_origin();
        }
    }

    void KinematicUnitComponent::deserialize_data(const tc_value* data, tc_scene_handle scene) {
        CxxComponent::deserialize_data(data, scene);
        deserialized_state_ = true;
    }

    void KinematicUnitComponent::set_axis(const Vec3& value) {
        Vec3 normalized_axis;
        if (!value.try_normalized(normalized_axis, 1.0e-12)) {
            tc::Log::error("[KinematicUnitComponent] rejected non-finite or "
                           "degenerate axis");
            return;
        }
        axis_ = normalized_axis;
        apply();
    }

    Vec3 KinematicUnitComponent::get_axis() const noexcept {
        return axis_;
    }

    void KinematicUnitComponent::set_coordinate_scale(double value) {
        if (!std::isfinite(value) || value <= 0.0) {
            tc::Log::error("[KinematicUnitComponent] rejected invalid coordinate scale");
            return;
        }
        coordinate_scale_ = value;
        apply();
    }

    double KinematicUnitComponent::get_coordinate_scale() const noexcept {
        return coordinate_scale_;
    }

    double KinematicUnitComponent::physical_coordinate() const noexcept {
        return coordinate * coordinate_scale_;
    }

    SpatialInertia3 KinematicUnitComponent::spatial_inertia() const noexcept {
        return {
            mass,
            inertia_diagonal,
            Pose3::translation(center_of_mass),
        };
    }

    void KinematicUnitComponent::set_coordinate(double value) {
        coordinate = value;
        apply();
    }

    void KinematicUnitComponent::apply() {
        // Default: no-op. Subclasses override.
    }

    void KinematicUnitComponent::recalculate_origin() {
        // Default: use the current transform as the origin pose.
        const Entity ent = entity();
        if (!ent.valid()) {
            return;
        }

        const GeneralTransform3 transform = ent.transform();
        origin_position = transform.local_position();
        origin_rotation = transform.local_rotation();
    }

} // namespace termin
