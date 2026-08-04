# Kinematic point tracking

This project demonstrates an explicit two-level kinematic HQP controlling a
spatial manipulator that follows a moving target. The scene hierarchy is
direct:

```text
Arm Root (ArticulationComponent, PointTrackingControllerComponent)
└── Azimuth (RotatorComponent around world-up Z + inertia)
    └── Shoulder (RotatorComponent + inertia)
        └── Elbow (RotatorComponent + inertia)
```

`PointTrackingControllerComponent` borrows the compiled `Articulation3D` and
constructs the complete task list in Python. Priority `0` minimizes horizontal
XY point-velocity error. Priority `1` then minimizes vertical Z error only in
the null space left by priority `0`; it cannot trade horizontal accuracy for
height. Predictive joint-position and joint-velocity limits are hard
constraints introduced at the highest level.

The task weights make the hierarchy explicit:

```python
PointVelocityTask3D(..., priority=0, diagonal_weight=[1, 1, 0])
PointVelocityTask3D(..., priority=1, diagonal_weight=[0, 0, 1])
result = controller.solve(tasks, time_step=dt)
```

After the solve, the component explicitly calls
`ArticulationComponent.integrate_velocity()`. Neither the controller nor the
articulation component owns an automatic simulation loop.

Open `KinematicPointTracking.terminproj` and enter Play Mode. The green target
moves along a three-dimensional orbit; the orange tip follows it with bounded
joint velocity. When all requested motion cannot be achieved simultaneously,
horizontal tracking wins lexicographically over vertical tracking. The
azimuth joint turns the whole column around the vertical axis, while the
shoulder and elbow change reach and height.
