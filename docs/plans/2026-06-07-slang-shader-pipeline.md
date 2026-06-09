# Slang Shader Pipeline Plan

Date: 2026-06-07

## Goal

Prepare the shader system for Slang-authored backend-neutral shaders. DirectX
11 is a later Windows-specific backend task; this plan focuses on the shader
tooling and runtime contracts needed before D3D11 can consume compiled shader
artifacts.

Runtime graphics backends must consume generated artifacts. They must not
compile Slang at runtime. Vulkan is the primary Linux development and test
path; OpenGL coverage is kept as compatibility/legacy coverage.

## Current State

- GLSL remains the only shader source language represented in `tc_shader`.
- `termin_shaderc` compiles GLSL to Vulkan SPIR-V through shaderc.
- Runtime/project export writes Vulkan artifacts under `shaders/vulkan/*.spv`.
- Vulkan can load precompiled SPIR-V through `TERMIN_SHADER_ARTIFACT_ROOT`.
- OpenGL compiles inline GLSL sources and is no longer the primary Slang
  validation path.
- `slangc`, Slang libraries, DXC, and FXC are not currently vendored into the
  repo or SDK.
- D3D11 already exists as a `BackendType` enum value and env alias, but the
  backend implementation is not present.

## Toolchain Policy

Initial Slang support should use external tools:

- `slangc` found through `TERMIN_SLANGC`, then `PATH`, then an optional SDK
  tool location.
- D3D11 artifact generation is Windows-only and requires Windows SDK `fxc.exe`
  unless a later Slang/toolchain update gives us a better DXBC path.
- Matrix layout must be explicit for Slang command-line compilation. Termin
  accepts both row-major and column-major layouts where a shader/backend path
  can support them, but the preferred default is column-major because the
  existing GLSL/Vulkan shader ABI and transform code are written in
  `mat4 * vec4` style. This policy is expressed in Termin artifact/ABI terms;
  if a Slang release uses target-specific or inverted CLI flag semantics, the
  `termin_shaderc` wrapper must adapt those details. Row-major remains an
  opt-in compatibility mode and must be validated with render smoke coverage
  before use in built-ins.
- Slang/HLSL `mul` syntax must be treated as a separate convention from
  storage layout. For Termin's preferred GLSL-style `M * v` transform semantics
  with column-major host matrices, Slang shaders should write `mul(M, v)`.
  Generated GLSL/SPIR-V may express this as a transposed-looking operation plus
  a target-specific matrix layout decoration; do not infer Termin's host ABI
  from emitted `RowMajor`/`ColMajor` decorations alone.

The first implementation should not vendor Slang. Vendoring can be considered
after the command-line integration and artifact contracts are stable.

## Phase 1: Shader ABI Contract

Make the shared shader ABI a live contract before introducing Slang.

Tasks:

- Update `docs/gpu-pipeline-layout.md` with explicit D3D11 register mapping.
- Keep the Vulkan/OpenGL binding table in sync with
  `VulkanRenderDevice::create_shared_layouts()`.
- Document push-constant emulation for OpenGL and D3D11.
- Remove stale comments that mention old bindings.

Acceptance:

- One document maps every shared UBO/texture/sampler slot to GLSL/Vulkan and
  Slang/HLSL register syntax.
- The document no longer contradicts the Vulkan shared layout.

## Phase 2: Backend-Aware Artifact Loader

Replace the current Vulkan-only artifact lookup with backend-aware lookup.

Target paths:

```text
shaders/opengl/<uuid>.vert.glsl
shaders/opengl/<uuid>.frag.glsl
shaders/vulkan/<uuid>.vert.spv
shaders/vulkan/<uuid>.frag.spv
shaders/d3d11/<uuid>.vs.cso
shaders/d3d11/<uuid>.ps.cso
```

Rules:

- If a matching artifact exists, the backend uses it.
- GLSL shaders may fall back to inline source in dev/editor mode.
- Slang shaders require artifacts in packaged/runtime builds.

Acceptance:

- Vulkan behavior stays compatible with existing packages.
- OpenGL can load generated GLSL artifacts before falling back to inline GLSL.
- Missing artifacts are logged with backend, shader UUID, stage, and expected
  path.

## Phase 3: Shader Language Metadata

Add source-language metadata to `tc_shader`.

Initial values:

```c
TC_SHADER_LANGUAGE_GLSL
TC_SHADER_LANGUAGE_SLANG
TC_SHADER_LANGUAGE_HLSL
```

Also add an artifact requirement policy or equivalent state so runtime code can
distinguish legacy GLSL fallback from Slang artifact-only shaders.

Acceptance:

- Existing `tc_shader_from_sources` style APIs create GLSL shaders by default.
- Material phases, hot reload, Python bindings, and runtime package loading
  preserve language metadata.
- Slang shaders without required artifacts fail loudly instead of silently
  compiling stale/generated source.

## Phase 4: `termin_shaderc` Frontend Generalization

Extend `termin_shaderc` from a GLSL-to-SPIR-V tool into a shader build wrapper.

Target CLI shape:

```text
termin_shaderc compile \
  --language glsl|slang \
  --target opengl|vulkan|d3d11 \
  --stage vertex|fragment|geometry \
  --entry main \
  --input <path> \
  --output <path>
```

Implementation order:

1. Preserve current `glsl -> vulkan` behavior.
2. Add `slang -> vulkan` by invoking `slangc`.
3. Add `slang -> opengl` by invoking `slangc` for GLSL output.
4. Add Windows-only `slang -> d3d11`: generate HLSL if needed, then compile
   VS/PS to DXBC `.cso` with `fxc.exe`.

Acceptance:

- Tests cover argument parsing, missing tool diagnostics, and compiler failure
  propagation.
- Fake compiler tests cover all targets without requiring Slang in CI.

Status:

- Added `@language glsl|slang` to the `.shader` DSL and carried the parsed
  language through `ShaderMultyPhaseProgramm`, `ShaderAsset`, `MaterialAsset`,
  and `TcMaterial.add_phase_from_sources()`.
- Added first stdlib material shader written in Slang:
  `stdlib/shaders/SlangNormalColor.shader` plus
  `stdlib/materials/SlangNormalColor.material`.
- The first material is intentionally small: it uses HLSL/Slang resource
  syntax for the ColorPass `PerFrame` UBO (`register(b2, space0)`) and
  per-draw model data (`SlangDrawData` at `register(b24, space0)`), then
  colors fragments from transformed normals. Binding 24 is a dedicated dynamic
  UBO slot for Slang/HLSL material draw data, separate from legacy GLSL
  push-constant injection.
- `termin_shaderc` maps HLSL `register(b/t/sN, spaceM)` declarations to
  Vulkan/OpenGL descriptor bindings with zero `-fvk-*-shift` values, so stdlib
  Slang sources do not need `[[vk::binding]]` for ordinary resources.
- Slang `.shader` stages bypass GLSL include/preprocess/material-UBO rewrite.
  `@property` on Slang `.shader` files is rejected for now so we do not
  accidentally synthesize a GLSL ABI into Slang source.
- Tests cover language parsing, rejection of Slang material properties, and
  stdlib material creation producing `TC_SHADER_LANGUAGE_SLANG`.
- Real `termin_shaderc` smoke checks compile the extracted Slang stages to
  Vulkan SPIR-V and OpenGL GLSL with the external `slangc`.

Remaining:

- Define the Slang-native material property/UBO contract instead of relying on
  the GLSL rewriter.
- Resolve the Slang matrix ABI before porting real materials: with
  `slangc 2026.5.2`, generated Vulkan artifacts currently decorate
  `ConstantBuffer` matrices as `RowMajor` even when the source and CLI request
  column-major. Keep `mul(M, v)` in source, but verify the runtime data layout
  before relying on this for PBR/skinning.
- Add runtime/editor artifact generation for stdlib `.shader` assets so this
  material can be used without manual lazy compilation setup.
- Add render smoke coverage that actually draws `SlangNormalColor` through
  ColorPass on Vulkan.

- Initial wrapper is implemented.
- Existing callers remain compatible: omitting `--language` defaults to
  `glsl`, and `glsl -> vulkan` still uses the in-process shaderc path.
- `slang -> vulkan` invokes external `slangc` with `-target spirv`.
- `slang -> opengl` invokes external `slangc` with `-target glsl`.
- Slang compilation now passes an explicit matrix layout flag; column-major is
  the default and row-major is available through an opt-in CLI switch.
- `slang -> d3d11` is intentionally rejected until the Windows FXC/DXBC phase.
- Tests use a fake `slangc` and cover Vulkan/OpenGL invocation, missing tool
  diagnostics, compiler failure propagation, unsupported GLSL targets, and the
  reserved D3D11 path.

## Phase 5: Project Build And Runtime Export

Extend project/runtime packaging to record language and artifacts.

Manifest direction:

```json
{
  "uuid": "...",
  "language": "slang",
  "artifacts": {
    "opengl": {"vertex": "...vert.glsl", "fragment": "...frag.glsl"},
    "vulkan": {"vertex": "...vert.spv", "fragment": "...frag.spv"}
  }
}
```

Rules:

- GLSL assets keep the current Vulkan SPIR-V path.
- Slang assets generate OpenGL GLSL and Vulkan SPIR-V first.
- D3D11 artifacts are generated only when running a Windows/D3D11 packaging
  profile.

Acceptance:

- Existing runtime package tests still pass.
- New tests assert backend artifact paths and language metadata.

Status:

- Project build shader usage export recognizes `shader.language`.
- GLSL usages preserve the existing Vulkan-only SPIR-V artifact layout.
- Slang usages generate Vulkan SPIR-V and OpenGL GLSL artifacts through
  `termin_shaderc`.
- Runtime package shader JSON now records `language` and an `artifacts` map.
- Runtime export writes Slang source files with `.slang` extension and emits
  both `shaders/vulkan` and `shaders/opengl` artifacts.
- Remaining work: parse/author `.shader` or `.slang` assets with language
  metadata instead of only setting it through live `TcShader`.

## Phase 5.5: Editor Lazy Dev Compilation

Keep packaged runtimes artifact-only, but let the editor work lazily while
shader sources are being authored.

Ownership:

- `termin-graphics` owns the runtime decision: load an artifact, check whether
  it matches the current `tc_shader` identity, or invoke `termin_shaderc` in
  dev mode.
- Backends only ask for a backend/stage artifact and consume the resulting
  bytes or source.
- Python/editor code only configures runtime paths and policy: artifact root,
  cache root, `termin_shaderc` path, and whether dev compilation is enabled.
- Build/package scripts still produce deterministic artifacts for SDK/runtime
  packages and must not rely on runtime compilation.

Status:

- `tgfx2_load_or_compile_shader_artifact_for_backend()` now lives in
  `termin-graphics` and is used by Vulkan and OpenGL `ensure_tc_shader()`.
- Dev compilation is disabled by default. It can be enabled through C++ API or
  `TERMIN_SHADER_DEV_COMPILE=1`.
- Runtime configuration can come from explicit C++/Python calls or env vars:
  `TERMIN_SHADER_ARTIFACT_ROOT`, `TERMIN_SHADER_CACHE_ROOT`, and
  `TERMIN_SHADERC`.
- The dev compiler writes source snapshots under `cache/source/`, backend
  artifacts under the configured artifact root, and a sidecar metadata file
  containing shader hash, language, target, stage, UUID, and version.
- Metadata is used to avoid recompiling unchanged shader/stage/target
  artifacts on repeated editor draws.
- `tgfx2_device_factory_test` covers the lazy compile path with a fake
  `termin_shaderc` and verifies that a second load reuses the cached artifact.
- The tcgui editor now configures shader runtime on project load:
  project-local artifacts go under `.termin/shader-artifacts`, source/cache data
  under `.termin/shader-cache`, `termin_shaderc` is resolved from
  `TERMIN_SHADERC`, `TERMIN_SDK`, local SDK, or `PATH`, and dev compilation is
  enabled for the editor session.
- Vulkan/OpenGL `ensure_tc_shader()` no longer falls back to compiling non-GLSL
  source directly when artifact/lazy compilation fails; that path now reports a
  non-GLSL artifact/dev-compile error instead of surfacing misleading GLSL
  syntax errors on Slang tokens.

Remaining work:

- Decide whether hot reload should remove stale artifacts eagerly or rely on
  metadata mismatch and overwrite-on-demand.
- Extend the lazy path to future D3D11 artifacts after the Windows
  `termin_shaderc --target d3d11` phase exists.

## Phase 6: First Slang Shader

Start with a small engine shader, not the material pipeline.

Original recommended candidate:

- fullscreen quad / blit / present shader.

Implemented first candidate:

- runtime default color fallback shader.

Rationale:

- It already flows through runtime package shader JSON and the backend artifact
  map introduced in Phase 5.
- It can be enabled explicitly by packaging code/tests without making Linux or
  Android builds require a host `slangc` by default.
- The default pipeline engine shaders are still GLSL/Vulkan-only and should be
  migrated as a separate renderer-facing step.

Acceptance:

- One `.slang` source produces OpenGL GLSL and Vulkan SPIR-V artifacts.
- Vulkan smoke renders the generated Slang artifact path. OpenGL coverage is
  compatibility coverage and must not block Vulkan-first Slang migration.
- Legacy GLSL remains available until enough built-ins are migrated.

Status:

- Added Slang sources for `termin-runtime-default-color` under
  `termin-app/termin/resources/stdlib/slang/`.
- Runtime package export has an opt-in `default_shader_language="slang"` mode.
- Slang default export writes `.slang` source files plus Vulkan SPIR-V and
  OpenGL GLSL artifact paths through `termin_shaderc`.
- The opt-in Slang default shader now uses Slang semantics for stage
  inputs/outputs instead of `[[vk::location]]`. Resource binding attributes
  remain until the Slang resource layout ABI is defined.
- Android and Quest/OpenXR build wrappers forward the default shader language
  option, while keeping `glsl` as the default.
- Tests cover Slang default artifact layout and explicit rejection of an
  unsupported default shader language.
- Verified with `slangc` 2026.5.2 from the official GitHub release, installed
  as an external host tool under `~/soft` and exposed through `TERMIN_SLANGC`.
- Real `termin_shaderc` smoke checks compile the default shader to Vulkan SPIR-V
  and OpenGL GLSL, and runtime package export succeeds with
  `default_shader_language="slang"`.
- OpenGL `tgfx2_smoke` covers the legacy runtime artifact-consumption contract:
  a `TC_SHADER_LANGUAGE_SLANG` shader with `TC_SHADER_ARTIFACT_REQUIRED` loads
  backend artifacts from `TERMIN_SHADER_ARTIFACT_ROOT`, builds a pipeline, and
  renders from the artifact sources instead of fallback sources.
- Vulkan `tgfx2_vulkan_smoke` now has an optional generated-Slang artifact
  render path. When `termin_shaderc` and `slangc` are available, it writes a
  temporary Slang vertex/fragment pair, compiles Vulkan SPIR-V artifacts, loads
  them through `TC_SHADER_ARTIFACT_REQUIRED`, binds a column-major matrix UBO,
  and validates the expected rendered pixels.
- Vulkan is now the default `run-tests.sh` C++ profile, so
  `tgfx2_vulkan_smoke` is part of the regular Linux test loop when Vulkan
  dependencies are installed. `--no-vulkan` remains available for explicit
  OpenGL/legacy compatibility checks.

## Phase 7: Minimal Built-In Migration

Migrate small built-ins one at a time:

1. Fullscreen / present.
2. Immediate renderer.
3. Canvas2D.
4. Text2D.
5. ID/debug/simple post-process shaders.

Defer material, PBR, lighting, and skinning until the artifact pipeline is
stable.

Acceptance:

- Each migrated shader has OpenGL and Vulkan coverage.
- No shader asset mixes hand-written GLSL and Slang as parallel source
  variants.

Status:

- First Vulkan FSQ artifact smoke is in place. `tgfx2_vulkan_smoke` now
  generates a temporary Slang vertex shader artifact at
  `shaders/vulkan/termin-engine-fsq.vert.spv`, sets
  `TERMIN_SHADER_ARTIFACT_ROOT`, and verifies that
  `RenderContext2::draw_fullscreen_quad()` consumes that artifact instead of
  the built-in GLSL fallback. The test compiles the canonical built-in FSQ
  Slang source and validates the expected center UV output.
- This proves the smallest built-in path works through
  `slangc -> termin_shaderc -> Vulkan SPIR-V -> RenderContext2 artifact load`.
  The first canonical source/export wiring now follows the same path.
- Added a built-in shader catalog contract in `docs/builtin-shader-catalog.md`.
  Runtime metadata for the first entry lives in
  `tgfx2/engine_shader_catalog.hpp`, and the canonical FSQ Slang source lives
  under `termin-graphics/resources/builtin_shaders/`.
- Runtime package export now treats the FSQ built-in as a Slang engine shader:
  it writes the `.slang` source snapshot, generates Vulkan SPIR-V, and also
  generates the OpenGL GLSL artifact for that stage.
- The Vulkan smoke now compiles the canonical FSQ Slang source instead of a
  test-only source string.
- The FSQ Slang source now relies on Slang/HLSL semantics rather than
  `[[vk::location]]`, keeping the source backend-neutral for this safe stage.
- Shadow, debug triangle, present blit, immediate renderer, Canvas2D, Text2D,
  Text3D, screen-space lines, world-space lines, world tube lines, base id,
  `LineRenderer` default material, runtime package default color,
  `FoliageLayerComponent` instanced vertex templates, normal, depth/depth-only,
  depth/color conversion, skybox, highlight, gizmo mask, ground grid, editor
  solid primitives, grayscale, bloom, and tonemap built-ins are now
  catalog-managed sources.
  Skybox remains a `.shader`
  program so the existing material UBO parser owns its generated GLSL stage
  layout. The resource-using entries carry logical resource metadata and
  explicit `legacy_binding` values. They are not migrated to Slang yet because
  texture resources, material UBO generation, and the current GL push-constant
  bridge still depend on numeric binding slots.
- `ShadowPass`, `DebugTrianglePass`, `IdPass` base shader, `NormalPass`,
  `DepthPass`, `DepthOnlyPass`, `DepthToColorPass`, `ColorToDepthPass`,
  `LineRenderer` default material, `SkyBoxPass`, `GrayscalePass`, `BloomPass`,
  and `TonemapPass` now register their live shaders from the built-in shader
  resource files. Default-pipeline package artifact generation uses the same
  catalog source files for built-ins that it exports.
- Those passes now resolve live shader names, source filenames, and stage
  shapes from `engine-shader-catalog.json` by stable UUID. Individual passes no
  longer duplicate catalog metadata for migrated built-ins.
- `LineRenderer` material fragment variants still derive from the active
  material fragment source at runtime. That remains material-pipeline work, not
  an engine built-in shader source migration.
- `FoliageLayerComponent` foliage variants now load their engine-authored
  vertex stage templates from the catalog and still combine them with the active
  material fragment source at runtime.
- `runtime_package_exporter` now builds the GLSL default color shader from the
  built-in shader catalog instead of keeping inline GLSL strings in Python.
- ResolvePass no longer has min/max shader variants. It resolves through the
  backend average path only; `strategy` remains as a serialized compatibility
  field and logs when an obsolete value is used.
- The live catalog/source loader moved down into `termin_graphics2`
  (`tgfx2/builtin_shader_sources.hpp`) so both engine renderers and
  render-passes use one shared catalog API instead of a render-pass-local
  helper.

## Phase 8: D3D11 Artifact Preparation

This phase starts only when working under Windows.

Tasks:

- Add `d3d11` target to `termin_shaderc`.
- Generate `.vs.cso` and `.ps.cso` artifacts.
- Verify HLSL register usage against `docs/gpu-pipeline-layout.md`.
- Keep D3D11 runtime free of Slang/FXC dependencies.

Acceptance:

- D3D11 shader artifacts are packaged under `shaders/d3d11/`.
- A future D3D11 backend can load bytecode blobs directly.

## Immediate Next Steps

1. Audit the remaining runtime/exporter inline engine shader strings and move
   the next isolated one into the built-in shader catalog.
2. Keep texture-using post-process built-ins catalog-managed as GLSL until the
   bind-by-name/runtime layout plan can carry their resource metadata.
3. Replace remaining runtime exporter inline engine shader strings with catalog
   entries as each source migrates.
4. Define the Slang-native material ABI before enabling `@property` on Slang
   `.shader` files: generated `MaterialParams : register(b1)`, texture register
   mapping, and include/module support in `termin_shaderc`.
5. Decide later how generated Slang OpenGL artifacts should target the existing
   GL smoke environment: request a GL 4.5 context, lower Slang GLSL output if
   the toolchain supports it, or keep OpenGL generated-artifact rendering as a
   separate higher-requirement smoke.
6. Keep D3D11 work Windows-only and start it after Slang artifacts have a stable
   Linux-side generation and runtime-consumption contract.
