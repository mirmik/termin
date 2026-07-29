# Graded World Transform

Date: 2026-07-29.

Status: accepted architecture; exact primitives and graded entity cache implemented.

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

- This concept does not move authored local transforms into ECS archetypes.
- It does not require scalar decomposition of matrices for SIMD.
- It does not define automatic lossy projection from arbitrary affine values
  back to TRS.
- It does not make shear an ordinary authored property in the first version.

## Transform states

The world transform has four semantic states:

```text
Rigid       T * R
Similarity  T * R * uniform S
AxisScaled  T * R * non-uniform S
Affine      T * arbitrary Basis
```

`Rigid` is an element of `SE(3)`. `Similarity` adds a strictly positive uniform
scale and remains closed under composition. Zero and negative uniform scales
are classified as `AxisScaled`. `AxisScaled` is the single fragile decomposed
tier: it remains useful while scale axes are compatible with later rotations,
but promotes to `Affine` when they are not.

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

    // Logical scene-graph orientation.
    Quatd orientation_;

    // Exact for decomposed states and invalid for Affine.
    Vec3d scale_;

    // Exact geometric linear transform in every state.
    Basis3d basis_;

    TransformKind kind_;
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

The basis is materialized for every state. `kind` does not select an optional
storage payload; it declares which stronger operations and decomposed values
are valid.

## Logical orientation and geometric basis

`orientation` and `basis` deliberately have different meanings after affine
promotion:

```text
orientation = product of authored local quaternion channels
basis       = exact linear transformation of geometry
```

For `Rigid`, `Similarity` and `AxisScaled`, the stored basis must equal the
basis reconstructed from orientation and scale. For `Affine`, the stored basis
is still authoritative but need not equal `R(orientation) * D`.

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

`linear_basis()` returns the materialized exact basis:

```cpp
return basis_;
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

## Previous Termin mismatch

Before this migration, the entity pool cached local and world position,
quaternion and scale separately, plus a world matrix. World values were
composed as:

```text
world_rotation = parent_rotation * local_rotation
world_scale    = parent_scale component-wise multiplied by local_scale
world_matrix   = TRS(world_position, world_rotation, world_scale)
```

That treated TRS as closed. The cached world matrix was reconstructed from the
lossy world pose and therefore also lost shear.

Relevant implementation:

- `termin-scene/src/tc_entity_pool.c`;
- `termin-scene/cpp/geom/general_transform3.cpp`;
- `termin-render/src/drawable.cpp`.

The entity pool now maintains the target invariant:

```text
world affine == parent world affine * local TRS affine
```

`GeneralPose3::global_pose()` cannot be the canonical exact world value after
this change. Migrating that facade and its consumers remains the next stage.

## Selected cache layout

The entity pool keeps a fixed-capacity world cache for every entity. There is
one storage path and no optional per-entity allocation:

```c
Vec3* world_positions;
Quat* world_orientations;
Vec3* world_scales;
uint8_t* world_transform_kinds;
Vec3* world_basis_x;
Vec3* world_basis_y;
Vec3* world_basis_z;
```

The three basis columns always contain the exact linear world transform. This
materialized basis replaces the current 4x4 `world_matrices` cache; a consumer
that requires a 4x4 model matrix expands the basis columns and translation at
the API boundary.

The other columns retain stronger semantic information:

- `world_positions` is the exact affine translation and provides a direct hot
  path for position-only consumers;
- `world_orientations` is the logical quaternion channel;
- `world_scales` is exact only for `Rigid`, `Similarity` and `AxisScaled`;
- `world_transform_kinds` states which guarantees are valid.

`global_scale()` must not return the contents of `world_scales` for an
`Affine` entity. Callers must either require a decomposed transform or request
an explicitly named approximation.

Local authoring remains in the existing position, quaternion and scale
columns. Moving local transforms into ECS archetypes is a separate
architecture change and is not part of this migration.

## Implementation sequence

The migration is deliberately staged so that exact geometry becomes available
before the misleading TRS-shaped world API is removed.

### 1. Exact geometry primitives (implemented)

Add standard-layout `Basis3d` and `Affine3d` ABI types with:

- construction from quaternion and diagonal scale;
- exact composition;
- point and vector transformation;
- checked inversion with logged singular failure;
- conversion to and from the public 4x4 matrix convention.

The primitive tests establish matrix order and serve as the reference for
scene propagation.

### 2. Graded entity world cache (implemented)

Replace the lossy world-matrix cache with the fixed columns described above.
Dirty propagation must:

- classify roots from local scale;
- compose exact translation and basis;
- compose logical quaternion orientation independently;
- promote according to the graded state table;
- recompute state from current inputs so a subtree can demote;
- preserve the existing lazy-update contract.

The C entity-pool API exposes kind, exact basis/affine and exact 4x4 matrix
views. Existing local TRS storage and serialization do not change.

### 3. Exact `GeneralTransform3` operations

Move geometric operations to the exact world affine:

- point and vector transform;
- inverse point and vector transform;
- model and inverse-model matrix;
- geometric bounds helpers.

Keep logical operations on the quaternion channel:

- global orientation;
- forward, up and right;
- global orientation setters;
- rigid-pose extraction.

Add explicit `global_affine()`, `kind()` and `try_rigid_pose()` APIs.

### 4. Consumer migration

Migrate consumers by contract rather than mechanically replacing the type:

- rendering, bounds, mesh queries, voxelization and navmesh geometry use exact
  affine values;
- cameras, locomotion and editor orientation tools use position and logical
  orientation;
- rigid physics accepts only its documented transform class and logs rejected
  affine ancestry;
- code that needs scale chooses a decomposed-only or explicitly approximate
  API.

### 5. Editor setters and reparenting

Translation and logical rotation gizmos edit their individual channels.
World-preserving reparenting computes:

```text
new local affine = inverse(new parent world affine) * old world affine
```

The first implementation keeps authored locals as TRS. If the exact local
result contains irreducible shear, the operation is rejected and logged.
There is no implicit lossy decomposition. A separately named lossy editor
operation may be designed later if a concrete workflow requires it.

### 6. Remove misleading world TRS APIs

After all in-tree consumers are migrated:

- remove or rename exact-looking `GeneralPose3` composition and inverse
  operations that are only TRS projections;
- remove `global_pose()` as the canonical world value;
- remove unconditional `global_scale()`;
- keep deliberately lossy conversion only behind policy-named APIs.

The migration is complete when no exact geometric path reconstructs a world
transform from quaternion and component-wise scale.

## Implementation tracking

The project board tracks the migration as:

1. `#1058` - exact `Basis3d` and `Affine3d` geometry primitives;
2. `#1059` - graded exact entity world-transform cache;
3. `#1060` - exact geometric and logical `GeneralTransform3` APIs;
4. `#1061` - rigid physics, collision and FEM contract;
5. `#1062` - editor gizmos and world-preserving reparenting;
6. `#1063` - remaining geometric and runtime consumers;
7. `#1064` - removal of lossy world-TRS APIs.

The dependency graph is:

```text
#1058 -> #1059 -> #1060
                      |
                      +-> #1061 -+
                      +-> #1062 -+-> #1064
                      +-> #1063 -+
```

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

## Initial policy choices

1. Zero local scale is allowed. It produces a non-invertible transform;
   checked inverse operations fail and log. A zero uniform scale is classified
   as `AxisScaled`, not `Similarity`.
2. Negative local scale is allowed and its signs are retained in
   `AxisScaled`. Reflections are not folded into the logical quaternion.
3. `Similarity` requires a strictly positive uniform scale. A negative uniform
   scale is `AxisScaled`.
4. Authored local affine transforms are not supported in the first version.
   Importers must reject irreducible local shear or bake it into asset data
   under an importer-specific policy.
5. The initial promotion implementation recognizes identity local rotation as
   the only special commuting case for an `AxisScaled` parent. More cases may
   be added only with exact classification tests.
6. Logical orientation is stored in its own fixed world-cache column.
7. Exact names for decomposed-only scale access and supported approximations
   are ordinary API design within `#1060`; no approximation may use the
   unconditional name `global_scale`.
