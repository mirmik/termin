# RenderTarget over tc_texture migration plan

Date: 2026-04-22

## Goal

Move `tc_render_target` output onto `tc_texture` rails without changing `FBOPool`.

The target model:

- `tc_render_target` owns persistent output textures:
  - `color_texture: tc_texture_handle`
  - `depth_texture: tc_texture_handle`
- Materials keep using ordinary `tc_texture_handle` slots.
- Dragging a render target into a material texture slot assigns the render target's color `tc_texture`.
- Rendering writes final pipeline output into GPU storage owned by the render target's `tc_texture`.
- `FBOPool` remains the private intermediate storage for pipeline framegraph resources.

## Current State

`tc_texture` is a runtime resource, not an asset. `TextureAsset` is the asset wrapper around `TcTexture`.

Current `tc_texture` still assumes CPU pixel data:

- `tc_texture.data`
- `width`, `height`, `channels`, `format`
- `tc_texture_upload_gpu()` requires `tex->data`

Current render target output is not `tc_texture` based:

- `RenderingManager` stores render target GPU state in `render_target_states_`.
- `ViewportRenderState` owns `output_color_tex` and `output_depth_tex` as `tgfx::TextureHandle`.
- `RenderEngine::ViewportContext` receives final output as raw `tgfx::TextureHandle`.

Current material texture binding is already close to the desired API:

- `tc_material_texture` stores `tc_texture_handle`.
- material binding calls `wrap_tc_texture_as_tgfx2(device, mat_tex.texture)`.

The main missing piece is support for GPU-only/renderable `tc_texture`.

## Non-Goals

- Do not rewrite `FBOPool` in this migration.
- Do not make pipeline intermediate resources `tc_texture` yet.
- Do not introduce a separate material `TextureSource` ABI unless `tc_texture` proves insufficient.
- Do not make render targets file assets.

## Phase 1: Extend tc_texture Metadata

Add storage and usage metadata to `tc_texture`.

Suggested enums:

```c
typedef enum tc_texture_storage_kind {
    TC_TEXTURE_STORAGE_CPU_PIXELS = 0,
    TC_TEXTURE_STORAGE_GPU_ONLY = 1,
} tc_texture_storage_kind;

typedef enum tc_texture_usage_flags {
    TC_TEXTURE_USAGE_SAMPLED = 1 << 0,
    TC_TEXTURE_USAGE_COLOR_ATTACHMENT = 1 << 1,
    TC_TEXTURE_USAGE_DEPTH_ATTACHMENT = 1 << 2,
    TC_TEXTURE_USAGE_COPY_SRC = 1 << 3,
    TC_TEXTURE_USAGE_COPY_DST = 1 << 4,
} tc_texture_usage_flags;
```

Add fields:

```c
uint8_t storage_kind;
uint32_t usage;
```

Default for existing textures:

```c
storage_kind = TC_TEXTURE_STORAGE_CPU_PIXELS;
usage = TC_TEXTURE_USAGE_SAMPLED;
```

Add small C API helpers:

```c
TC_API void tc_texture_set_storage_kind(tc_texture* tex, tc_texture_storage_kind kind);
TC_API void tc_texture_set_usage(tc_texture* tex, uint32_t usage);
TC_API void tc_texture_set_size_format(tc_texture* tex, uint32_t w, uint32_t h, tc_texture_format fmt);
TC_API bool tc_texture_is_gpu_only(const tc_texture* tex);
```

Expected files:

- `termin-graphics/include/tgfx/resources/tc_texture.h`
- `termin-graphics/src/resources/tc_texture_registry.c`

## Phase 2: Add GPU-Only tgfx2 Resolution

Teach the texture bridge to resolve both CPU-pixel textures and GPU-only renderable textures.

Current behavior:

- `wrap_tc_texture_as_tgfx2()` uploads/wraps CPU pixel data.
- Non-GL path errors when `tex->data == NULL`.

Required behavior:

- CPU textures keep the existing path.
- GPU-only textures create or reuse a real `tgfx::TextureHandle` using `tc_texture` size/format/usage.
- Recreate when `tc_texture.header.version` changes.
- Cache by `(tc_texture pool_index, tgfx::IRenderDevice*)`.

Add or adapt:

```cpp
tgfx::TextureHandle ensure_tc_texture_tgfx2(
    tgfx::IRenderDevice& device,
    tc_texture_handle handle
);
```

Then make `wrap_tc_texture_as_tgfx2()` use that path for GPU-only textures.

Expected files:

- `termin-render/include/termin/render/tgfx2_bridge.hpp`
- `termin-render/src/tgfx2_bridge.cpp`
- possibly `termin-graphics/src/tgfx_resource_gpu.c` if the legacy `tc_gpu` API also needs renderable storage support immediately.

Important ownership rule:

- CPU texture OpenGL wrappers remain temporary external handles, released by the caller.
- GPU-only `tc_texture` handles are owned by the texture bridge/cache and must not be destroyed by material binding.

## Phase 3: Make tc_render_target Own Textures

Extend render target pool storage:

```c
tc_texture_handle* color_textures;
tc_texture_handle* depth_textures;
```

On `tc_render_target_new()`:

- create color texture
- create depth texture
- mark both `TC_TEXTURE_STORAGE_GPU_ONLY`
- assign usage and format
- set owner/name metadata

Suggested usage:

```c
color.usage =
    TC_TEXTURE_USAGE_SAMPLED |
    TC_TEXTURE_USAGE_COLOR_ATTACHMENT |
    TC_TEXTURE_USAGE_COPY_SRC |
    TC_TEXTURE_USAGE_COPY_DST;

depth.usage =
    TC_TEXTURE_USAGE_SAMPLED |
    TC_TEXTURE_USAGE_DEPTH_ATTACHMENT;
```

Add API:

```c
TC_API tc_texture_handle tc_render_target_get_color_texture(tc_render_target_handle h);
TC_API tc_texture_handle tc_render_target_get_depth_texture(tc_render_target_handle h);
TC_API void tc_render_target_ensure_textures(tc_render_target_handle h);
```

`tc_render_target_set_width()` and `tc_render_target_set_height()` must update texture metadata and bump texture versions.

Expected files:

- `termin-render/include/render/tc_render_target.h`
- `termin-render/src/tc_render_target.c`

## Phase 4: Render Into RenderTarget-Owned Textures

Replace render target output allocation in `RenderingManager`.

Current pattern:

```cpp
ViewportRenderState* state = get_or_create_render_target_state(rt);
state->ensure_output_textures(*device, w, h);
ctx.output_color_tex = state->output_color_tex;
ctx.output_depth_tex = state->output_depth_tex;
```

Target pattern:

```cpp
tc_render_target_ensure_textures(rt);

tc_texture_handle color = tc_render_target_get_color_texture(rt);
tc_texture_handle depth = tc_render_target_get_depth_texture(rt);

ctx.output_color_tex = ensure_tc_texture_tgfx2(*device, color);
ctx.output_depth_tex = ensure_tc_texture_tgfx2(*device, depth);
```

Primary functions to update:

- `RenderingManager::render_render_target_offscreen`
- `RenderingManager::render_viewport_offscreen`
- `RenderingManager::render_scene_pipeline_offscreen`, where viewport output is backed by a render target

Expected files:

- `termin-engine/src/rendering_manager.cpp`
- `termin-engine/include/termin/render/rendering_manager.hpp`

`ViewportRenderState` can remain for transition and non-render-target viewport output. It should stop being the owner for render target output.

## Phase 5: Keep Material Binding Generic

Material binding should remain based on `tc_texture_handle`.

Desired invariant:

```cpp
wrap_tc_texture_as_tgfx2(device, mat_tex.texture)
```

works for both:

- CPU pixel textures
- render target-owned GPU-only textures

No render-target special case should be needed in `ColorPass` or `MaterialPass`.

Expected files:

- `termin-app/cpp/termin/render/material_ubo_apply.cpp`
- `termin-render/src/tgfx2_bridge.cpp`

## Phase 6: Python Bindings

Expose render target output textures:

```python
rt.color_texture
rt.depth_texture
```

or methods:

```python
rt.get_color_texture()
rt.get_depth_texture()
```

The returned value should be usable with the existing material API:

```python
phase.set_texture("u_reflection", rt.color_texture)
```

Expected file:

- `termin-render/python/tc_render_target_bindings.cpp`

## Phase 7: UI Drag-and-Drop

For tcgui:

- `ViewportListWidgetTcgui` already has render target nodes.
- Make render target nodes draggable or otherwise provide a drag payload.
- Drop payload can contain render target handle/name, then resolve to `rt.color_texture`.

For Qt:

- Extend `EditorMimeTypes` with:

```python
RENDER_TARGET_REF = "application/x-termin-render-target-ref"
```

- Add create/parse helpers.

Material inspector:

- Current `_TextureEditor` lists only asset textures.
- For MVP, add drop support without changing combo contents.
- On drop render target:

```python
phase.set_texture(uniform_name, render_target.color_texture)
```

Later UI improvement:

```text
Texture slot:
  Assets
    brick.png
  Render Targets
    Mirror.color
    Minimap.color
```

Expected files:

- `termin-app/termin/editor_tcgui/viewport_list_widget.py`
- `termin-app/termin/editor_tcgui/material_inspector.py`
- `termin-app/termin/editor/drag_drop.py`
- Qt equivalents if the Qt editor path is still maintained

## Phase 8: Material Serialization

Current `.material` serialization saves only TextureAsset UUIDs.

For render target textures, there is no TextureAsset. Add a separate section for non-asset texture references.

MVP format:

```json
{
  "textures": {
    "u_albedo": "texture-asset-uuid"
  },
  "texture_refs": {
    "u_reflection": {
      "kind": "render_target",
      "target": "MirrorRT",
      "channel": "color"
    }
  }
}
```

Alternative future format:

```json
{
  "textures": {
    "u_albedo": {
      "kind": "asset",
      "uuid": "texture-asset-uuid"
    },
    "u_reflection": {
      "kind": "render_target",
      "target": "MirrorRT",
      "channel": "color"
    }
  }
}
```

Prefer the MVP format first to avoid breaking old material files.

Expected file:

- `termin-app/termin/assets/material_asset.py`

## Phase 9: Scheduling Dependencies

Even when render target output is represented as `tc_texture_handle`, the producer render target must be rendered before consumers.

Add dependency discovery:

- scan material phase textures
- identify textures owned by render targets
- render producer targets before current target/viewport

Possible owner metadata:

```c
tc_render_target_handle owner_render_target;
```

stored in `tc_texture`, or a reverse lookup in the render target pool.

Suggested API:

```c
TC_API bool tc_texture_get_owner_render_target(
    tc_texture_handle texture,
    tc_render_target_handle* out
);
```

MVP scheduling:

- Before rendering regular viewports, render all render targets referenced by scene materials.
- Later replace with a DAG/topological sort so render targets can depend on other render targets.

Expected files:

- `termin-engine/src/rendering_manager.cpp`
- material/drawable traversal helpers as needed

## Test Plan

Start with a small render path test before UI work.

1. Create a render target.
2. Verify it creates valid color/depth `tc_texture_handle`s.
3. Render into the render target.
4. Bind `rt.color_texture` in a material texture slot.
5. Render a viewport using that material.
6. Resize the render target.
7. Verify the texture metadata and GPU handle update.
8. Delete the render target and verify material references fail gracefully.

Regression checks:

- ordinary TextureAsset material textures still render
- material save/load preserves existing `"textures"` format
- render target-backed texture does not require CPU pixel data
- no stale tgfx2 handles after render target resize

## Key Invariants

- `tc_texture` does not require CPU data.
- `tc_texture` can represent renderable sampled GPU storage.
- `tc_render_target` owns and publishes output textures.
- Materials remain consumers of `tc_texture_handle`.
- `RenderEngine` receives final output as `tgfx::TextureHandle`, but ownership is rooted in `tc_texture`.
- `FBOPool` remains unchanged in this migration.
