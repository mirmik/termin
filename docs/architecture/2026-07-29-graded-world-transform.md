# Graded World Transform

Date: 2026-07-29.

Status: proposed architecture concept.

## Context

The editable transform of a scene node is naturally represented as local TRS:

```text
translation + quaternion rotation + axis scale
```

Local TRS is convenient for authoring, animation and serialization, but it is
not closed under hierarchical composition. With column vectors, the linear
part of a local TRS is:

```text
B = R * D
```

where `R` is a rotation and `D` is a diagonal scale matrix. For a parent and a
child:

```text
B_world = B_parent * R_local * D_local
```

If the parent has non-uniform scale and the child has a non-commuting rotation,
the result contains shear and cannot be represented exactly as another TRS.

Always storing and exposing an arbitrary affine transform solves correctness,
but discards useful stronger guarantees. Most scene nodes are rigid, many
scaled roots use only uniform scale, and arbitrary affine transforms are
usually localized to particular asset branches. Rigid transforms also have
clear composition, inversion, interpolation and physics semantics.

The target model therefore preserves the strongest exact representation that
is valid for each world transform and promotes to a more general
representation only when composition requires it.

## Goals

1. Preserve exact hierarchical composition, including generated shear.
2. Keep rigid and uniform-scale branches explicitly recognizable.
3. Keep quaternion orientation stable for gameplay, cameras, physics and
   editor tools.
4. Localize affine representation to affected subtrees.
5. Keep representation branching inside the transform type and propagation
   system rather than spreading it across consumers.
6. Retain local TRS as the ordinary authored and animated representation.

## Non-goals

- This concept does not select AoS, SoA, archetype or sparse-payload storage.
- It does not require scalar decomposition of matrices for SIMD.
- It does not define automatic lossy projection from arbitrary affine values
  back to TRS.
- It does not make shear an ordinary authored property in the first version.
- It does not claim that tagged representation alone saves memory. An inline
  tagged union is normally as large as its largest alternative.

## Transform states

The world transform has four semantic states:

```text
Rigid       T * R
Similarity  T * R * uniform S
AxisScaled  T * R * non-uniform S
Affine      T * arbitrary Basis
```

`Rigid` is an element of `SE(3)`. In the initial proposal, `Similarity` adds a
positive uniform scale and remains closed under composition; the treatment of
negative uniform scale is an open policy decision. `AxisScaled` is the single
fragile decomposed tier: it remains useful while scale axes are compatible
with later rotations, but promotes to `Affine` when they are not.

The state names describe exact guarantees, not merely likely contents.

## Proposed data model

The editable local value remains a plain TRS:

```cpp
struct LocalTransform3 {
    Vec3d translation;
    Quatd rotation;
    Vec3d scale;
};
```

The derived world value is a closed type with controlled construction:

```cpp
enum class TransformKind : uint8_t {
    Rigid,
    Similarity,
    AxisScaled,
    Affine,
};

class WorldTransform3 {
    Vec3d translation_;

    // Logical scene-graph orientation. It is composed from local quaternion
    // channels even when basis_ becomes affine.
    Quatd orientation_;

    TransformKind kind_;

    union {
        // Active for Rigid, Similarity and AxisScaled.
        Vec3d scale_;

        // Active for Affine and authoritative for geometric transformation.
        Basis3d basis_;
    };
};
```

The conceptual invariants are:

```text
Rigid:
    scale == (1, 1, 1)
    linear basis == R(orientation)

Similarity:
    scale.x == scale.y == scale.z
    linear basis == R(orientation) * D(scale)

AxisScaled:
    linear basis == R(orientation) * D(scale)

Affine:
    basis is authoritative
    no exact decomposed scale is claimed
    orientation remains the logical quaternion channel
```

The concrete C/C++ representation may avoid a language union if construction
or ABI constraints make another closed layout simpler. The invariants and API
are more important than the initial byte layout.

## Logical orientation and geometric basis

`orientation` and `basis` deliberately have different meanings after affine
promotion:

```text
orientation = product of authored local quaternion channels
basis       = exact linear transformation of geometry
```

For `Rigid`, `Similarity` and `AxisScaled`, the basis is reconstructed from
orientation and scale. For `Affine`, the stored basis is authoritative and
need not equal `R(orientation) * D`.

Keeping logical orientation avoids deriving a quaternion from an arbitrary
basis through polar or QR decomposition. It gives stable semantics to:

- camera and gameplay orientation;
- `forward`, `up` and `right` logical axes;
- physics pose extraction where the transform contract permits it;
- orientation gizmos;
- `set_global_orientation`;
- animation channels.

Consumers that need actual transformed directions, bounds or geometry must
use the basis rather than logical orientation.

An arbitrary externally supplied `Affine3` does not intrinsically contain a
logical quaternion channel. Such construction must either require an explicit
logical orientation or use an explicitly named extraction policy such as
polar decomposition. It must not silently invent the channel.

## Composition

For parent world transform `P` and local TRS `L`, common values are:

```text
t_world = t_parent + B_parent * t_local
q_world = q_parent * q_local
B_local = R(q_local) * D(scale_local)
```

The exact affine reference is always:

```text
B_world = B_parent * B_local
```

The conservative promotion table is shown for the generalized composition of
two graded transforms. The current authored `LocalTransform3` uses only its
first three columns; the `Affine` column describes a possible future affine
local representation and exact reparenting operations.

| Parent × Local | Rigid | Similarity | AxisScaled | Affine |
|---|---:|---:|---:|---:|
| Rigid | Rigid | Similarity | AxisScaled | Affine |
| Similarity | Similarity | Similarity | AxisScaled | Affine |
| AxisScaled | Affine* | Affine* | Affine* | Affine |
| Affine | Affine | Affine | Affine | Affine |

`*` may remain `AxisScaled` when the local rotation commutes with the parent
axis scale. The first implementation should recognize only robust cases:

- parent scale is actually uniform, in which case the parent should already
  be `Similarity`;
- local rotation is exactly identity;
- an explicitly supported axis-preserving rotation case.

General epsilon-based commutation detection is not required. It risks state
flicker under animation and makes representation classification depend on
arbitrary tolerances. Conservative promotion is exact even when it is not
minimal.

When promotion is required:

```cpp
result.kind_ = TransformKind::Affine;
result.basis_ =
    parent.linear_basis()
    * Basis3d::from_quat(local.rotation)
    * Basis3d::from_scale(local.scale);
```

For an affine parent:

```cpp
result.basis_ = parent.basis_ * local.linear_basis();
```

`Affine` is conservatively absorbing during one propagation evaluation.
Although specially chosen affine matrices can cancel and produce a simpler
result, discovering such cancellation would require decomposition and is not
part of ordinary propagation.

Promotion is not permanent state attached to the entity. A dirty subtree is
recomputed from its current parent and local transform, so it may naturally
return from `Affine` to a simpler state after an ancestor changes.

## Conversion and consumer API

Consumers should not switch on `TransformKind` themselves. The type owns the
representation-dependent operations:

```cpp
class WorldTransform3 {
public:
    TransformKind kind() const;

    const Vec3d& translation() const;
    const Quatd& orientation() const;

    bool is_rigid() const;
    bool is_conformal() const;
    bool is_affine() const;

    Basis3d linear_basis() const;
    Affine3d affine() const;

    Vec3d transform_point(const Vec3d& point) const;
    Vec3d transform_vector(const Vec3d& vector) const;

    std::optional<Pose3> try_rigid_pose() const;
};
```

`linear_basis()` materializes the exact basis:

```cpp
switch (kind_) {
case TransformKind::Rigid:
    return Basis3d::from_quat(orientation_);

case TransformKind::Similarity:
case TransformKind::AxisScaled:
    return Basis3d::from_quat(orientation_)
         * Basis3d::from_scale(scale_);

case TransformKind::Affine:
    return basis_;
}
```

Expected consumer boundaries are:

```text
rendering and geometric bounds:
    affine() / linear_basis()

gameplay and cameras:
    translation() / orientation()

rigid physics:
    try_rigid_pose()

scale-aware volume components:
    component-owned dimensions plus an explicitly accepted transform class
```

There is no general exact `global_scale()` property. APIs that need an
approximation must name the policy, for example:

```text
axis_lengths
QR scale
principal stretches
```

## Inversion

Inversion follows the same promotion principle:

```text
inverse(Rigid)      -> Rigid
inverse(Similarity) -> Similarity
inverse(AxisScaled) -> generally Affine
inverse(Affine)     -> Affine
```

The inverse of an axis-scaled linear transform is:

```text
(R * D)^-1 = D^-1 * R^-1
```

and generally cannot be rewritten exactly as another `R' * D'`. Code must not
force the inverse back into TRS.

Singular scale remains a separate policy question. An exact inverse operation
must fail and log when the basis is not invertible.

## Global setters and reparenting

Logical orientation has a precise setter independent of shear:

```text
local.rotation =
    inverse(parent.orientation) * target_world_orientation
```

This changes the authored quaternion channel. It does not promise that the
orthogonal factor of the resulting affine basis equals the target quaternion.

World position can be set through the exact parent affine inverse when the
parent is invertible.

A complete target world affine transform requires:

```text
local_affine = inverse(parent_world_affine) * target_world_affine
```

The result may contain shear and therefore may not fit `LocalTransform3`.
Consequently, exact world-affine setters and reparent-with-world-preservation
must choose one explicit contract:

1. support an affine local representation;
2. reject a result not representable as local TRS and log the reason;
3. perform an explicitly named lossy projection.

Silent TRS decomposition is not acceptable.

## Current Termin mismatch

The current entity pool caches local and world position, quaternion and scale
separately, plus a world matrix. World values are composed as:

```text
world_rotation = parent_rotation * local_rotation
world_scale    = parent_scale component-wise multiplied by local_scale
world_matrix   = TRS(world_position, world_rotation, world_scale)
```

This treats TRS as closed. The cached world matrix is reconstructed from the
lossy world pose and therefore also loses shear. It is not an exact product of
the parent world matrix and local matrix.

Relevant implementation:

- `termin-scene/src/tc_entity_pool.c`;
- `termin-scene/cpp/geom/general_transform3.cpp`;
- `termin-render/src/drawable.cpp`.

The target invariant is:

```text
world affine == parent world affine * local TRS affine
```

`GeneralPose3::global_pose()` cannot be the canonical exact world value after
this change. It should be replaced or clearly exposed as a policy-based lossy
view.

## Storage boundary

This concept intentionally does not decide the physical cache layout.
Possible layouts include:

- an inline tagged value per entity;
- separate transform columns in ECS archetypes;
- a common compact decomposed value plus sparse affine payloads;
- an always-affine cache plus representation metadata.

The semantic model should be implemented and tested before choosing a more
complex sparse representation. A normal inline tagged union does not save
memory because it occupies the size of `Basis3d` plus common fields.

The local transform, world transform and logical orientation may also be
placed in archetype component columns if Termin adopts archetype systems as
the authoritative mutation path. That requires reliable per-row change
tracking before mutable queries can update transforms without leaving the
world cache stale.

## Verification

The core property test is:

```text
to_affine(compose(parent, local))
    approximately equals
to_affine(parent) * to_affine(local)
```

It must cover randomized and constructed cases for:

- rigid chains;
- uniform-scale chains;
- non-uniform parent scale followed by child rotation;
- multiple affine descendants;
- identity and axis-preserving rotations;
- negative scale according to the selected policy;
- near-singular and singular scale;
- inversion;
- dirty-subtree recomputation and demotion;
- logical orientation continuity across affine promotion.

Tests must also assert the advertised kind guarantees. A `Rigid`,
`Similarity` or `AxisScaled` result must reconstruct the same affine basis
without shear.

## Open decisions

1. Whether zero scale is rejected at authoring time or allowed as a
   non-invertible transform.
2. Whether negative scale is permitted in decomposed world states and how
   reflection signs are represented.
3. Whether importers may create authored local affine nodes for source formats
   that contain irreducible shear.
4. Whether `Similarity` classification requires positive scale.
5. Whether any axis-preserving non-uniform composition cases beyond identity
   rotation are worth retaining without promotion.
6. Whether logical orientation is cached inside the value or in a separate
   component column.
7. The eventual AoS, archetype-column or sparse affine-payload layout.
