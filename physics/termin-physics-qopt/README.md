# termin-physics-qopt

`termin-physics-qopt` is the physical simulation layer built on
`termin-qopt`. It owns the contribution-based dynamics problem, physical
contacts and time stepping; it does not own robot-control policy.

The native library contains:

- `DynamicsSystem` and typed topology/assembly contracts;
- maximal-coordinate 2D and 3D rigid bodies and joints;
- `Articulation3DDynamicsContribution`, which borrows a
  `termin::robotics::Articulation3D`;
- bounded articulation motor efforts;
- a validated bridge from robotics inverse-dynamics actuator/result contracts
  to articulation motor channels;
- a point-contact force adapter for inverse-dynamics normal/tangent variables;
- unilateral contacts, persistence and warm-start state;
- the Coulomb-friction approximation;
- acceleration solve, integration, position/velocity projection and
  transactional rollback.

Its dependency direction is:

```text
termin-qopt          termin-robotics
        \             /
         termin-physics-qopt
                    ↑
     termin-components-physics-fem
```

Physical types live in `termin::physics_qopt` and are included through
`<termin/physics_qopt/...>`. Numerical solver types remain in `termin::qopt` and
are included through `<termin/qopt/...>`.

The dynamic-control loop keeps controller policy outside the physics system:

```cpp
const auto motor_model = inverse_dynamics_actuators_from_motor(motor);
InverseDynamicsHqpController3D controller(
    articulation_model, motor_model.actuators, gravity_world);

JointPostureTask3D posture(
    {}, target_positions, target_velocities, position_gain, velocity_gain);
const std::array<const ArticulationTask3D*, 1> tasks{&posture};
const auto control = controller.solve(tasks, {.time_step = time_step});
if (!control.ok() ||
    apply_inverse_dynamics_motor_commands(motor, control) !=
        RoboticsControlAdapterDiagnostic3D::None) {
    // Report the controller or adapter diagnostic and do not step silently.
}
const auto step = system.step({.time_step = time_step});
```

The motor adapter validates channel count and reduced-DOF order before writing
commands. Contact-force variables are likewise explicit:

```cpp
const auto support = inverse_dynamics_contact_force_block(
    articulation_dynamics,
    ContactEndpoint3D::articulation_unit(
        articulation_dynamics, foot_unit, foot_point_local),
    ground_normal_world, friction_coefficient, maximum_normal_force,
    "left-foot");
InverseDynamicsControlOptions3D options;
options.time_step = time_step;
options.force_variable_blocks = {support.block};
const auto control = controller.solve(tasks, options);
```

Positive normal force acts along the explicitly supplied world direction on
the controlled articulation. Variables are ordered `[normal, tangent_1,
tangent_2]`; the adapter supplies `normal >= 0`, an optional normal maximum,
and the conservative pyramid `|t1| + |t2| <= mu * normal`.

`examples/dynamic_joint_control.cpp` demonstrates the complete plant loop:
inverse-dynamics HQP, validated motor command transfer and `DynamicsSystem`
stepping. With native tests enabled it is built and run as
`termin_physics_qopt_dynamic_joint_control_example`.

The multibody oracle and native regression corpus live under `tests/`. The
separate scene-component module compiles authored entities into these physical
contributions.
