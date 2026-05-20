# External Render Target Resources in Framegraph Pipelines

## Problem

Framegraph pipeline output is currently represented by special resource names such as `OUTPUT` and `DISPLAY`.
Runtime execution treats those names as external render target textures, but graph analysis and FBO introspection can
still treat them as ordinary internal framegraph resources. This allows invalid aliases such as:

```text
OUTPUT == fbo_1
```

The intended relationship is different:

```text
RT_COLOR == current RenderTarget.color texture
RT_DEPTH == current RenderTarget.depth texture
```

Internal FBOs keep their own allocation and format. External render target textures are provided by the render target
that executes the pipeline.

## Target Model

Render target textures enter the graph explicitly as external resources:

```text
RenderTargetInput.color -> RT_COLOR
RenderTargetInput.depth -> RT_DEPTH
```

The final output node only marks pipeline completion:

```text
PipelineOutput.color <- some resource
PipelineOutput.depth <- some resource
```

`PipelineOutput` does not allocate textures, copy/blit data, or rewrite resource names. If a copy into the render
target is needed, the pipeline author adds an explicit pass:

```text
fbo_1 -> BlitPass(input_res=fbo_1, output_res=RT_COLOR)
RT_COLOR -> PipelineOutput.color
```

If a pass can write directly to the render target texture, it uses `RT_COLOR` as its output:

```text
RT_COLOR -> InplacePass(input_res=RT_COLOR, output_res=RT_COLOR)
RT_COLOR -> PipelineOutput.color
```

## Rules

- `RT_COLOR` and `RT_DEPTH` are external resources bound to the current render target.
- External resources are not allocated by `FBOPool`.
- Internal resources may alias other internal resources.
- External resources must not be canonicalized to internal FBOs.
- No implicit blit is inserted by the compiler.
- Blits/copies into render target textures are explicit graph passes.
- Framegraph Debugger must show the actual runtime texture behind an external resource.
- Legacy `OUTPUT`/`DISPLAY` may remain as compatibility aliases during migration, but new graph authoring should use
  explicit external resources.

## Migration Plan

1. Add compiler/runtime support for external resource names:
   - `RT_COLOR`
   - `RT_DEPTH`
   - temporary compatibility: `OUTPUT`, `DISPLAY`
2. Add graph nodes:
   - `RenderTargetInput` with outputs `color`, `depth`
   - `PipelineOutput` with inputs `color`, `depth`
3. Update graph compiler:
   - register `RenderTargetInput` outputs as external resources
   - stop rewriting upstream pass outputs to `OUTPUT`
   - make `PipelineOutput` a validation/completion marker only
   - keep legacy output-node handling behind compatibility logic
4. Update `RenderEngine`:
   - map external color resources to `ViewportContext.output_color_tex`
   - map external depth resources to `ViewportContext.output_depth_tex`
   - skip `FBOPool` allocation for external resources
5. Update Framegraph Debugger:
   - list external resources as resources
   - show real runtime texture info for external resources
   - keep internal FBO info from `FBOPool`
6. Rewrite built-in pipelines:
   - Default pipeline
   - Editor pipeline
7. Migrate saved `.pipeline` graph files:
   - old `RenderTarget` output nodes become `PipelineOutput`
   - add `RenderTargetInput`
   - insert explicit blit/copy pass when old graph expected an implicit final write
8. Add tests:
   - compiler does not alias external resources to internal FBOs
   - external resources are not allocated by `FBOPool`
   - debugger reports external resource format from the actual render target texture
   - Default and Editor pipelines finish through explicit external resources

## First Vertical Slice

Implement external resources in compiler/runtime while preserving legacy names:

```text
RT_COLOR -> output_color_tex
RT_DEPTH -> output_depth_tex
OUTPUT   -> output_color_tex  (legacy)
DISPLAY  -> output_color_tex  (legacy)
```

Then migrate `FovPipeline.pipeline` to use explicit render-target input/output nodes and verify:

```text
fbo_1:    r32f
RT_COLOR: rgba16f
RT_DEPTH: depth32f
```

## Current State

Compiler/runtime support for explicit graph-boundary nodes is implemented:
`render_target_input` resolves to external `RT_COLOR`/`RT_DEPTH`, those
resources bypass `FBOPool`, and runtime binds them to the active render target
textures. tcgui can load, save, and create the explicit input/output nodes.

Framegraph Debugger queries actual render target texture info for `OUTPUT`,
`DISPLAY`, `RT_COLOR`, and `RT_DEPTH` before consulting internal FBO aliases.
The graph compiler initializes the C++ inspect dispatcher before applying
socket/param fields, so compiled passes receive `input_res`/`output_res` values
instead of keeping constructor defaults.

`/home/mirmik/project/chronosquad-termin/Assets/Pipelines/FovPipeline.pipeline`
already uses `RenderTargetInput` + `PipelineOutput`; `DepthPass.output_res`
resolves to `RT_COLOR`, while the internal FBO remains `fbo_1`.

Remaining work:

- Rewrite built-in Default/Editor pipelines to the explicit input/output model.
- Migrate remaining project pipeline assets.
