# D3D11 Backend Readiness Plan

Date: 2026-06-15

## Goal

Prepare Termin for a Direct3D 11 backend without leaking D3D register and
binding details into shader authorship, pass code, or higher-level
`termin_graphics` libraries.

This plan follows the live contract in
`termin-graphics/docs/architecture/shader-resource-contracts.md`:

```text
Shader source owns semantic resource declarations.
Pass and termin_graphics code own semantic resource production and binding.
termin_shaderc owns backend placement.
Runtime resolves names through the active shader layout.
Backends consume resolved placement.
```

The first milestone is not a full renderer. The first milestone is a reliable
D3D11 shader artifact and layout path that a future backend can consume.

## Current State

- Status update 2026-06-19: `create_device(BackendType::D3D11)` is wired on
  Windows when `TGFX2_ENABLE_D3D11` is enabled. The backend has a smoke-tested
  device, immediate command list, render pass clear, shader bytecode loading,
  graphics pipeline creation, resource set binding, `tc_shader` artifact
  loading, canonical `tc_texture`/`tc_mesh` materialization, and a
  `RenderContext2` fullscreen-quad path.
- Status update 2026-06-19: the Windows-only builtin shader matrix compiles
  82 Slang stages from `termin-graphics/resources/builtin_shaders` to D3D11
  `.cso` artifacts with real `slangc` and `fxc`, including layout sidecars.
- Status update 2026-06-19: project-builder and runtime-package export paths
  can explicitly request `shader_targets=["vulkan", "opengl", "d3d11"]`.
  D3D11 artifacts are emitted as `shaders/d3d11/<uuid>.vs.cso` and
  `shaders/d3d11/<uuid>.ps.cso`, and runtime manifests record the requested
  shader target requirements. The target wrappers and build profiles now pass
  the requested shader target list through to runtime package export, and the
  legacy direct desktop CLI accepts repeated `--shader-target` values. D3D11
  is still opt-in so Linux/Android builds do not require Windows SDK `fxc`.
- Status update 2026-06-20: a minimal DXGI/SDL window path exists through
  `D3D11Swapchain`. The swapchain exposes its backbuffer as a tgfx2
  `TextureHandle`, so existing `ICommandList` render passes can render into
  the presented target. It also supports an offscreen-present path through
  `compose_and_present(color_texture)`, currently implemented as an exact-size
  GPU copy into the backbuffer followed by `Present`. `tgfx2_d3d11_window`
  covers SDL HWND extraction, DXGI swapchain creation, offscreen render target
  clear, backbuffer copy/readback, and `Present`.
- Status update 2026-06-20: `termin::SDLBackendWindow` can now create D3D11
  primary and secondary windows when `TERMIN_BACKEND=d3d11` is selected. This
  keeps the editor/player model aligned with OpenGL and Vulkan: the engine
  renders into an offscreen tgfx2 texture, then `BackendWindow::present()`
  composes that texture into the window swapchain. `backend_window_d3d11_present`
  covers the window-level path without depending on shader pipeline support.
- `BackendType::D3D11` exists and `TERMIN_BACKEND=d3d11` / `dx11` parses.
- Runtime artifact paths already reserve `shaders/d3d11/<uuid>.<stage>.cso`
  with D3D stage suffixes such as `.vs.cso` and `.ps.cso`.
- `termin_shaderc --target d3d11` can produce `.cso` artifacts on Windows via
  the Slang-to-HLSL-to-FXC path.
- Slang shaders are already authored in a mostly HLSL-like style with semantic
  stage IO and logical resource declarations.
- `termin_shaderc` owns scope-first backend placement for migrated Slang
  artifacts and emits D3D11 register-class/index metadata for `.cso` sidecars.
- The current shader resource sidecar and `tc_shader_resource_binding` model
  expose D3D register class/index metadata, but editor/runtime coverage is
  still being expanded through the D3D11 backend.
- `RenderContext2` has bind-by-name paths for constant buffers, storage
  buffers, and sampled textures. Standalone samplers and storage textures need
  either first-class support or explicit MVP rejection.
- `ResourceBinding` has `set`, `binding`, `kind`, handles, offset, range, and
  array element. D3D11 can initially map `kind + binding + stage_mask` to
  register class/index, but this should be made explicit in layout metadata.

## D3D11 Binding Model

D3D11 does not have Vulkan-style descriptor sets. It has independent register
classes and stage-local binding APIs:

| Termin resource kind | D3D11 register class |
|---|---|
| `constant_buffer` | `b#` |
| `texture` / SRV buffer | `t#` |
| `sampler` | `s#` |
| `storage_buffer` / `storage_texture` | `u#` |

Therefore D3D11 backend placement should be represented as:

```text
stage_mask + register_class + register_index
```

For transition compatibility, `binding` may equal `register_index` and
`register_class` may be derived from `kind`. The sidecar schema should still
gain explicit D3D placement fields before the runtime backend depends on it.

## Phase 1: Freeze The Resource Contract

Tasks:

1. Treat `shader-resource-contracts.md` as the source of truth for new D3D11
   work.
2. Keep Slang source backend-neutral: no `register(...)`, no `[[vk::...]]`,
   no D3D-specific attributes in production shaders.
3. Keep pass and renderer code bind-by-name. Do not add D3D-specific resource
   binding branches above the backend layer.
4. Decide MVP support for standalone samplers and storage textures:
   implement them before backend work or reject them clearly in `termin_shaderc
   --target d3d11`.

Acceptance:

- New D3D11 work can be reviewed against one rule: semantic code above
  `termin_shaderc`/backend, concrete placement below it.
- Any remaining authored backend layout syntax in migrated Slang shaders is
  treated as migration debt or an explicit test fixture.

## Phase 2: Extend Layout Metadata For D3D11

Tasks:

1. Add an explicit backend-placement representation to layout sidecars. For
   D3D11, include `register_class` and `register_index`.
2. Keep the existing `set` and `binding` fields during migration so Vulkan and
   OpenGL loaders remain compatible.
3. Extend `tc_shader_resource_binding` or add a backend-placement companion
   structure so runtime code does not have to infer D3D register class from
   unrelated fields forever.
4. Bump the shader artifact layout schema version.
5. Update parser/loader validation to reject malformed D3D placement fields.

Candidate sidecar shape:

```json
{
  "name": "per_frame",
  "kind": "constant_buffer",
  "scope": "frame",
  "set": 0,
  "binding": 2,
  "stage_mask": 3,
  "d3d11": {
    "register_class": "b",
    "register_index": 2
  }
}
```

Acceptance:

- Existing Vulkan/OpenGL artifacts still load.
- D3D11 sidecars can represent `b#`, `t#`, `s#`, and `u#` without relying on
  string parsing in the backend.
- Stage-pair resource merges detect same-name resources with incompatible D3D
  placement.

## Phase 3: Add D3D11 Placement Allocation To `termin_shaderc`

Tasks:

1. Add a target-specific placement allocator for `--target d3d11`.
2. Reserve deterministic register ranges for Termin scopes and resource kinds.
3. Use `kind` to choose register class and scope/name policy to choose register
   index.
4. Reject unknown scopes for artifact-required migrated resources unless the
   resource is explicitly marked legacy/debug.
5. Reject overlaps within `(stage, register_class, register_index)`.
6. Keep diagnostics in semantic terms, for example:

```text
resource 'shadow_maps' is pass scope texture but overlaps material texture range
```

Acceptance:

- A representative shader matrix can produce D3D11 layout sidecars without
  producing bytecode yet.
- The same shader source gives deterministic D3D11 placement across runs.
- Vulkan/OpenGL placement behavior remains unchanged.

Representative shader matrix:

- material shader with `material` plus two material textures;
- postprocess shader with transient input/depth textures;
- skinned material variant with `bone_block`;
- pass shader with `per_frame`, `shadow_block`, and `shadow_maps`;
- simple UI/debug shader with draw-scope constants.

## Phase 4: Implement D3D11 Artifact Generation

Tasks:

1. Implement `termin_shaderc --language slang --target d3d11`.
2. Decide the toolchain path:
   - preferred MVP: Slang emits HLSL, then Windows SDK `fxc.exe` compiles DXBC
     `.cso`;
   - alternative if validated: Slang emits DXBC directly.
3. Ensure generated HLSL and compiled DXBC agree with the D3D11 placement
   sidecar.
4. Compile stage artifacts to:

```text
shaders/d3d11/<uuid>.vs.cso
shaders/d3d11/<uuid>.ps.cso
shaders/d3d11/<uuid>.gs.cso
```

5. Keep runtime/editor D3D11 free of Slang/FXC dependencies. Runtime consumes
   `.cso` and `.layout.json` only.

Acceptance:

- Fake-tool tests cover command construction, missing tool diagnostics, and
  failure propagation without requiring Windows SDK in ordinary CI.
- Windows smoke tests with real tools compile at least vertex+fragment Slang
  shaders to `.cso`.
- Generated D3D11 artifacts have matching layout sidecars.

## Phase 5: Runtime Layout And Binding Coverage

Tasks:

1. Teach `tc_shader_bridge` to parse the extended D3D11 layout metadata.
2. Make bind-by-name coverage match the resource kinds D3D11 MVP allows.
3. Add first-class symbolic binding support for standalone samplers if MVP
   allows separate samplers.
4. Add first-class symbolic binding support for storage textures/UAVs if MVP
   allows them. Otherwise reject them at shaderc/runtime load with clear
   errors.
5. Validate uploaded constant-buffer sizes against reflected sidecar sizes.
6. Keep stage masks available through the runtime resource layout so the D3D11
   backend can call VS/PS/GS binding APIs correctly.

Acceptance:

- Runtime can load `.cso.layout.json` and expose D3D placement metadata without
  a D3D11 device.
- Missing resource names, kind mismatches, and oversized constant buffers log
  clear errors.
- No new migrated path binds a numeric slot directly from pass code.

## Phase 6: D3D11 Backend Skeleton

Tasks:

1. Add build flags and platform guards for a Windows-only D3D11 backend.
2. Implement `D3D11RenderDevice` enough to create:
   - device/context;
   - swapchain or external render target path;
   - buffers;
   - textures;
   - samplers;
   - shader objects from `.cso` bytecode;
   - simple graphics pipelines;
   - command list abstraction or immediate-context bridge.
3. Wire `create_device(BackendType::D3D11)` to the implementation when built.
4. Keep feature gaps explicit in capabilities and logs.

Acceptance:

- `TERMIN_BACKEND=d3d11` creates a device on Windows when the backend is built.
- Non-Windows builds compile without D3D11 headers or libraries.
- Missing backend support fails with an actionable error, not an unresolved
  symbol or silent fallback.

## Phase 7: D3D11 Resource Binding Backend

Tasks:

1. Map resolved runtime resource bindings to D3D11 calls:
   - `VSSetConstantBuffers` / `PSSetConstantBuffers` / `GSSetConstantBuffers`;
   - `VSSetShaderResources` / `PSSetShaderResources` / `GSSetShaderResources`;
   - `VSSetSamplers` / `PSSetSamplers` / `GSSetSamplers`;
   - `CSSetUnorderedAccessViews` or graphics-stage UAV paths only if required.
2. Apply bindings per `stage_mask`.
3. Define the constant-buffer update strategy:
   - dynamic ring buffers;
   - per-draw upload buffers;
   - update-discard buffers.
4. Match existing `RenderContext2` offset/range behavior where D3D11 can
   support it. If a feature needs D3D11.1 `*SetConstantBuffers1`, gate it
   explicitly.
5. Ensure resource lifetime and deferred destruction match D3D11 immediate
   context usage.

Acceptance:

- A simple shader with `per_frame` and `draw_data` renders through bind-by-name.
- Stage-local register binding is correct when a resource appears only in VS or
  only in PS.
- Binding a resource not declared by the active shader does not leak stale D3D
  state into the draw.

## Phase 8: Pipeline, Vertex Input, And Render State

Tasks:

1. Map `PipelineDesc` to D3D11 input layout, shader stages, raster state,
   depth/stencil state, blend state, topology, and render-target formats.
2. Build input layouts from shader bytecode plus `VertexBufferLayout`.
3. Verify Termin's coordinate-system assumptions against D3D11 defaults:
   winding, depth range, texture origin, clip-space conventions, and matrix
   multiplication conventions.
4. Preserve backend-neutral frontend behavior. If D3D11 needs coordinate or
   texture-origin adaptation, hide it in the backend or shader artifact path.

Acceptance:

- A triangle smoke test renders with the expected orientation and depth.
- A textured quad smoke test samples the expected texels without pass-code
  backend branches.
- Existing `coord_system.md` D3D11 notes are either confirmed or updated.

## Phase 9: Smoke Tests And Packaging

Tasks:

1. Add Windows-only D3D11 artifact generation tests for built-in Slang shaders.
2. Add D3D11 device factory tests guarded by build/platform flags.
3. Add smoke tests:
   - clear only;
   - triangle;
   - textured fullscreen pass;
   - uniform-buffer transform;
   - simple material pass;
   - skinned or `bone_block` shader after basic material path works.
4. Extend runtime package/export paths to optionally include D3D11 artifacts.
   Status: optional D3D11 artifact output is wired for project-builder and
   runtime-package exporter APIs. Target wrappers, build profiles, and the
   legacy direct desktop CLI can now select explicit shader targets.
5. Add CI/build documentation for required Windows SDK tools.

Acceptance:

- SDK/package output can include `shaders/d3d11/*.cso` and matching sidecars.
- D3D11 tests are skipped cleanly on non-Windows hosts.
- D3D11 failures report missing backend, missing artifact, missing tool, or
  shader layout mismatch distinctly.

## Phase 10: Migration Follow-Through

Tasks:

1. Remove or quarantine D3D11-incompatible GLSL-only paths from D3D11 runtime
   packages.
2. Ensure remaining built-in shaders needed by default editor/runtime paths are
   Slang-backed or have D3D11 artifacts.
3. Add docs for writing D3D11-compatible Termin shaders. This should point to
   semantic contracts, not teach `register(...)`.
4. Revisit multi-set Vulkan and D3D register-space assumptions after D3D11 MVP
   proves the semantic model.

Acceptance:

- D3D11 can run a small real Termin scene without pass-level numeric binding
  branches.
- Shader authors and pass authors continue to use the same source/bind-by-name
  model across Vulkan, OpenGL, and D3D11.

## Non-Goals For MVP

- Do not implement D3D12-style register spaces.
- Do not require Slang, FXC, or DXC at runtime.
- Do not support authored production `register(...)` placement as the default
  shader authoring model.
- Do not port every legacy GLSL shader before the first D3D11 smoke. Port only
  the shaders needed for the selected smoke scenes.
- Do not implement Vulkan multi-set layouts as a prerequisite for D3D11.

## Immediate Next Steps

1. Run a real editor/player smoke with `TERMIN_BACKEND=d3d11` and a minimal
   scene whose shaders already have D3D11 `.cso` artifacts.
2. Add D3D11-friendly fullscreen/material smoke coverage above the clear-only
   window test, using runtime package shader artifacts instead of GLSL source.
3. Decide MVP resource-kind support for standalone samplers and storage
   textures, then reject or implement them consistently in shaderc and runtime.
4. Fill the remaining `RenderContext2` gaps needed by default editor/runtime
   passes, especially bind-by-name sampler handling if selected for MVP.
5. Revisit `D3D11Swapchain::compose_and_present()` scaling/format handling
   once a real scene exposes the engine output format contract.
