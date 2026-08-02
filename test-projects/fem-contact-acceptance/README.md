# FEM Contact Acceptance

This standalone Termin project exercises the native frictionless contact path
from the scene `CollisionWorld` into `ContactSet3DContribution`. It deliberately
does not use the game-physics `PhysicsWorld`.

The blue maximal body falls onto the static ground. At the documented
`time_step = 0.002 s` it may penetrate by roughly 5.5 mm during the first impact
step, then split position projection restores the surface pose without adding
restitution. Its zero-friction tangential-velocity preservation is covered by
the headless native component test.

The orange reduced articulation is a two-metre lever with one revolute DOF.
Its fixed hinge is 1.5 metres above the ground, so the initially horizontal
lever visibly falls under gravity and strikes the plane before it can hang
vertically. The resulting diagonal resting pose requires a persistent contact
reaction and exercises contact force mapping into the reduced joint coordinate.
There is deliberately no motor in this fixture. The HUD displays signed gap,
normal impulse/reaction, active contact count, topology and energy telemetry.
It also distinguishes current, cached, and warm-started contacts. Both plots
retain a bounded 30-second history.

## Run

```bash
./sdk/bin/termin_editor \
  test-projects/fem-contact-acceptance/FEMContactAcceptance.terminproj
```

Enter Play mode and leave the scene running for at least 30 seconds. Expected:

- the blue body settles at the ground surface without bouncing or tunnelling;
- the orange lever falls, strikes the ground, and remains diagonally supported
  while the QP solver stays initialized;
- contact count and reaction remain continuous after settling, without the
  exact-surface one-frame sawtooth or penetration runaway;
- stopping and starting Play does not retain stale contacts.

Headless coverage is part of
`termin_components_physics_fem_component_test` and runs through
`./run-tests.sh`.
