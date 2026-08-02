# FEM Standing Robot

This standalone Termin project is the first vertical acceptance for the native
reduced-coordinate articulation path. `Robot Base` is a free rigid body with
six physical DOF. Four scene-authored branches each contain a hip, an upper
leg, a knee, and a lower leg. The eight `RotatorComponent` coordinates compile
into the same `FEMArticulationComponent`; every joint has a separate bounded
motor and servo contribution.

The thighs lean inward and the knees bend back in the opposite direction, so
the knees tuck under the body while the feet remain under their attachment
points. The model cannot remain upright as a passive four-strut table:
motor moments are required to hold the authored pose. No joint is represented
by a maximal-coordinate constraint, the base is not fixed, all damping is zero,
and every servo has zero feed-forward effort.

Four foot-effector entities own spherical colliders and use the common
`CollisionWorld` geometry path. Contact routing resolves each effector to the
nearest parent FEM link, so collision geometry does not have to live on the
same entity as mass and inertia. Each effector origin is the center of its
contact sphere; the collider has no local offset, and the visible sphere uses
the same `0.24 m` diameter on all three axes.
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
- the base descends from `z = 1.67 m` and remains between `1.37 m` and
  `1.67 m` after settling;
- four foot contacts carry approximately `109.9 N`, the weight of the
  `11.2 kg` model;
- friction work is never positive and the settled feet are not sliding;
- the solver continues advancing without a numerical-failure log.

Clear `SERVOS ENABLED` after the stance has settled. The HUD disables all eight
servo components while leaving motors, contacts, and friction intact. The bent
legs collapse and the floating base loses at least `0.25 m` of height within
three seconds. Check the box again to restore control; restarting Play restores
the authored initial state.

The same five-second stance and the first `0.25 m` of servo-off collapse are
covered by `termin_components_physics_fem_component_test`. A separate
fifty-second acceptance reproduces the scene's high, asymmetrically tilted drop
and verifies that contact solving keeps advancing. The collapse must
complete within three seconds; all three cases are run by `./run-tests.sh`.
