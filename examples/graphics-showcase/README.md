# Graphics profile showcase

This is the cross-package acceptance example for the Termin `graphics` SDK
profile. It deliberately uses the installed SDK as a product: run it with the
bundled isolated Python and do not add the repository to `PYTHONPATH`.

```bash
task build:graphics -- --sdl
sdk-graphics/bin/termin_python -I examples/graphics-showcase/main.py \
  --headless \
  --output /tmp/termin-graphics-showcase.png \
  --report /tmp/termin-graphics-showcase.json
```

The central repository test gate performs the same run with poisoned ambient
Python paths and validates the profile boundary, report and artifact:

```bash
task test
```

The gate currently delegates this focused check to
`scripts/smoke-graphics-showcase`; that path is an implementation detail, not
a second public command interface.

An initial pip-installable Linux product can be built independently of the SDK:

```bash
task package:graphics:python
python3.14t -m pip install --find-links dist/graphics-python termin-graphics-profile
```

The metapackage pins the complete matching wheel set and owns precompiled
Vulkan/OpenGL shaders and the UI font. It does not contain `slangc`, Slang
libraries or `termin_shaderc`. Importing `tgfx` remains side-effect free;
`tgfx.configure_default_shader_runtime()` activates the wheel artifacts with
developer compilation disabled. Applications that intentionally compile shader
sources must install the tools separately and opt into developer compilation.
This prototype targets the repository's pinned CPython 3.14t ABI and the host
Linux x86_64 platform. It has not yet been repaired or certified as a manylinux
artifact for upload to PyPI.

The product includes `termin-window`, the GUI window adapter, and Termin's
pinned bundled SDL2. Headless execution remains a required contract: it does
not create a window or initialize an application display host, and it still
uses `termin.gui_native.OffscreenGuiComposition`. `termin-display`, engine
runtime, editor, and PySDL2 remain outside the product. Failure of any section
is logged with its name and makes the process fail.

## Feature matrix

| Section | Product surface |
|---|---|
| `native_ui` | Retained controls, collections, text, models and layout |
| `tcplot_sine` | Sine, cosine and damped-sine line families |
| `tcplot_scatter` | Three clustered scatter series and a trend line |
| `tcplot_multi` | Polynomial and damped-oscillation plots side by side |
| `tcplot_marker` | Draggable retained marker with nearest-sample snapping |
| `tcplot_helix` | Double helix and deterministic 3D scatter |
| `tcplot_surface` | Sinc surface, Viridis colorbar, wireframe and z scaling |
| `visual_scene_gallery` | Retained shapes, hierarchy, transforms, opacity, z-order and hit regions |
| `animated_skinned_glb` | Loaded GLB mesh, two-joint skeleton and sampled animation pose |
| `visual_scene_nodegraph` | Visual-scene primitives, nodegraph model and projection |
| `visual_scene3d_widget` | Retained 3D items, camera provider, orbit fallback and item actions in `SceneView3D` |
| `plot_nodegraph_composition` | Plot2D and Plot3D embedded as node-body widgets |

The remaining profile packages are exercised as supporting parts of those
pages rather than represented by artificial empty tabs: `termin-image` writes
the acceptance PNG, and `termin-base`, `termin-dispatch`,
`termin-inspect`, `termin-tween` and the nanobind runtime support package are
verified by the isolated import boundary. Build tooling is deliberately not a
runtime dependency. `termin-window` is the canonical interactive host described
below.

The JSON report records the exact imported graphics-profile packages, every
declared section, framebuffer coverage metrics and the final artifact path.
The requested PNG is produced by the composition section rather than copied
from a golden image.

The same installed product also has an interactive frontend for the integration
section:

```bash
task build:graphics -- --sdl
sdk-graphics/bin/termin_python -I examples/graphics-showcase/main.py --windowed
```

The frontend opens on an overview and exposes every registry section as a tab;
it uses `termin.window`, while engine-level `termin.display` remains outside
this profile. For automated checks, `--frames N` and `--seconds N` bound the
window lifetime.

The initial standalone Python product is Linux-only. A future Windows wheel
must keep SDL enabled and use the bundled SDL2 DLL; the following no-SDL recipe
is only an SDK headless diagnostic, not the public product contract:

```powershell
task build:graphics -- --no-sdl --no-vulkan --no-opengl
.\sdk-graphics\bin\termin_python.exe -I .\examples\graphics-showcase\main.py `
  --headless --output $env:TEMP\termin-graphics-showcase.png `
  --report $env:TEMP\termin-graphics-showcase.json
```
