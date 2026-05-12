# C++ renderer facades for tgfx2, tcgui and tcplot

## Context

`termin-gui` currently has a useful rendering model, but the reusable part of
that model lives in Python:

- widgets do not know about `IRenderDevice`;
- widgets render through a `UIRenderer` facade;
- `UI` receives a host-provided `Tgfx2Context`;
- `UIRenderer` owns batching, clipping, text, texture drawing and target
  handling on top of tgfx2.

This is the right shape for higher-level code. The problem is placement:
`UIRenderer` is a GUI-level Python class, while the primitive drawing services
it provides are not GUI-specific. `tcplot` needs the same kind of facade for
axes, grid, labels, legends, 2D overlays and texture composition. Making
`tcplot` depend on `termin-gui` would couple plot rendering to the widget
system, layout, themes and Python API.

The reusable rendering layer should live lower, in `termin-graphics`.

## Module boundaries

Target dependency direction:

```text
termin-graphics
    ^
    | uses tgfx2 renderer facades
tcplot
    ^
    | optional PlotWidget / embedding
termin-gui

termin-display provides windows, surfaces, contexts and presentation.
```

Responsibilities:

- `termin-graphics`: backend-agnostic GPU abstractions, tgfx2 context,
  primitive renderers, text rendering, texture drawing and common render
  utilities.
- `termin-display`: windows, render surfaces, swapchains/FBOs, presentation and
  input routing.
- `termin-gui`: widget tree, layout, theme, event dispatch and UI composition.
- `tcplot`: plot model, axes, data transforms, plot-specific layout and plot
  rendering.

`tcplot` should answer "how to render this plot through tgfx2". `termin-gui`
should answer "how to embed this into a widget tree".

## Proposed C++ layer

Add a reusable C++ immediate/batched 2D renderer to `termin-graphics`.
Possible names:

- `tgfx::Canvas2DRenderer`
- `tgfx::Immediate2DRenderer`
- `tgfx::ShapeRenderer2D`

The exact name is less important than the boundary: this is not a GUI widget
renderer. It is a tgfx2 drawing facade.

Minimal useful API:

```cpp
class Canvas2DRenderer {
public:
    explicit Canvas2DRenderer(tgfx::FontAtlas* default_font = nullptr);

    void begin(tgfx::RenderContext2& ctx, int width, int height);
    void begin(tgfx::RenderContext2& ctx,
               tgfx::TextureHandle target_color,
               tgfx::TextureHandle target_depth,
               int width,
               int height);
    void end();

    void begin_clip(float x, float y, float w, float h);
    void end_clip();

    void draw_rect(float x, float y, float w, float h, Color color,
                   float radius = 0.0f);
    void draw_rect_outline(float x, float y, float w, float h, Color color,
                           float thickness = 1.0f);
    void draw_line(float x0, float y0, float x1, float y1, Color color,
                   float thickness = 1.0f);
    void draw_polyline(std::span<const Vec2> points, Color color,
                       float thickness = 1.0f);
    void draw_texture(tgfx::TextureHandle texture,
                      float x, float y, float w, float h,
                      Color tint = Color::white());

    void draw_text(std::string_view text, float x, float y,
                   float size_px, Color color,
                   tgfx::FontAtlas* font = nullptr);
    TextMeasure measure_text(std::string_view text, float size_px,
                             tgfx::FontAtlas* font = nullptr) const;
};
```

Notes:

- The renderer should use `RenderContext2`, not own or create an
  `IRenderDevice`.
- It may own GPU resources needed for batching: vertex buffers, shaders,
  pipeline state and cached texture resources.
- It should not choose a backend. Backend selection remains a host/display
  concern.
- It should restore or explicitly set the state it depends on at the start of
  each pass. Multiple clients can render through the same `RenderContext2`.
- Clip stack belongs here, because both GUI and plot rendering need nested
  clipping.

## What happens to termin-gui

`tcgui.widgets.UIRenderer` should become a thin Python-facing wrapper over the
C++ renderer:

- keep the current public Python API where practical;
- keep GUI-specific convenience behavior in Python;
- delegate primitive drawing, clipping, batching, text and texture drawing to
  the C++ `Canvas2DRenderer`;
- keep `UI` as the owner of the renderer instance for a widget tree.

Widgets should keep the current shape:

```python
def render(self, renderer: UIRenderer):
    ...
```

They should still not receive `IRenderDevice`, `RenderContext2` or backend
objects in constructors.

## What happens to tcplot

`tcplot` should consume the C++ 2D renderer directly or through a small
plot-specific renderer facade.

Suggested shape:

```text
PlotView2D / PlotView3D
    plot state, camera, data transforms, input state

PlotRenderer2D / PlotRenderer3D
    plot-specific render orchestration
    uses tgfx::Canvas2DRenderer for 2D primitives/text/overlays
    uses tgfx2 draw calls directly for meshes and 3D passes
```

For 2D plots:

- axes, grid, ticks, labels, legends and selection overlays can be drawn through
  `Canvas2DRenderer`;
- line/point series may use either specialized plot batches or
  `Canvas2DRenderer` if performance is acceptable;
- plot state should not hold `IRenderDevice`.

For 3D plots:

- mesh/surface rendering stays in plot-specific 3D code;
- billboard labels, axes labels and 2D overlays use the shared 2D renderer;
- camera and projection remain plot-specific.

The C# and WPF examples should create/adapt the graphics context at the control
or host level, then pass a renderer/context facade to plot rendering. They
should not contain backend-specific calls except for the single place where the
example selects its backend.

## Migration plan

1. Create the C++ `Canvas2DRenderer` in `termin-graphics` with rects, lines,
   clipping and basic text.
2. Add tests or smoke examples for drawing through `RenderContext2` into an
   offscreen target.
3. Bind the renderer to Python.
4. Rework `tcgui.widgets.UIRenderer` to delegate primitive drawing to the C++
   renderer while keeping the existing Python widget API.
5. Rework `tcplot` 2D rendering to use the shared renderer for UI-like drawing:
   background, grid, axes, labels, legend and clipping.
6. Rework `tcplot` 3D overlays and billboards to use the same renderer where
   appropriate.
7. Remove temporary plot ownership of `IRenderDevice`, `PipelineCache` and
   `RenderContext2` from view constructors. Keep these at host/renderer level.
8. Recheck multi-window behavior in OpenGL and Vulkan. The renderer should be
   per context or explicitly tied to a shared `Tgfx2Context`; views should not
   own global GPU state.

## Expected result

After the migration:

- backend selection is explicit and centralized in host/display code;
- multiple windows can share the same device/context model used by
  `termin-display`;
- `termin-gui` and `tcplot` share the same primitive rendering implementation;
- plot views are backend-agnostic and can be embedded in GUI, WPF, standalone
  windows or offscreen render flows;
- Python code keeps a convenient `UIRenderer` facade without being the only
  implementation of the rendering logic.
