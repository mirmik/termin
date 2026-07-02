# D3D11 Slang Scope Preservation Plan

Date: 2026-07-02

Related documents:

- `termin-graphics/docs/architecture/shader-resource-contracts.md`
- `termin-graphics/docs/architecture/pipeline-layout.md`
- `termin-graphics/docs/architecture/backend-binding-plan.md`
- `docs/plans/2026-06-11-slang-scope-first-binding.md`
- `docs/plans/2026-06-20-d3d11-runtime-placement-goal-plan.md`

## Problem Statement

D3D11 material shaders can lose authored `TerminScope` metadata for Slang
resources that are declared in imported modules and later lowered into generated
HLSL resources.

Observed case:

```text
termin_shadows.slang:
  [[TerminScope("pass")]]
  public Sampler2DShadow shadow_maps[MAX_SHADOW_MAPS];

D3D11 generated HLSL:
  Texture2D<float> shadow_maps_texture_0[16] : register(t0);
  SamplerComparisonState shadow_maps_sampler_0 : register(s0);

D3D11 sidecar:
  shadow_maps scope=unscoped
```

The runtime then rejects `shadow_maps` because `ShaderResourceApply` expects the
standard pass-scope shadow map resource, while the D3D11 sidecar describes it as
`unscoped`.

This is a shader compiler pipeline bug. If a Slang source or imported Slang
module declares `[[TerminScope(... )]]`, that scope must survive every backend
conversion and appear in the final artifact layout sidecar.

## Policy

Generated HLSL is not a source of shader semantics.

The source of truth for semantic resource metadata is:

```text
Slang source + imported Slang modules + Slang reflection metadata
```

Generated HLSL may be scanned only to recover backend-emitted symbols and native
D3D11 register declarations needed for patching/FXC compatibility. It must not
invent or assign logical resource ownership.

Rules:

- `TerminScope` authored in Slang must be preserved for all resources, including
  resources declared in imports.
- D3D11 HLSL augmentation must not assign scope from resource names such as
  `shadow_maps`, `lighting`, or `per_frame`.
- ABI-known names may be validated centrally, but they must not be used as the
  primary mechanism for scope recovery.
- Resources discovered only in generated HLSL with no source/reflection metadata
  must remain diagnostic cases, not silently become production `unscoped`
  resources for migrated artifact-required shaders.
- The final `.cso.layout.json` beside the compiled D3D11 artifact is the
  durable metadata product. No durable HLSL-side sidecar is planned while Slang
  to HLSL to CSO runs inside one `termin_shaderc` invocation.

## Target Pipeline

```text
Slang source + imports
  -> declared resource metadata
     (name, kind, scope, size/fields, stage mask)
  -> Slang target output
     - Vulkan: SPIR-V
     - D3D11: generated HLSL
  -> backend augmentation
     - Vulkan: descriptor decoration patching
     - D3D11: emitted HLSL symbol/register reconciliation
  -> final artifact + final layout sidecar
```

For D3D11, the augmentation step should reconcile generated HLSL declarations
against already-known declared resources:

```text
shadow_maps_texture_0 / shadow_maps_sampler_0
  -> logical resource shadow_maps
  -> existing declared metadata: kind=texture, scope=pass
  -> D3D11 placement: t#/s# and scalar_sampler_for_texture_array
```

It should not create a new semantic resource with `scope=unscoped` when the
resource was declared in Slang imports.

## Design Direction

### 1. Treat HLSL As A Non-Semantic Intermediate

Keep generated HLSL as a transient backend artifact. It may be retained by
`TERMIN_SHADERC_KEEP_INTERMEDIATE` for debugging, but it is not a public shader
contract and does not own semantic metadata.

D3D11 HLSL scanning should produce an internal emitted-resource view such as:

```text
emitted symbol/resource name
native declaration kind
register class/index
array/scalar sampler lowering facts
```

This emitted-resource view is matched onto the source/reflection metadata list.

### 2. Build Declared Resource Metadata Before Backend Augmentation

`termin_shaderc` should have an authoritative metadata list before any D3D11
HLSL augmentation runs. It should contain resources from:

- Slang reflection `parameters` and their `userAttribs`;
- entry source declarations that reflection omits but source scan can see;
- imported Slang modules when reflection omits imported scoped resources.

The important property is that `scope` comes from authored `TerminScope` or an
explicit compiler default supplied by the caller that owns the shader domain.

### 3. Add Import-Aware Slang Resource Metadata Collection

If Slang reflection for the D3D11 target omits imported resources or omits their
`userAttribs`, `termin_shaderc` should scan imported Slang modules enough to
collect declared resource metadata.

Minimal import scan requirements:

- resolve `import foo;` using the same include roots passed to Slang;
- read `.slang` modules from builtin shader include directories and source-local
  include paths;
- collect global resource declarations with optional `[[TerminScope(... )]]`;
- collect constant-buffer declarations and texture/sampler declarations used by
  current builtin modules;
- avoid following arbitrary filesystem paths outside configured include roots;
- avoid duplicate resources by logical name, with conflict diagnostics for
  incompatible kind/scope.

This scan should preserve source ownership. It must not infer scope from names.

### 4. Reconcile D3D11 Generated HLSL With Declared Metadata

Change `augment_d3d11_resource_bindings_from_hlsl()` so it no longer creates
semantic metadata from generated HLSL as the normal path.

Expected behavior:

- For every generated HLSL resource declaration, normalize the emitted symbol to
  a logical resource name using existing Slang lowering conventions
  (`*_texture_0`, `*_sampler_0`, `*_0`).
- If a matching declared resource exists, attach or update D3D11 placement and
  lowering facts on that resource.
- If no matching declared resource exists:
  - for legacy/non-migrated modes, keep current compatibility behavior only if
    explicitly needed and logged;
  - for migrated Slang artifact-required paths, fail with a diagnostic that the
    generated HLSL resource has no source metadata.
- Do not write `scope=unscoped` for a generated HLSL resource if authored scope
  was available in Slang source/imports.

### 5. Keep ABI Validation Separate

The shader ABI table remains useful for central validation of well-known engine
resources. It should check that resources such as `shadow_maps` have the
expected kind/scope when they are declared.

It must not become the scope assignment mechanism for D3D11 HLSL resources.

Allowed:

```text
source metadata says shadow_maps kind=texture scope=pass
ABI validation accepts it
```

Not allowed:

```text
HLSL scan found name shadow_maps with no scope
compiler assigns pass because shadow_maps is an ABI name
```

## Implementation Steps

1. Add a regression test that compiles a D3D11 Slang fragment shader importing
   `termin_shadows` and calling `compute_shadow_auto()`. The generated
   `.cso.layout.json` must contain `shadow_maps` with `scope=pass` and no
   warning about missing scope.
2. Add a matching Vulkan regression check, or extend an existing shaderc test,
   to document that Vulkan already preserves the imported `shadow_maps` scope.
3. Introduce an internal declared-resource metadata collection step for Slang
   sources/imports before D3D11 HLSL augmentation.
4. Update D3D11 HLSL augmentation to reconcile emitted HLSL declarations against
   declared metadata instead of creating scoped semantic resources from HLSL.
5. Add conflict tests:
   - imported resource and reflection resource disagree on scope;
   - imported resource and HLSL emitted declaration disagree on kind;
   - HLSL emitted declaration has no source metadata in migrated Slang mode.
6. Keep `TERMIN_SHADERC_KEEP_INTERMEDIATE` useful for debugging by leaving HLSL
   on disk, but do not introduce a durable `.hlsl.layout.json` sidecar unless
   Slang-to-HLSL and HLSL-to-CSO become separate CLI operations.
7. Rebuild SDK shader artifacts and verify editor material lighting no longer
   logs `shadow_maps` scope mismatches.

## Acceptance Criteria

- `CookTorrancePBR` D3D11 artifacts declare `shadow_maps` as `scope=pass`.
- `termin_shaderc` emits no missing-scope warning for `shadow_maps` when the
  scope is authored in `termin_shadows.slang`.
- `ShaderResourceApply` no longer logs
  `declares shadow_maps ABI resource 'shadow_maps' with kind=2 scope=6,
  expected kind=2 scope=2` for correctly compiled shaders.
- No new name-based scope inference is introduced in the shader compiler
  pipeline.
- D3D11 generated HLSL remains a backend intermediate, not an independent source
  of shader semantics.
- Existing Vulkan/OpenGL shaderc scope tests continue to pass.

## Focused Verification

```powershell
python -m pytest termin-graphics/tests/python/test_termin_shaderc_d3d11_cli.py
python -m pytest termin-graphics/tests/python/test_termin_shaderc_cli.py -k shadow
cmake --build build\Release-tests --config Release --target termin_shaderc
```

After SDK rebuild:

```powershell
.\build-sdk.ps1 --no-wheels
```

Then run the editor on a project using `CookTorrancePBR` and confirm the D3D11
log has no `shadow_maps` scope mismatch errors.

## Open Questions

- Should imported Slang resource scanning be implemented directly in
  `termin_shaderc`, or should it ask Slang for a richer reflection mode if one
  exists for imported declarations?
- Which shader categories are allowed to keep legacy generated-HLSL-only
  resources during migration, and should that be an explicit CLI flag?
- Should missing source metadata be a hard error for all `--language slang`
  D3D11 shaders, or only for artifact-required engine/material shaders?