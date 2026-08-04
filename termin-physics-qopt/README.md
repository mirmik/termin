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
commands. Contact-force decision variables are intentionally not inferred from
the simulation state; they require the explicit contact adapter described in
the robotics roadmap.

The multibody oracle and native regression corpus live under `tests/`. The
separate scene-component module compiles authored entities into these physical
contributions.
