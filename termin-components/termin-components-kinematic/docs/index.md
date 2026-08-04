# termin-components-kinematic

Kinematic component package for actuator, articulation and kinematic-unit
components.

Связанные документы:

- [termin-components](../../docs/index.md)
- [termin-scene](../../../termin-scene/docs/index.md)

## Основные области

- `ArticulationComponent` compiles a direct
  `KinematicUnit -> KinematicUnit` scene tree into a solver-neutral borrowed
  `Articulation3D`.
- `KinematicUnitComponent` owns its output-frame spatial inertia together with
  the authored coordinate, zero pose and motion axis. No body/link scene
  object is introduced.
- `ActuatorComponent` and `RotatorComponent` define the supported one-DOF unit
  motions.
- Build and packaging metadata in `CMakeLists.txt` / `setup.py`.

## Публичный API

Component-level kinematic API is installed through this package and participates in the canonical `termin.kinematic` namespace.

`ArticulationComponent` rebuilds once at scene start or on an explicit
`rebuild()` call. It exposes the compiled articulation to Python as a borrowed
reference. It never runs a controller or integrates automatically. A caller
may explicitly call `integrate_velocity(generalized_velocity, dt)`, which
advances the numerical state and synchronizes authored coordinates back to the
unit entities.

Only direct unit ancestry is accepted. Fixed visual children are allowed, but
a unit hidden below a non-unit entity is rejected so the scene tree and the
numerical topology cannot silently diverge.

See the repository architecture decision
[Articulation3D as a chain of moving frames](../../../docs/architecture/2026-08-04-articulation3d-moving-frame-chain.md)
and the runnable
[kinematic point-tracking project](../../../test-projects/kinematic-point-tracking/README.md).
