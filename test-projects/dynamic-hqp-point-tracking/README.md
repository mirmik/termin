# Dynamic HQP point tracking

A fixed-base three-dimensional manipulator tracks an orbiting target using an
explicit two-level inverse-dynamics HQP. The first unit rotates in azimuth;
shoulder and elbow rotate about horizontal axes.

The scene uses one shared runtime model:

```text
Arm Root (ArticulationComponent, FEMArticulationComponent, controller)
└── Azimuth Unit (RotatorComponent, bounded FEM motor)
    └── Shoulder Unit (RotatorComponent, bounded FEM motor)
        └── Elbow Unit (RotatorComponent, bounded FEM motor)
```

`DynamicPointTrackingControllerComponent.fixed_update()` executes at the
control priority and constructs the complete task hierarchy in Python:

```python
PointAccelerationTask3D(..., priority=0, diagonal_weight=[1, 1, 0])
PointAccelerationTask3D(..., priority=1, diagonal_weight=[0, 0, 1])
result = controller.solve(tasks, time_step=dt)
```

Priority `0` protects horizontal XY tracking. Priority `1` improves vertical
Z tracking only in the remaining null space and therefore cannot degrade the
horizontal result. Joint position, joint velocity, motor effort and
unactuated-dynamics conditions remain hard constraints.

The component transfers the resulting bounded efforts through the validated
FEM motor adapter. `FEMPhysicsWorldComponent` executes afterwards at the
physics priority and is the only component that advances the state.

The visual meshes are presentation attached to the moving unit entities; they
are not links in `Articulation3D`.
