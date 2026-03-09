# Offscreen-First Rendering Architecture

## Overview

The offscreen-first rendering model separates rendering into two phases:
1. **Render Phase**: All viewports render to their `output_fbo` in a single GL context
2. **Present Phase**: Output FBOs are blitted to displays and swapped

## Benefits

- Scene pipelines can span viewports on different displays
- All GPU resources live in one context (no context_key complexity)
- Displays are independent and symmetrical
- Natural support for RenderTextures (every viewport has an output_fbo)
- Easy to add: viewport-in-viewport, screenshots, headless rendering

## Integration

### Step 1: Initialize RenderingManager

```python
from termin.visualization.render import RenderingManager

# At application startup (before creating displays)
manager = RenderingManager.instance()
manager.initialize()  # Creates OffscreenContext
```

### Step 2: Configure SDLEmbeddedWindowBackend

```python
from termin.visualization.platform.backends.sdl_embedded import SDLEmbeddedWindowBackend

# Create backend with shared context
sdl_backend = SDLEmbeddedWindowBackend()
sdl_backend.set_share_context(
    share_context=manager.offscreen_context.gl_context,
    make_current_fn=manager.offscreen_context.make_current,
)
sdl_backend.set_graphics(manager.graphics)
```

### Step 3: Rendering Loop

```python
# In your render loop (e.g., EditorWindow or game loop)
def render_frame():
    manager = RenderingManager.instance()

    # This automatically uses offscreen rendering if initialize() was called
    manager.render_all()  # render_all_offscreen() + present_all()
```

Or manually control the phases:

```python
def render_frame():
    manager = RenderingManager.instance()

    # Phase 1: Render all viewports to output_fbos
    manager.render_all_offscreen()

    # Phase 2: Blit to displays
    manager.present_all()
```

## Architecture Details

### OffscreenContext

Dedicated GL context for rendering. All GPU resources live here.

```
OffscreenContext
├── gl_context: SDL GL context (hidden window)
├── graphics: GraphicsBackend (OpenGL)
└── context_key: 0 (constant, single context)
```

### ViewportRenderState

Now includes `output_fbo` for final render result:

```python
@dataclass
class ViewportRenderState:
    fbos: Dict[str, FramebufferHandle]  # Intermediate FBOs
    shadow_map_arrays: Dict[str, ShadowMapArrayResource]
    output_fbo: Optional[FramebufferHandle] = None  # Final result
```

### Render Flow

```
┌─────────────────────────────────────────────────────────────┐
│                    RENDER PHASE                              │
│  (OffscreenContext, single GL context)                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  render_all_offscreen() {                                   │
│      offscreen_context.make_current()                       │
│                                                             │
│      // Scene pipelines (can span multiple displays)        │
│      for pipeline in scene_pipelines:                       │
│          viewport_contexts = collect_from_ALL_displays()    │
│          render_scene_pipeline_offscreen(...)               │
│                                                             │
│      // Unmanaged viewports                                 │
│      for viewport in unmanaged_viewports:                   │
│          render_viewport_offscreen(viewport)                │
│  }                                                          │
│                                                             │
│  Result: viewport.state.output_fbo contains rendered image  │
└─────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                   PRESENT PHASE                              │
│              (per-display, blit + swap)                     │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  present_all() {                                            │
│      for display in displays:                               │
│          display.surface.make_current()                     │
│          clear(display_fbo)                                 │
│                                                             │
│          for viewport in sorted_by_depth(display):          │
│              blit(viewport.output_fbo → display_fbo,        │
│                   viewport.rect)                            │
│                                                             │
│          display.surface.present()  // swap buffers         │
│  }                                                          │
└─────────────────────────────────────────────────────────────┘
```

## Backwards Compatibility

The system supports legacy per-display rendering:

- If `manager.initialize()` is NOT called, `render_all()` uses legacy mode
- Legacy mode: each display rendered separately with context switching
- `_use_offscreen_rendering` flag controls which mode is used

## Migration Path

1. Call `manager.initialize()` at startup
2. Configure SDLEmbeddedWindowBackend with shared context
3. Existing code continues to work (render_all handles mode selection)
4. Remove context_key usage over time (all resources use constant key 0)
