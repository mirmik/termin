# FEM Standing Robot

This standalone Termin project is the first vertical acceptance for the native
reduced-coordinate articulation path. `Robot Base` is a free rigid body with
six physical DOF. Four scene-authored branches each contain a hip, an upper
leg, a knee, and a lower leg. The eight `RotatorComponent` coordinates compile
into the same `FEMArticulationComponent`; every joint has a separate bounded
motor and servo contribution.

The knees are deliberately bent. The model therefore cannot remain upright as
a passive four-strut table: motor moments are required to hold the authored
pose. No joint is represented by a maximal-coordinate constraint, the base is
not fixed, all damping is zero, and every servo has zero feed-forward effort.

Four spherical foot colliders use the common `CollisionWorld` geometry path.
`FEMPhysicsWorldComponent` assigns the generated contacts a combined Coulomb
coefficient of `0.8`. The robot starts five centimetres above the plane, falls
onto its feet, and settles without a restitution impulse. The HUD reports base
pose/speed, energy, topology, aggregate motor work, contact reaction, friction
work, and a representative knee servo. It retains twelve seconds of normal
reaction and knee-effort history.

## Run

```bash
./sdk/bin/termin_editor \
  test-projects/fem-standing-robot/FEMStandingRobot.terminproj
```

Enter Play mode and observe the first five seconds. Expected:

- topology is `9 bodies`, `1 articulation`, and `14 reduced DOF` (`6 + 8`);
- the base descends from `z = 1.55 m` and remains between `1.25 m` and
  `1.55 m` after settling;
- four foot contacts carry approximately `109.9 N`, the weight of the
  `11.2 kg` model;
- friction work is never positive and the settled feet are not sliding;
- the solver continues advancing without a numerical-failure log.

Clear `SERVOS ENABLED` after the stance has settled. The HUD disables all eight
servo components while leaving motors, contacts, and friction intact. The bent
legs collapse and the floating base loses at least `0.25 m` of height within
three seconds. Check the box again to restore control; restarting Play restores
the authored initial state.

The same five-second stance and three-second servo-off collapse are covered by
`termin_components_physics_fem_component_test`, which is run by
`./run-tests.sh`.
