# Kinematic point tracking

This project demonstrates a solver-neutral two-unit manipulator following a
moving target. The scene hierarchy is direct:

```text
Arm Root (ArticulationComponent, PointTrackingControllerComponent)
└── Shoulder (RotatorComponent + inertia)
    └── Elbow (RotatorComponent + inertia)
```

`PointTrackingControllerComponent` borrows the compiled `Articulation3D`,
calculates a Cartesian point-velocity command through
`VelocityHqpController3D`, and explicitly calls
`ArticulationComponent.integrate_velocity()`. Neither the controller nor the
articulation component owns an automatic simulation loop.

Open `KinematicPointTracking.terminproj` and enter Play Mode. The green target
moves in the XZ plane; the orange tip of the arm follows it with bounded joint
velocity.
