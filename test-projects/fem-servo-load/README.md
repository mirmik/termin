# FEM Servo Load

This standalone Termin project demonstrates a bounded PD servo acting on one
reduced articulation coordinate. It is intentionally separate from the passive
double-pendulum energy-conservation example.

`Servo Stand` is a fixed `FEMArticulationComponent`. Its child `Servo Joint`
contains a `RotatorComponent`, a physical `FEMArticulationMotorComponent`, and
a separate `FEMJointServoComponent`; the compiler infers their shared reduced
DOF. `Driven Load` is one physical rigid link. Its arm and endpoint sphere are
visual parts of that same link, while its mass and principal inertia are
authored explicitly on `FEMRigidBodyComponent`.

The joint coordinate is authored in degrees. Its axis is the unit Y direction,
and `coordinate_scale = pi / 180` converts state and targets to radians at the
physics boundary. The servo starts at 15 degrees and tracks 90 degrees using:

```text
effort = 100 (target_position - position)
       + 100 integral(target_position - position) dt
       + 20  (target_velocity - velocity)
       + feed_forward_effort
```

The example sets `feed_forward_effort` to zero and enables the integral loop.
The servo writes its command to the motor, which limits it to 50 N·m. The
integral contribution is limited to 40 N·m and uses conditional integration to
avoid winding up further while the motor is saturated. It removes the loaded
joint's steady-state position error without treating a constant direct effort
as gravity compensation. Constant direct effort remains available for external
controllers and known bias loads.

Clear `Position Control` to disable the complete position loop, including both
the proportional and integral terms. `Integral Control` independently disables
only the integral term while the position loop remains enabled. With `Position
Control` cleared, the component is a pure velocity regulator using
`target_velocity`, `velocity_gain`, and the optional direct feed-forward effort.

## Run

```bash
./sdk/bin/termin_editor \
  test-projects/fem-servo-load/FEMServoLoad.terminproj
```

Enter Play mode. The motor should initially saturate and lift the load toward
the horizontal target. The HUD
shows measured/target coordinate, tracking error, applied/maximum effort,
instantaneous power and aggregate motor work. Mechanical energy is not
conserved because the motor exchanges energy with the articulation.

The same HUD embeds a ready `termin.gui.Plot2D` widget and streams a bounded
30-second history of measured and target coordinates into two retained line
series. This demonstrates direct tcplot rendering inside a `.uiscript` widget
tree; it does not use a `SceneView` or an offscreen texture.

The project uses only native component factories and has no Python runtime
module or NumPy dependency.
