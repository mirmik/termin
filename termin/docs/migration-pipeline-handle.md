# Migration: RenderPipeline → handle-based wrapper

## Problem

`RenderPipeline` is currently an owning C++ object that stores:
- `handle_` — index in tc_pipeline pool (C-level, stores passes)
- `name_` — duplicates `tc_pipeline.name`
- `specs_` — resource specs
- `fbo_pool_` — FBO cache for intermediate render targets
- `shadow_arrays_` — shadow map texture arrays

It uses `cpp_owner` pointer in tc_pipeline to find itself from handle,
and `py_wrapper` to cache Python object reference.

This causes problems:
- C++ creates pipeline, sets it on viewport via handle — Python can't see it
  (py_wrapper not set)
- Two ownership models (C++ unique_ptr in RenderingManager + Python wrapper)
  conflict
- `viewport.pipeline` returns None when pipeline was assigned from C++

## Target

`RenderPipeline` becomes a lightweight handle wrapper (like `TcViewport`,
`TcSceneRef`). All data lives in tc_pipeline pool. No ownership semantics.

## Steps

### Phase 1: Move data into tc_pipeline pool

**Files:** `tc_pipeline.h`, `tc_pipeline.c`

1. Add `void* render_cache` + `void (*render_cache_destructor)(void*)` to
   `tc_pipeline` struct
2. Add C API: `tc_pipeline_get_render_cache()`,
   `tc_pipeline_set_render_cache(h, cache, destructor)`
3. Free render_cache in `tc_pipeline_pool_free()`
4. Remove `cpp_owner` and `py_wrapper` fields and their API functions

### Phase 2: Make RenderPipeline a thin handle wrapper

**Files:** `render_pipeline.hpp`, `render_pipeline.cpp`

1. Remove fields: `name_`, `specs_`, `fbo_pool_`, `shadow_arrays_`
2. Add `PipelineRenderCache` struct (FBOPool + shadow_arrays + specs) —
   stored as render_cache in pool
3. `cache()` method — lazy-creates PipelineRenderCache in render_cache
4. `name()` reads from tc_pipeline pool, `set_name()` writes to pool
5. `specs()` / `fbo_pool()` / `shadow_arrays()` access via cache()
6. Remove destructor (does NOT destroy pipeline in pool)
7. Explicit `destroy()` method calls `tc_pipeline_destroy(handle_)`
8. Remove move constructor/assignment (trivially copyable handle)
9. Add `RenderPipeline(tc_pipeline_handle h)` constructor

### Phase 3: Update RenderingManager

**Files:** `rendering_manager.hpp`, `rendering_manager.cpp`

1. `scene_pipelines_`: change from
   `map<string, unique_ptr<RenderPipeline>>` to
   `map<string, tc_pipeline_handle>`
2. `clear_scene_pipelines()`: call `tc_pipeline_destroy()` for each handle
3. `compile_scene_pipeline()`: return `tc_pipeline_handle`
4. `get_scene_pipeline()`: return `RenderPipeline` by value (from handle)
5. `create_pipeline()` / `make_default_pipeline()`: return `RenderPipeline`
   by value
6. `PipelineFactory` typedef: return `RenderPipeline` by value
   (or `tc_pipeline_handle`)
7. `mount_scene()`: accept `tc_pipeline_handle` instead of `RenderPipeline*`
8. `render_viewport_offscreen()` / `render_scene_pipeline_offscreen()`:
   create `RenderPipeline` wrapper on stack from handle
9. Remove `from_handle()` static method (just use constructor)

### Phase 4: Update PullRenderingManager

**Files:** `pull_rendering_manager.hpp`, `pull_rendering_manager.cpp`

Same changes as Phase 3 where applicable.

### Phase 5: Update viewport bindings

**Files:** `viewport_module.cpp`

1. Pipeline getter: create `RenderPipeline` from handle via
   `RenderPipeline.from_handle()` Python-side
2. Pipeline setter: extract handle from Python object, set on viewport
3. Remove all `py_wrapper` / `Py_INCREF` / `Py_DECREF` code
4. Serialize: read name directly from `tc_pipeline_get_name(handle)`

### Phase 6: Update Python bindings

**Files:** `render_pipeline_bindings.cpp`, `rendering_manager_bindings.cpp`

1. Add `RenderPipeline.from_handle(index, generation)` static method
2. Remove move semantics from binding (RenderPipeline is copyable)
3. `_pipeline_handle` property returns (index, generation) tuple
4. Adapt `rendering_manager_bindings.cpp` to return `RenderPipeline` by value
5. Pipeline factory callback: return RenderPipeline by value

### Phase 7: Update Python editor code

**Files:** `rendering_controller.py`, `editor_scene_attachment.py`,
`viewport_inspector.py`

1. `EditorSceneAttachment`: pipeline created via factory, assigned to viewport
   — should work as before (Python sets pipeline, py setter stores handle)
2. `rendering_controller.sync_viewport_configs_to_scene()`:
   `viewport.pipeline.name` now works because getter creates wrapper from
   handle
3. `viewport_inspector._select_viewport_pipeline()`: same — works via getter
4. Remove workaround code (re-assign pipeline after attach)

### Phase 8: Cleanup

1. Remove `tc_pipeline_get_cpp_owner` / `tc_pipeline_set_cpp_owner`
2. Remove `tc_pipeline_get_py_wrapper` / `tc_pipeline_set_py_wrapper`
3. Remove `cpp_owner` / `py_wrapper` from `tc_pipeline` struct
4. Remove debug logs added during investigation

## Testing

- Editor: create Display 0, viewport main, assign Default pipeline, save,
  reload — pipeline visible in inspector and renders
- Play/Stop game mode — viewport pipeline preserved
- Scene pipeline compilation — still works
- Pipeline inspector — can change pipeline, viewport updates
- Multiple viewports with different pipelines

## Notes

- `PipelineFactory` currently returns `RenderPipeline*` — change to return
  by value. Python factory callback creates pipeline, returns wrapper.
- `RenderEngine::render_view_to_fbo()` takes `RenderPipeline*` — change to
  reference or value.
- FBO ownership: FBOs in `fbo_pool_` are per-pipeline GPU resources. Moving
  to render_cache means they follow the pipeline handle in the pool.
  `tc_pipeline_destroy()` frees render_cache → FBOs freed.
