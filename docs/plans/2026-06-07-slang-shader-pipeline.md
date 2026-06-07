# Slang Shader Pipeline Plan

Date: 2026-06-07

## Goal

Prepare the shader system for Slang-authored backend-neutral shaders. DirectX
11 is a later Windows-specific backend task; this plan focuses on the shader
tooling and runtime contracts needed before D3D11 can consume compiled shader
artifacts.

Runtime graphics backends must consume generated artifacts. They must not
compile Slang at runtime.

## Current State

- GLSL remains the only shader source language represented in `tc_shader`.
- `termin_shaderc` compiles GLSL to Vulkan SPIR-V through shaderc.
- Runtime/project export writes Vulkan artifacts under `shaders/vulkan/*.spv`.
- Vulkan can load precompiled SPIR-V through `TERMIN_SHADER_ARTIFACT_ROOT`.
- OpenGL compiles inline GLSL sources and does not load generated GLSL artifacts.
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

- Initial wrapper is implemented.
- Existing callers remain compatible: omitting `--language` defaults to
  `glsl`, and `glsl -> vulkan` still uses the in-process shaderc path.
- `slang -> vulkan` invokes external `slangc` with `-target spirv`.
- `slang -> opengl` invokes external `slangc` with `-target glsl`.
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
- OpenGL and Vulkan smoke paths render matching output.
- Legacy GLSL remains available until enough built-ins are migrated.

Status:

- Added Slang sources for `termin-runtime-default-color` under
  `termin-app/termin/resources/stdlib/slang/`.
- Runtime package export has an opt-in `default_shader_language="slang"` mode.
- Slang default export writes `.slang` source files plus Vulkan SPIR-V and
  OpenGL GLSL artifact paths through `termin_shaderc`.
- Android and Quest/OpenXR build wrappers forward the default shader language
  option, while keeping `glsl` as the default.
- Tests cover Slang default artifact layout and explicit rejection of an
  unsupported default shader language.
- Verified with `slangc` 2026.5.2 from the official GitHub release, installed
  as an external host tool under `~/soft` and exposed through `TERMIN_SLANGC`.
- Real `termin_shaderc` smoke checks compile the default shader to Vulkan SPIR-V
  and OpenGL GLSL, and runtime package export succeeds with
  `default_shader_language="slang"`.
- Remaining work: hook one smoke path that actually consumes the generated
  OpenGL/Vulkan artifacts and validates the matrix convention at render time.

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

1. Finish the ABI/doc cleanup.
2. Generalize artifact lookup without changing shader source language.
3. Add shader language metadata.
4. Add Slang-aware `termin_shaderc` command-line path.
