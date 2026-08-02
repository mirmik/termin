# FEM Contact Acceptance

This standalone Termin project exercises the native frictionless contact path
from the scene `CollisionWorld` into `ContactSet3DContribution`. It deliberately
does not use the game-physics `PhysicsWorld`.

The blue maximal body falls onto the static ground. At the documented
`time_step = 0.002 s` it may penetrate by roughly 5.5 mm during the first impact
step, then split position projection restores the surface pose without adding
restitution. Its zero-friction tangential-velocity preservation is covered by
the headless native component test.

The orange reduced articulation rests on the same ground. Gravity plus a
`2 N·m` motor command press its link into the plane; contact reaction supplies
the balancing generalized joint effort. The HUD displays signed gap, normal
impulse/reaction, active contact count, topology, motor and energy telemetry.
It also distinguishes current, cached, and warm-started contacts. Both plots
retain a bounded 30-second history.

## Run

```bash
./sdk/bin/termin_editor \
  test-projects/fem-contact-acceptance/FEMContactAcceptance.terminproj
```

Enter Play mode and leave the scene running for at least 30 seconds. Expected:

- the blue body settles at the ground surface without bouncing or tunnelling;
- the orange link remains supported and the QP solver stays initialized;
- contact count and reaction remain continuous after settling, without the
  exact-surface one-frame sawtooth or penetration runaway;
- stopping and starting Play does not retain stale contacts.

Headless coverage is part of
`termin_components_physics_fem_component_test` and runs through
`./run-tests.sh`.
