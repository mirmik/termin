# Dynamic HQP point tracking

A fixed-base three-dimensional manipulator tracks an orbiting target using
inverse-dynamics HQP. The first unit rotates in azimuth; shoulder and elbow
rotate about horizontal axes.

The scene uses one shared runtime model:

```text
Arm Root (ArticulationComponent, FEMArticulationComponent, controller)
└── Azimuth Unit (RotatorComponent, bounded FEM motor)
    └── Shoulder Unit (RotatorComponent, bounded FEM motor)
        └── Elbow Unit (RotatorComponent, bounded FEM motor)
```

`DynamicPointTrackingControllerComponent.fixed_update()` executes at the
control priority, calculates bounded efforts, and transfers them through the
validated FEM motor adapter. `FEMPhysicsWorldComponent` executes afterwards at
the physics priority and is the only component that advances the state.

The visual meshes are presentation attached to the moving unit entities; they
are not links in `Articulation3D`.
