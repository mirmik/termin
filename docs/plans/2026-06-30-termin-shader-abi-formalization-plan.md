# Termin Shader ABI Formalization Plan

Date: 2026-06-30
Kanboard: #85

## Status

Active implementation plan for the shader ABI direction documented in
`termin-graphics/docs/architecture/shader-resource-contracts.md`.

The goal is not to remove all well-known shader resource names. The goal is to
turn them into documented ABI and remove ad hoc name inference, private alias
lists, and backend placement decisions that depend on special resource names.

## Progress

- 2026-06-30: Added runtime shader ABI vocabulary in `termin-render`, made
  `draw_data` canonical, isolated `draw` as a documented legacy alias, and
  routed frame/material/draw/lighting/shadow runtime binding helpers through ABI
  lookup and validation.
- 2026-06-30: Added material-pipeline ABI boundary validation. Well-known ABI
  aliases are canonicalized before resource merge, and a well-known ABI name
  with incompatible kind/scope now reports an ABI contract diagnostic instead
  of becoming an unrelated resource.
- 2026-06-30: Promoted the ABI vocabulary to `termin-graphics` C API
  (`tc_shader_abi_*`) and made the `termin-render` C++ API a facade over that
  table. `termin_shaderc` now canonicalizes ABI aliases, assigns documented ABI
  scopes when reflection/source omits them, and rejects explicit ABI kind/scope
  mismatches before backend placement.

## Order Of Work

### 1. ABI Vocabulary

Add a small runtime-facing vocabulary for Termin shader ABI resources:

- canonical name;
- expected shader resource kind;
- expected scope;
- temporary aliases, if any.

This is not a new resource subsystem. It is the single source for validating
well-known ABI names and for isolating migration aliases such as `draw`.

Initial ABI resources:

- `per_frame`;
- `draw_data`;
- `material`;
- material texture property names;
- `bone_block`;
- `lighting`;
- `shadow_block`;
- `shadow_maps`.

### 2. Canonicalize Draw Data

Make `draw_data` the canonical draw-transform resource name. Keep `draw` only as
a documented legacy alias while old C macro/runtime paths are migrated.

Expected result:

- new contracts and shader sources use `draw_data`;
- compatibility lookup for `draw` is centralized;
- tests describe when `draw` is still accepted.

### 3. Runtime ABI Helpers

Move pass/runtime helpers from private name arrays to ABI-aware validation:

- lighting block;
- shadow block;
- shadow map array;
- frame constants;
- material UBO;
- draw data.

Expected behavior:

- canonical declaration with matching kind/scope binds normally;
- optional ABI resource omitted from a shader layout is skipped;
- wrong kind/scope logs an ABI diagnostic;
- required resource missing logs an ABI diagnostic;
- pass code does not try local historical aliases.

### 4. Parser And Material Bindings

Route parser-produced material/frame/draw requirements through the ABI
vocabulary instead of duplicating names, scopes, and aliases in multiple places.

Keep #20 separate for legacy GLSL fixed numeric binding retirement.

### 5. Compiler Boundary

`termin_shaderc` may validate documented ABI resources when it has enough
metadata, but must not invent semantic ownership for arbitrary names.

Compiler-side backend placement remains generic:

```text
scope + kind + stable logical name -> backend placement
```

It must not grow per-resource placement special cases.

### 6. Exporter And Catalog Boundary

Keep runtime package exporter and `engine-shader-catalog.json` ownership under
#161. The shader ABI work may expose catalog requirements, but should not fold
the exporter split into #85.

## First Slice

Implement the smallest useful cut:

1. Add ABI vocabulary and tests.
2. Make `draw_data` canonical with `draw` isolated as legacy alias.
3. Convert `shader_resource_apply.cpp` and nearby runtime helpers away from
   private alias arrays.

This slice should be testable on Linux and should not require Windows/D3D11
manual smoke.
