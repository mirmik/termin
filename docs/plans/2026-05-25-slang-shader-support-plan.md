# Slang Shader Support Plan

Date: 2026-05-25

## Goal

Add Slang shader support alongside the existing GLSL shader path without
rewriting the engine immediately. Backends should consume generated artifacts;
the shader source language should stay outside backend runtime logic.

## M0: Fix The Shader ABI

Document one binding/register contract shared by all backends:

- Constant buffers / UBOs: `b0`, `b1`, `b2`, `b3`, `b16`.
- Textures: `t4` through `t15`.
- Samplers: `s0` and up.
- Small per-draw data: native push constants on Vulkan, dynamic constant/UBO
  emulation on OpenGL and D3D11.

The document must map the same ABI to:

- OpenGL `layout(binding=N)`.
- Vulkan descriptor bindings.
- D3D11 `register(bN/tN/sN)`.

This should live in `docs/` or `termin-graphics/docs/architecture/` and be
treated as the compatibility contract for every shader compiler target.

## M1: Generalize The Artifact Loader

Replace the current Vulkan-only artifact loader with a backend-aware one.

Current path:

```text
shaders/vulkan/<uuid>.<stage>.spv
```

Target paths:

```text
shaders/opengl/<uuid>.vert.glsl
shaders/opengl/<uuid>.frag.glsl
shaders/vulkan/<uuid>.vert.spv
shaders/vulkan/<uuid>.frag.spv
shaders/d3d11/<uuid>.vs.cso
shaders/d3d11/<uuid>.ps.cso
```

Behavior:

- If the backend artifact exists, use it.
- If it does not exist, keep the existing GLSL fallback for legacy shaders.
- Slang shaders should require artifacts in packaged/runtime builds.

## M2: Add Shader Language Metadata

Add minimal language metadata to `tc_shader`:

```c
TC_SHADER_LANGUAGE_GLSL
TC_SHADER_LANGUAGE_SLANG
TC_SHADER_LANGUAGE_HLSL
```

Rules:

- Existing `tc_shader_from_sources(...)` keeps creating GLSL shaders.
- Add a path for shader assets that have a manifest/source path and language.
- Avoid overloading `vertex_source` / `fragment_source` with generated text
  without recording where it came from.

## M3: Add OpenGL Artifact Loading

Teach the OpenGL backend to load generated GLSL artifacts:

- Try `shaders/opengl/<uuid>.<stage>.glsl`.
- If absent, compile the existing source through `glShaderSource` as today.

This lets Slang shaders run on OpenGL while preserving all current GLSL shaders.

## M4: Add A Slang Build Step

Add either a new mode to `termin_shaderc` or a separate shader builder tool:

```text
compile --language slang --target opengl|vulkan|d3d11
```

First implementation can invoke external `slangc`.

Initial supported inputs:

- Vertex stage.
- Fragment stage.
- Entry point names.
- Include paths.
- Debug name.
- Output path.

## M5: Integrate Project Build

Extend `termin-app/termin/project_builder/shader_build.py`:

- GLSL assets continue through the current GLSL-to-SPIR-V path.
- Slang assets compile to OpenGL GLSL and Vulkan SPIR-V first.
- D3D11 DXBC artifacts are added when the D3D11 backend work starts.
- The resource manifest records language and generated artifacts.

## M6: First Slang Shader

Start with a small shader, not the material pipeline.

Recommended first candidate:

- Fullscreen quad / blit shader.

Validation:

- Generated OpenGL GLSL compiles.
- Generated Vulkan SPIR-V loads.
- Pixel output matches between OpenGL and Vulkan.

## M7: Migrate A Minimal Built-in Set

After the first shader works, migrate built-ins one by one:

1. Fullscreen quad / present.
2. Immediate renderer.
3. Text2D.
4. Canvas2D.
5. Gizmo/highlight or ID pass.

Each migrated shader needs an OpenGL and Vulkan smoke path.

## M8: Prepare D3D11

After M1 through M7:

- Add `d3d11` target to the shader builder.
- Generate `.cso` artifacts through Slang's DXBC target.
- The D3D11 backend consumes artifacts only; it does not compile Slang at
  runtime.

## Migration Rules

- Do not rewrite existing GLSL without need.
- New backend-neutral shaders should be written in Slang.
- A Slang shader without artifacts is a build/package error.
- Runtime source fallback is allowed only for GLSL/dev mode.
- Do not mix hand-written GLSL and Slang inside the same shader asset.

## Main Risk

The main risk is not Slang itself. The main risk is ABI drift: constant buffer
layout, texture slots, sampler slots, and push-constant emulation must match
across all targets. M0 and the first pixel-output test are critical; without
them Slang becomes a third shader variant instead of removing variants.
