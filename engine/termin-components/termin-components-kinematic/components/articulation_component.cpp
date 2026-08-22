#include <components/articulation_component.hpp>

#include <cmath>
#include <functional>
#include <string>
#include <utility>

#include <components/actuator_component.hpp>
#include <components/kinematic_unit_component.hpp>
#include <components/rotator_component.hpp>
#include <tcbase/tc_log.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/geom/general_pose3.hpp>
#include <termin/robotics/velocity_control.hpp>

namespace termin {
    namespace {
        constexpr double rigid_tolerance = 1.0e-10;

        std::string entity_name(Entity entity) {
            const char* name = entity.name();
            return name != nullptr ? name : "<unnamed>";
        }

        bool unit_scale(Vec3 scale) {
            return scale.is_finite() && std::abs(scale.x - 1.0) <= rigid_tolerance &&
                   std::abs(scale.y - 1.0) <= rigid_tolerance && std::abs(scale.z - 1.0) <= rigid_tolerance;
        }

        bool local_transform_is_rigid(Entity entity) {
            const GeneralPose3 pose = entity.transform().local_pose();
            return unit_scale(pose.scale) && pose.lin.is_finite() && pose.ang.is_finite() &&
                   pose.ang.norm() > rigid_tolerance;
        }

        Pose3 unit_zero_pose(const KinematicUnitComponent& unit) {
            return Pose3{
                unit.origin_rotation.normalized(),
                unit.origin_position,
            };
        }

        Screw3 unit_motion_twist(const KinematicUnitComponent& unit) {
            if (dynamic_cast<const RotatorComponent*>(&unit) != nullptr) {
                return {unit.get_axis(), Vec3::zero()};
            }
            if (dynamic_cast<const ActuatorComponent*>(&unit) != nullptr) {
                return {Vec3::zero(), unit.get_axis()};
            }
            return Screw3::zero();
        }

        std::vector<KinematicUnitComponent*> enabled_units(Entity entity) {
            std::vector<KinematicUnitComponent*> result;
            for (std::size_t index = 0; index < entity.component_count(); ++index) {
                tc_component* component = entity.component_at(index);
                if (component == nullptr || component->kind != TC_CXX_COMPONENT) {
                    continue;
                }
                auto* unit = dynamic_cast<KinematicUnitComponent*>(CxxComponent::from_tc(component));
                if (unit != nullptr && unit->enabled()) {
                    result.push_back(unit);
                }
            }
            return result;
        }

        bool subtree_has_enabled_unit(Entity entity) {
            if (!enabled_units(entity).empty()) {
                return true;
            }
            for (Entity child : entity.children()) {
                if (subtree_has_enabled_unit(child)) {
                    return true;
                }
            }
            return false;
        }
    } // namespace

    std::string_view articulation_component_diagnostic_name(ArticulationComponentDiagnostic diagnostic) noexcept {
        switch (diagnostic) {
        case ArticulationComponentDiagnostic::None:
            return "none";
        case ArticulationComponentDiagnostic::InvalidRoot:
            return "invalid-root";
        case ArticulationComponentDiagnostic::EmptyArticulation:
            return "empty-articulation";
        case ArticulationComponentDiagnostic::MultipleUnitsOnEntity:
            return "multiple-units-on-entity";
        case ArticulationComponentDiagnostic::UnsupportedUnit:
            return "unsupported-unit";
        case ArticulationComponentDiagnostic::IndirectUnit:
            return "indirect-unit";
        case ArticulationComponentDiagnostic::NestedArticulation:
            return "nested-articulation";
        case ArticulationComponentDiagnostic::NonRigidTransform:
            return "non-rigid-transform";
        case ArticulationComponentDiagnostic::InvalidCoordinateScale:
            return "invalid-coordinate-scale";
        case ArticulationComponentDiagnostic::InvalidCoordinateLimits:
            return "invalid-coordinate-limits";
        case ArticulationComponentDiagnostic::InvalidInertia:
            return "invalid-inertia";
        case ArticulationComponentDiagnostic::InvalidModel:
            return "invalid-model";
        case ArticulationComponentDiagnostic::IntegrationFailure:
            return "integration-failure";
        case ArticulationComponentDiagnostic::SynchronizationFailure:
            return "synchronization-failure";
        }
        return "unknown";
    }

    ArticulationComponent::ArticulationComponent()
        : CxxComponent("ArticulationComponent") {}

    void ArticulationComponent::register_type() {
        auto descriptor = ComponentTypeDescriptorBuilder::native<ArticulationComponent>(
            "ArticulationComponent", "termin-components-kinematic", "Component");
        descriptor.category("Kinematic");
        (void)descriptor.inspect().add_button(
            "rebuild", "Rebuild Articulation", [](void* object, const tc::InspectContext&) {
                (void)static_cast<ArticulationComponent*>(object)->rebuild();
            });
        (void)descriptor.commit();
    }

    void ArticulationComponent::start() {
        (void)rebuild();
    }

    void ArticulationComponent::on_destroy() {
        articulation_.reset();
        bindings_.clear();
        coordinate_scales_.clear();
    }

    bool ArticulationComponent::rebuild() {
        articulation_.reset();
        bindings_.clear();
        coordinate_scales_.clear();
        diagnostic_ = ArticulationComponentDiagnostic::None;
        diagnostic_entity_.clear();

        const Entity root = entity();
        if (!root.valid()) {
            diagnostic_ = ArticulationComponentDiagnostic::InvalidRoot;
            diagnostic_entity_ = "<invalid>";
        } else if (!local_transform_is_rigid(root)) {
            diagnostic_ = ArticulationComponentDiagnostic::NonRigidTransform;
            diagnostic_entity_ = entity_name(root);
        }

        std::vector<robotics::ArticulationUnit3D> units;
        robotics::Articulation3DState state;
        const auto fail = [&](ArticulationComponentDiagnostic diagnostic, Entity candidate) {
            if (diagnostic_ == ArticulationComponentDiagnostic::None) {
                diagnostic_ = diagnostic;
                diagnostic_entity_ = entity_name(candidate);
            }
        };

        std::function<void(Entity, std::size_t)> compile_children;
        compile_children = [&](Entity parent_entity, std::size_t parent_unit) {
            if (diagnostic_ != ArticulationComponentDiagnostic::None) {
                return;
            }
            for (Entity child : parent_entity.children()) {
                if (child.get_component<ArticulationComponent>() != nullptr) {
                    fail(ArticulationComponentDiagnostic::NestedArticulation, child);
                    return;
                }

                const std::vector<KinematicUnitComponent*> child_units = enabled_units(child);
                if (child_units.empty()) {
                    if (subtree_has_enabled_unit(child)) {
                        fail(ArticulationComponentDiagnostic::IndirectUnit, child);
                        return;
                    }
                    continue;
                }
                if (child_units.size() != 1) {
                    fail(ArticulationComponentDiagnostic::MultipleUnitsOnEntity, child);
                    return;
                }

                KinematicUnitComponent* unit = child_units.front();
                if (dynamic_cast<RotatorComponent*>(unit) == nullptr &&
                    dynamic_cast<ActuatorComponent*>(unit) == nullptr) {
                    fail(ArticulationComponentDiagnostic::UnsupportedUnit, child);
                    return;
                }
                if (!local_transform_is_rigid(child)) {
                    fail(ArticulationComponentDiagnostic::NonRigidTransform, child);
                    return;
                }
                const double scale = unit->get_coordinate_scale();
                if (!std::isfinite(scale) || scale <= 0.0) {
                    fail(ArticulationComponentDiagnostic::InvalidCoordinateScale, child);
                    return;
                }
                if (!std::isfinite(unit->min_coordinate) || !std::isfinite(unit->max_coordinate) ||
                    unit->min_coordinate > unit->max_coordinate) {
                    fail(ArticulationComponentDiagnostic::InvalidCoordinateLimits, child);
                    return;
                }
                const SpatialInertia3 inertia = unit->spatial_inertia();
                if (!inertia.is_valid()) {
                    fail(ArticulationComponentDiagnostic::InvalidInertia, child);
                    return;
                }

                Pose3 zero_pose = unit_zero_pose(*unit);
                if (parent_unit == robotics::articulation_root_frame) {
                    zero_pose = (root.transform().global_pose() * zero_pose).normalized();
                }
                const std::size_t unit_index = units.size();
                units.push_back({
                    .parent_unit = parent_unit,
                    .parent_to_unit_zero = zero_pose,
                    .motion_twist_at_unit = unit_motion_twist(*unit),
                    .inertia = inertia,
                    .limits =
                        {
                            .minimum = unit->min_coordinate * scale,
                            .maximum = unit->max_coordinate * scale,
                        },
                    .diagnostic_name = entity_name(child),
                });
                state.coordinates.push_back(unit->physical_coordinate());
                state.velocities.push_back(0.0);
                bindings_.push_back(unit);
                coordinate_scales_.push_back(scale);
                compile_children(child, unit_index);
                if (diagnostic_ != ArticulationComponentDiagnostic::None) {
                    return;
                }
            }
        };

        if (diagnostic_ == ArticulationComponentDiagnostic::None) {
            compile_children(root, robotics::articulation_root_frame);
        }
        if (diagnostic_ == ArticulationComponentDiagnostic::None && units.empty()) {
            diagnostic_ = ArticulationComponentDiagnostic::EmptyArticulation;
            diagnostic_entity_ = entity_name(root);
        }
        if (diagnostic_ != ArticulationComponentDiagnostic::None) {
            tc::Log::error("[ArticulationComponent] compilation failed at '%s': %s",
                           diagnostic_entity_.c_str(),
                           articulation_component_diagnostic_name(diagnostic_).data());
            bindings_.clear();
            coordinate_scales_.clear();
            return false;
        }

        articulation_ =
            std::make_shared<robotics::Articulation3D>(std::move(units), std::move(state), entity_name(root));
        if (articulation_->diagnostic() != robotics::Articulation3DDiagnostic::None) {
            tc::Log::error("[ArticulationComponent] reduced model is invalid: %s",
                           robotics::articulation3d_diagnostic_name(articulation_->diagnostic()).data());
            articulation_.reset();
            bindings_.clear();
            coordinate_scales_.clear();
            diagnostic_ = ArticulationComponentDiagnostic::InvalidModel;
            diagnostic_entity_ = entity_name(root);
            return false;
        }
        return true;
    }

    bool ArticulationComponent::synchronize() {
        if (articulation_ == nullptr || bindings_.size() != articulation_->unit_count() ||
            coordinate_scales_.size() != bindings_.size() ||
            articulation_->state().coordinates.size() != bindings_.size()) {
            diagnostic_ = ArticulationComponentDiagnostic::SynchronizationFailure;
            tc::Log::error("[ArticulationComponent] cannot synchronize an incomplete "
                           "runtime binding");
            return false;
        }
        for (std::size_t index = 0; index < bindings_.size(); ++index) {
            KinematicUnitComponent* unit = bindings_[index];
            const double scale = coordinate_scales_[index];
            if (unit == nullptr || !std::isfinite(scale) || scale <= 0.0) {
                diagnostic_ = ArticulationComponentDiagnostic::SynchronizationFailure;
                tc::Log::error("[ArticulationComponent] invalid unit binding at index %zu", index);
                return false;
            }
            unit->set_coordinate(articulation_->state().coordinates[index] / scale);
        }
        diagnostic_ = ArticulationComponentDiagnostic::None;
        diagnostic_entity_.clear();
        return true;
    }

    bool ArticulationComponent::integrate_velocity(std::span<const double> generalized_velocity, double time_step) {
        if (articulation_ == nullptr) {
            diagnostic_ = ArticulationComponentDiagnostic::InvalidModel;
            tc::Log::error("[ArticulationComponent] cannot integrate before rebuild");
            return false;
        }
        const robotics::VelocityIntegrationResult3D result = robotics::integrate_articulation_velocity(
            *articulation_, {generalized_velocity.data(), generalized_velocity.size()}, time_step);
        if (!result.ok()) {
            diagnostic_ = ArticulationComponentDiagnostic::IntegrationFailure;
            tc::Log::error("[ArticulationComponent] velocity integration failed: %s",
                           robotics::velocity_integration_diagnostic_name(result.diagnostic).data());
            return false;
        }
        return synchronize();
    }

    bool ArticulationComponent::initialized() const noexcept {
        return articulation_ != nullptr;
    }

    std::size_t ArticulationComponent::unit_count() const noexcept {
        return articulation_ != nullptr ? articulation_->unit_count() : 0;
    }

    KinematicUnitComponent* ArticulationComponent::unit_component(std::size_t unit_index) noexcept {
        return unit_index < bindings_.size() ? bindings_[unit_index] : nullptr;
    }

    const KinematicUnitComponent* ArticulationComponent::unit_component(std::size_t unit_index) const noexcept {
        return unit_index < bindings_.size() ? bindings_[unit_index] : nullptr;
    }

    double ArticulationComponent::unit_coordinate_scale(std::size_t unit_index) const noexcept {
        return unit_index < coordinate_scales_.size() ? coordinate_scales_[unit_index] : 0.0;
    }

    ArticulationComponentDiagnostic ArticulationComponent::diagnostic() const noexcept {
        return diagnostic_;
    }

    std::string_view ArticulationComponent::diagnostic_entity() const noexcept {
        return diagnostic_entity_;
    }

    robotics::Articulation3D* ArticulationComponent::articulation() noexcept {
        return articulation_.get();
    }

    const robotics::Articulation3D* ArticulationComponent::articulation() const noexcept {
        return articulation_.get();
    }

    std::shared_ptr<robotics::Articulation3D> ArticulationComponent::articulation_shared() const noexcept {
        return articulation_;
    }
} // namespace termin
