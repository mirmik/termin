# Numeric Types and Precision

Status: accepted project-wide default.

## Precision boundary

Long-lived mutable numeric state uses double precision by default. This includes scene and tool state, camera parameters, accumulated transforms, simulation state, interactive gesture snapshots, and iterative CPU calculations. The corresponding canonical geometry types are `Vec2`, `Vec3`, `Mat33`, `Mat44`, `Quat`, `Rect2`, `Bounds2`, and `AABB`.

Single precision is appropriate when the value does not outlive the frame and its accuracy is not significant: GPU vertex/uniform payloads, transient render lists, pixels and other explicitly float-based backend interfaces. Conversion from double to float happens once at that boundary. Values should not repeatedly cross between precisions.

An exception is justified by a measured memory, bandwidth, vectorization, external ABI, or file-format constraint. The owning module must make that boundary explicit rather than allowing an incidental float type to spread into durable state.

## Structured geometry

Functions accept semantic geometry values instead of flat coordinate lists whenever such a type exists. Prefer `Vec2` over `(x, y)`, `Vec3` over `(x, y, z)`, `Rect2` over `(x, y, width, height)`, and `AABB` over separate minimum and maximum points. Flat scalar forms belong only at C ABI, serialization, or graphics-backend boundaries which require them.

This keeps coordinate systems and argument order visible in the type signature and prevents related values from being passed or converted independently.

Semantic types also own the algebra that is meaningful for them. Component-wise vector products, clamping and extrema belong to `Vec*`; containment, intersection and expansion belong to `Rect*`, `Bounds*` and `AABB*`; homogeneous multiplication and perspective division belong to `Mat44*`. Modules should not recreate these operations by unpacking the same values into local scalars.

## Checked operations

Operations which can fail for valid runtime inputs use an explicit checked form. Examples include normalizing a zero or non-finite vector, inverting a singular matrix, and applying a projective transform whose homogeneous `w` is zero. New code uses `try_normalized`, `normalized_or`, `try_inverse` and `try_transform_point` according to whether failure should be propagated or an explicit domain fallback is appropriate.

Legacy convenience methods may retain their established behavior for compatibility, but that behavior must not be used as an implicit error channel. In particular, a fallback vector or identity matrix is also a valid result and therefore cannot communicate failure by itself.

Checked functions with an output parameter leave that output unchanged on failure. Callers either return the failure, log it at the owning system boundary, or choose and name a domain-specific fallback.

## Boundary adapters

Packed C structs such as `tc_vec3`, `tc_bounds2f` and `tc_mat44` are valid semantic boundary representations when their meaning matches the value being transported. A C ABI does not by itself require an anonymous `float[3]` or a repeated local vector struct. Prefer the canonical standard-layout type and keep layout assertions near ABI-sensitive declarations.

Flat arrays remain appropriate for shader layouts, push constants, interleaved vertex and pixel buffers, persisted or wire formats, and external APIs whose storage contract requires them. Convert once in an explicitly named adapter owned by that boundary; do not let backend storage types become the internal math API.

## Camera example

Orbital camera state and its pan gesture are double precision. Pointer pan is expressed as two `Vec2` positions and a `Rect2` viewport. The gesture retains a double-precision inverse view-projection snapshot and computes its target through unprojection. Rendering converts the resulting `Mat44` to `Mat44f` only while constructing the per-frame GPU payload.
