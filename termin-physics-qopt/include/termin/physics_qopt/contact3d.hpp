#pragma once

#include <cstddef>
#include <cstdint>
#include <string>
#include <string_view>
#include <vector>

#include <termin/geom/vec3.hpp>
#include <termin/physics_qopt/dynamics.hpp>
#include <termin/physics_qopt/point_kinematics3d.hpp>
#include <termin/physics_qopt/termin_physics_qopt_api.hpp>

namespace termin::physics_qopt {

    class RigidBody3DContribution;
    class Articulation3DDynamicsContribution;

    enum class Contact3DDiagnostic : std::uint8_t {
        None,
        InvalidEndpoint,
        InvalidEndpointPair,
        InvalidNormal,
        NonFiniteGap,
        InvalidFrictionCoefficient,
        DuplicateKey,
        CacheCapacityExceeded,
        InvalidState,
        InternalFailure,
    };

    [[nodiscard]] TERMIN_PHYSICS_QOPT_API std::string_view
    contact3d_diagnostic_name(Contact3DDiagnostic diagnostic) noexcept;

    // A contact endpoint is a material point owned by a dynamics contribution,
    // or a fixed point in the inertial world. It deliberately contains no
    // collider, scene, or entity reference.
    class TERMIN_PHYSICS_QOPT_API ContactEndpoint3D {
    public:
        ContactEndpoint3D() = default;

        [[nodiscard]] static ContactEndpoint3D static_world(termin::Vec3 position_world) noexcept;
        [[nodiscard]] static ContactEndpoint3D rigid_body(RigidBody3DContribution& body,
                                                          termin::Vec3 point_local) noexcept;
        [[nodiscard]] static ContactEndpoint3D articulation_unit(Articulation3DDynamicsContribution& articulation,
                                                                 std::size_t unit_index,
                                                                 termin::Vec3 point_local) noexcept;
        [[nodiscard]] static ContactEndpoint3D articulation_base(Articulation3DDynamicsContribution& articulation,
                                                                 termin::Vec3 point_local) noexcept;

        [[nodiscard]] bool valid() const noexcept;
        [[nodiscard]] bool is_static() const noexcept;
        [[nodiscard]] bool belongs_to(const Articulation3DDynamicsContribution& articulation) const noexcept;
        [[nodiscard]] PointKinematics3DResult point_kinematics() const noexcept;

    private:
        enum class Kind : std::uint8_t {
            Invalid,
            StaticWorld,
            RigidBody,
            ArticulationBase,
            ArticulationUnit,
        };

        Kind kind_ = Kind::Invalid;
        RigidBody3DContribution* body_ = nullptr;
        Articulation3DDynamicsContribution* articulation_ = nullptr;
        std::size_t unit_index_ = 0;
        termin::Vec3 point_ = termin::Vec3::zero();
    };

    struct TERMIN_PHYSICS_QOPT_API Contact3D {
        std::uint64_t key = 0;
        // Optional caller-owned pair/manifold identity. Contacts from a live
        // group may survive a complete geometric query miss while their
        // material points remain within the persistence distance.
        std::uint64_t group_key = 0;
        ContactEndpoint3D endpoint_a;
        ContactEndpoint3D endpoint_b;
        // Unit vector from endpoint A toward endpoint B. Positive signed_gap
        // means separation; negative signed_gap means penetration.
        termin::Vec3 normal_from_a_to_b_world = termin::Vec3::unit_y();
        double signed_gap = 0.0;
        // Coulomb coefficient for this already combined material pair. Zero
        // preserves the exact frictionless path.
        double friction_coefficient = 0.0;
    };

    struct TERMIN_PHYSICS_QOPT_API ContactState3D {
        std::uint64_t key = 0;
        double signed_gap = 0.0;
        double normal_velocity = 0.0;
        double normal_impulse = 0.0;
        double normal_reaction = 0.0;
        termin::Vec3 tangent_velocity_world = termin::Vec3::zero();
        termin::Vec3 tangent_impulse_world = termin::Vec3::zero();
        double friction_work = 0.0;
        bool active = false;
        bool sliding = false;
    };

    // Frictionless transient contact rows. For n pointing A -> B, the
    // non-penetration condition is n dot (v_B - v_A) >= target. The QP stores
    // the equivalent C*v <= d row, so its non-negative multiplier produces
    // physical impulses -n on A and +n on B.
    class TERMIN_PHYSICS_QOPT_API ContactSet3DContribution final : public DynamicsContribution {
    public:
        explicit ContactSet3DContribution(std::string_view diagnostic_name = {});

        [[nodiscard]] Contact3DDiagnostic set_contacts(std::vector<Contact3D> contacts) noexcept;
        [[nodiscard]] Contact3DDiagnostic set_contacts(std::vector<Contact3D> contacts,
                                                       std::vector<std::uint64_t> live_groups) noexcept;
        [[nodiscard]] const std::vector<Contact3D>& contacts() const noexcept;
        [[nodiscard]] const std::vector<ContactState3D>& states() const noexcept;
        [[nodiscard]] Contact3DDiagnostic diagnostic() const noexcept;
        [[nodiscard]] std::size_t cached_contact_count() const noexcept;
        [[nodiscard]] std::size_t warm_started_contact_count() const noexcept;
        [[nodiscard]] double persistence_distance() const noexcept;
        [[nodiscard]] std::size_t maximum_cached_contacts() const noexcept;
        [[nodiscard]] bool set_persistence_distance(double distance) noexcept;
        [[nodiscard]] bool set_maximum_cached_contacts(std::size_t maximum) noexcept;
        void clear_cache() noexcept;

        AssemblyDiagnostic register_topology(DynamicsTopology& topology) noexcept override;
        AssemblyDiagnostic register_unilateral_constraints(DynamicsUnilateralTopology& topology,
                                                           double time_step) noexcept override;
        AssemblyDiagnostic register_friction_contacts(DynamicsFrictionTopology& topology,
                                                      double time_step) noexcept override;
        AssemblyDiagnostic assemble(DynamicsAssembly& assembly, DynamicsAssemblyPhase phase) noexcept override;
        AssemblyDiagnostic assemble_friction(DynamicsFrictionAssembly& assembly) noexcept override;
        AssemblyDiagnostic begin_step() noexcept override;
        void commit_step() noexcept override;
        void rollback_step() noexcept override;
        void apply_unilateral_solution(const DynamicsTopology& topology,
                                       const DynamicsUnilateralTopology& unilateral_topology,
                                       ConstDenseVectorView reactions,
                                       ConstDenseVectorView tight_mask) noexcept override;
        [[nodiscard]] bool write_unilateral_warm_start(const DynamicsUnilateralTopology& topology,
                                                       DenseVectorView active_mask) const noexcept override;
        void apply_friction_solution(const DynamicsFrictionTopology& topology,
                                     ConstDenseVectorView normal_impulses,
                                     ConstDenseVectorView tangent_impulses,
                                     ConstDenseVectorView friction_work) noexcept override;
        [[nodiscard]] double position_error_linf() const noexcept override;
        [[nodiscard]] double velocity_error_linf() const noexcept override;

    private:
        struct StepContact {
            DynamicsUnilateralConstraintHandle row;
            DynamicsFrictionContactHandle friction;
            termin::Vec3 tangent_1_world = termin::Vec3::zero();
            termin::Vec3 tangent_2_world = termin::Vec3::zero();
            double reference_separation = 0.0;
        };

        [[nodiscard]] Contact3DDiagnostic validate_contacts() const noexcept;
        [[nodiscard]] bool
        update_state(std::size_t index, PointKinematics3D& endpoint_a, PointKinematics3D& endpoint_b) noexcept;

        std::vector<Contact3D> contacts_;
        std::vector<ContactState3D> states_;
        std::vector<ContactState3D> state_cache_;
        std::vector<ContactState3D> states_snapshot_;
        std::vector<StepContact> step_contacts_;
        std::string diagnostic_name_;
        double time_step_ = 0.0;
        double persistence_distance_ = 1.0e-4;
        std::size_t maximum_cached_contacts_ = 4096;
        std::size_t warm_started_contact_count_ = 0;
        Contact3DDiagnostic diagnostic_ = Contact3DDiagnostic::None;
        bool snapshot_ready_ = false;
    };

} // namespace termin::physics_qopt
