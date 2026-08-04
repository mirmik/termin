# Kinematic point tracking

This project demonstrates a solver-neutral spatial manipulator following a
moving target while standing on a floor. The scene hierarchy is direct:

```text
Arm Root (ArticulationComponent, PointTrackingControllerComponent)
└── Azimuth (RotatorComponent around world-up Z + inertia)
    └── Shoulder (RotatorComponent + inertia)
        └── Elbow (RotatorComponent + inertia)
```

`PointTrackingControllerComponent` borrows the compiled `Articulation3D`,
calculates a Cartesian point-velocity command through
`VelocityHqpController3D`, and explicitly calls
`ArticulationComponent.integrate_velocity()`. Neither the controller nor the
articulation component owns an automatic simulation loop.

Open `KinematicPointTracking.terminproj` and enter Play Mode. The green target
moves along a three-dimensional orbit; the orange tip follows it with bounded
joint velocity. The azimuth joint turns the whole column around the vertical
axis, while the shoulder and elbow change reach and height.
