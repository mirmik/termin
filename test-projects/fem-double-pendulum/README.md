# FEM Double Pendulum

This complete Termin project exercises the experimental Python FEM/QP physics
stack through `termin-physics-fem`. Two rigid links are connected by a point
joint; the first link is pinned to a fixed world anchor. The bodies use rigid
entity transforms, while their visible dimensions live in mesh offsets, as
required by the FEM transform contract.

The current `FEMRevoluteJointComponent` constrains the shared point but not a
rotation axis. The authored initial state is planar, so it behaves as a planar
double pendulum unless disturbed out of plane.

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

The selected project module declares `termin-physics-fem` and its QP
dependencies for a future portable desktop bundle. An actual build is
currently an intentional failing gate:

```bash
./sdk/bin/termin_builder build linux-dev \
  --project test-projects/fem-double-pendulum
```

Runtime package validation currently accepts only registered C++ component
factories. It runs before the selected Python module closure is loaded, so it
rejects the four `FEM*Component` types even though the Python-enabled player
can load them. This missing build/runtime capability contract is tracked on
the Termin task board as `#1230`.

## Manual verification

- Enter Play mode and let the scene run for at least 20 seconds.
- The fixed gold anchor and both touching link endpoints should not separate.
- The links should remain in the XZ plane in the undisturbed authored setup.
- Check the log for module loading, unknown-component, singular-matrix, and FEM
  transform-contract errors.

The current point-only revolute constraint and its inactive visualization code
are tracked separately as `#1228` and `#1229`.
