# termin-components-physics

Physics component package for connecting entity components to physics simulation data.

Связанные документы:

- [termin-components](../../docs/index.md)
- [termin-physics](../../../termin-physics/docs/index.md)

## Основные области

- Build metadata in `CMakeLists.txt` and `setup.py`.
- Python component implementations under `python/termin/physics_components`.

## Публичный API

Component-level physics API is installed through this package and participates in the canonical `termin.physics_components` namespace.

## Transform contract

`RigidBodyComponent` uses the entity's logical world position and orientation
as the rigid-body frame. A world basis is accepted only while it has an exact
decomposed scale with finite positive axes. That scale sizes the component's
physics shape; it is not folded into the rigid pose.

Affine/sheared ancestry, reflections and singular scale are rejected with an
error log. Physics-to-scene synchronization updates world position and logical
orientation independently, preserving the authored local scale and the exact
scene basis derived from it.
