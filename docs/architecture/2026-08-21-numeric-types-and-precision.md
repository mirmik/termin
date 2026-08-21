# Numeric Types and Precision

Status: accepted project-wide default.

## Precision boundary

Long-lived mutable numeric state uses double precision by default. This includes scene and tool state, camera parameters, accumulated transforms, simulation state, interactive gesture snapshots, and iterative CPU calculations. The corresponding canonical geometry types are `Vec2`, `Vec3`, `Mat33`, `Mat44`, `Quat`, `Rect2`, `Bounds2`, and `AABB`.

Single precision is appropriate when the value does not outlive the frame and its accuracy is not significant: GPU vertex/uniform payloads, transient render lists, pixels and other explicitly float-based backend interfaces. Conversion from double to float happens once at that boundary. Values should not repeatedly cross between precisions.

An exception is justified by a measured memory, bandwidth, vectorization, external ABI, or file-format constraint. The owning module must make that boundary explicit rather than allowing an incidental float type to spread into durable state.

## Structured geometry

Functions accept semantic geometry values instead of flat coordinate lists whenever such a type exists. Prefer `Vec2` over `(x, y)`, `Vec3` over `(x, y, z)`, `Rect2` over `(x, y, width, height)`, and `AABB` over separate minimum and maximum points. Flat scalar forms belong only at C ABI, serialization, or graphics-backend boundaries which require them.

This keeps coordinate systems and argument order visible in the type signature and prevents related values from being passed or converted independently.

## Camera example

Orbital camera state and its pan gesture are double precision. Pointer pan is expressed as two `Vec2` positions and a `Rect2` viewport. The gesture retains a double-precision inverse view-projection snapshot and computes its target through unprojection. Rendering converts the resulting `Mat44` to `Mat44f` only while constructing the per-frame GPU payload.
