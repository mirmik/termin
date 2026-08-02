# FEM Double Pendulum

This complete Termin project exercises the native C++ QP multibody stack
through the reduced-coordinate articulation path. `Fixed Anchor` is an
`FEMArticulationComponent`; beneath it the scene alternates explicit joint
entities containing `RotatorComponent` with link entities containing
`FEMRigidBodyComponent`. The two generalized coordinates replace twelve body
coordinates and ten hinge constraint equations.

Both rotators declare the Y hinge axis in their local attachment frames, so the
double pendulum remains in the authored XZ plane by construction. The visible
link dimensions remain mesh offsets; all articulation frames are rigid.

## Open in the editor

```bash
./sdk/bin/termin_editor \
  test-projects/fem-double-pendulum/FEMDoublePendulum.terminproj
```

Open `Scenes/Main.scene`, then enter Play mode to start the simulation from the
authored poses. The orange link starts at 55 degrees from vertical and the blue
link at -25 degrees, which produces an immediately visible nonlinear motion.

## Inspect the desktop profile

```bash
./sdk/bin/termin_builder profile linux-dev \
  --project test-projects/fem-double-pendulum

./sdk/bin/termin_builder build linux-dev \
  --dry-run \
  --project test-projects/fem-double-pendulum
```

The project needs no Python module or NumPy runtime dependency. Its scene
component types are native factories registered by Termin bootstrap, so the
desktop package is expected to build directly:

```bash
./sdk/bin/termin_builder build linux-dev \
  --project test-projects/fem-double-pendulum
```

The top-right native HUD displays current mechanical energy, its signed change
from the initial state, simulated time, successful solver steps, and the
compiled multibody topology size. `FEMPhysicsHudComponent` refreshes the named
labels in `UI/physics_hud.uiscript` without introducing Python into either the
simulation or presentation path.

## Manual verification

- Enter Play mode and let the scene run for at least 20 seconds.
- The fixed gold anchor and both touching link endpoints should not separate.
- The links should remain in the XZ plane in the undisturbed authored setup.
- The telemetry HUD should update energy, time, and successful step count.
- The HUD topology line should report one articulation and two reduced DOFs.
- Check the log for unknown-component, articulation-compilation, native-QP
  step, and FEM transform-contract errors.

Joint visualization remains separate editor work tracked as `#1229`.
