# Render Graph Resource Types Plan

## Goal

Make render graph resources typed enough to represent an FBO as a tuple of
attachments, while allowing passes to consume color and depth attachments as
sampled textures.

Initial public resource/socket types:

- `fbo`: tuple resource with color attachment and optional depth attachment.
- `color_texture`: sampled/view reference to an FBO color attachment.
- `depth_texture`: sampled/view reference to an FBO depth attachment.
- `shadow`: existing shadow resource type.

`FboSplit` and `FboJoin` are compile-time graph nodes. They are not runtime
passes and must not create `tc_pass` instances.

## Implementation Checklist

1. [x] Add graph utility node definitions.
   - [x] Add `termin/render/graph_node_def.hpp`.
   - [x] Add `termin-render/src/graph_node_def.cpp`.
   - [x] Register boundary/utility node definitions in one C++ source of truth:
     `resource`, `external_rt`, `render_target_input`, `pipeline_output`,
     `output`, `fbo_split`, `fbo_join`.

2. [x] Add resource alias model.
   - [x] Add `AttachmentKind`, `ResourceView`, and `FboComposition`.
   - [x] Store views/compositions in `ResourceNaming`.
   - [x] Store views/compositions in `PipelineRenderCache` so `RenderEngine` can
     use the compiled graph metadata.

3. [x] Update C++ graph data parsing.
   - [x] `GraphData::from_trent` must get boundary/utility sockets from graph node
     definitions instead of hard-coded `if/else` sockets.
   - [x] Pass sockets still come from inspect graph metadata.

4. [x] Update graph compilation.
   - [x] `is_pass_node` must treat registered non-executable graph nodes as
     non-passes.
   - [x] `assign_resource_names` must create view aliases for `fbo_split`:
     `A.color -> {parent=A, attachment=color}` and
     `A.depth -> {parent=A, attachment=depth}`.
   - [x] `assign_resource_names` must create FBO compositions for `fbo_join`.
   - [x] `compile_graph` must copy the alias maps into `PipelineRenderCache`.
   - [x] `FboSplit`/`FboJoin` must not add resource specs and must not create
     runtime passes.

5. [x] Add type validation.
   - [x] Allow same-type connections.
   - [x] Require explicit `FboSplit`/`FboJoin` for conversions between `fbo`,
     `color_texture`, and `depth_texture`.
   - [x] Log/throw compile errors instead of guessing.

6. [x] Update render engine.
   - [x] After collecting FBO textures, apply `resource_views`.
   - [x] After views, apply `fbo_compositions`.
   - [x] Do not allocate a new FBO for composed FBO resources.
   - [x] Log `ERROR` when a view/composition refers to a missing attachment.

7. [x] Update UI editors.
   - [x] Add `FBO Split` and `FBO Join` in tcgui pipeline editor.
   - [x] Add matching nodes in Qt nodegraph.
   - [x] Both editors must serialize to the same graph format; compilation remains
     C++ only.

8. [x] Add tests.
   - [x] Split creates `color_texture` and `depth_texture` views.
   - [x] Join creates an FBO composition and no runtime pass.
   - [x] Split/join nodes do not add resource specs.
   - [x] Invalid direct type conversion fails.
   - [x] `RenderTargetInput.color -> FboSplit -> FboJoin -> PipelineOutput.color`
     compiles through the C++ compiler.
