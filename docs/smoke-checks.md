# Smoke Checks

This page lists repeatable smoke checks for render, shader, graphics backend,
and packaged runtime changes. Prefer the central scripts first, then run the
targeted checks that match the touched subsystem.

## Default Repository Gate

Use the default repository gate during normal development. It runs the working
set: C/C++ tests without window creation, Python tests except those marked
`full`, and no editor-process smoke tests.

```bash
task test --
```

Use the full repository gate before merging broad SDK, render, shader, module,
or build-system changes:

```bash
task test -- --full
```

The full gate enables C++ window tests, Python tests marked `full`, and
editor-process module hot-reload smokes. On headless Linux the smoke scripts use
the canonical `scripts/termin-editor-virtual-display` wrapper when its Xvfb/Mesa
dependencies are available. If the editor smoke stage is not relevant or the
host cannot launch the editor, run `task test -- --full --no-editor-smoke`.

## Render And Shader Matrix

| Area | Command | What It Proves |
| --- | --- | --- |
| C/C++ render and graphics tests | `task test:cpp -- --full --sdl` | Builds and runs the registered CTest graph, including tgfx2 OpenGL/Vulkan-capable tests where the host supports them. |
| SDF font atlas headless check | `ctest --test-dir build/Release -R '^tgfx2_sdf_test$' --output-on-failure` | FontAtlas bitmap/SDF glyph metrics, UVs, measurements, and CPU atlas signal work without a GL/Vulkan/D3D runtime. |
| Python shader/material/project tests | `task test:python -- termin-materials/tests/test_shader_parser.py termin-voxels/tests/test_voxel_shader.py termin-shader-runtime/tests/test_shader_tool_resolution.py termin-app/tests/test_shader_tool_resolution.py` | Parser/runtime shader import, built-in shader catalog, and shader tool resolution stay usable from Python. |
| OpenGL tgfx2 smoke | `ctest --test-dir build/Release -R '^(tgfx2_smoke|tgfx2_opengl_bound_resource_set)$' --output-on-failure` | OpenGL device, render target readback, shader artifacts, and bound-resource-set path work. |
| Vulkan tgfx2 smoke | `ctest --test-dir build/Release -R '^(tgfx2_vulkan_smoke|tgfx2_vulkan_window)$' --output-on-failure` | Vulkan offscreen/window paths, readback, resource binding, vertex formats, and optional Slang artifact path work. |
| D3D11 bound path on Windows | `pwsh scripts/validate-tgfx2-d3d11-bound-path.ps1` | Windows D3D11 device smoke and backend-facing bound-resource-set path work. Add `-WindowTests` to compile and run the direct flip-model swapchain smoke plus VSync/Immediate `SDLBackendWindow` presentation. |
| D3D11 editor scene on Windows | `.\sdk\bin\termin_python.exe .\scripts\smoke-windows-d3d11-editor.py` | The installed editor opens the repository fixture through D3D11, renders Color/Present passes, produces non-empty framegraph and UI PNG captures, reports no debug-layer errors, and shuts down cleanly. |
| Backend window presentation | `ctest --test-dir build/Release -R '^(termin_window_backend_triangle|termin_window_backend_triangle_immediate|termin_window_backend_triangle_vulkan_vsync|termin_window_backend_triangle_vulkan_immediate|termin_window_backend_d3d11_present|termin_window_backend_d3d11_present_immediate)$' --output-on-failure` | SDLBackendWindow VSync and Immediate presentation work on OpenGL, Vulkan, and D3D11, with unavailable window backends skipped by the test. D3D11 Immediate requires reported DXGI tearing support and fails explicitly when unavailable. |
| Engine frame limiter | `ctest --test-dir build/Release -R '^termin_engine_frame_cadence_test$' --output-on-failure` and `task test:python -- termin-engine/tests/test_engine_frame_limit.py` | Positive `target_fps` values provide cadence deadlines, while zero selects Unlimited mode without a software frame deadline. |
| Native UI headless QA | `ctest --test-dir build/Release -R '^termin_gui_native_(showcase_test|window_adapter_test|offscreen_composition_test|renderer_pixel_smoke)$' --output-on-failure` | Stable showcase structure plus real adapter/offscreen control and text pixels, textures, rounded geometry and nested clipping on compiled Vulkan/D3D11 backends. Only an explicitly unavailable compiled backend is skipped; shader, pipeline, readback and dropped-batch failures fail the gate. |
| Native UI Python showcase | `sdk/bin/termin_python --termin-overlay build/python-envs/test/overlay.json -m pytest termin-gui-native/python/tests/test_gui_native.py -q` | The Python-built native control tree has stable layout/paint totals, shared models, focus reachability, clipping and long UTF-8 fixtures. |
| Installed graphics-profile showcase | `task build:graphics -- --no-sdl && scripts/smoke-graphics-showcase` | The installed editor-free SDK imports its complete unconditional Python closure in isolated bundled Python, contains no `termin.display`/engine runtime, and renders native UI, visual-scene/nodegraph, Plot2D, Plot3D and their composition to a non-empty PNG. On Windows use `task build:graphics -- --no-sdl --no-vulkan --no-opengl` and the documented headless showcase command for the D3D11 variant. |
| Standalone Graphics Python product (initial Linux contract) | `task package:graphics:python` (or focus one variant with `-- --python-abi cp314` / `cp314t`) | Independently rebuilds and verifies the graphics graph for both CPython 3.14 ABIs with `termin-window`, the GUI window adapter and pinned bundled SDL2, emits `cp314` and `cp314t` wheels under `dist/graphics-python`, centralizes native libraries plus precompiled Vulkan/OpenGL shaders, fonts and `termin_shaderc`, and proves both offscreen and SDL-offscreen windowed showcases work in clean per-ABI venvs with an empty `PATH` and no packaged Slang, without consuming `sdk-graphics`. |
| Graphics Python manylinux release gate | `task package:graphics:python:manylinux` | Builds the internal modular cp314/cp314t matrix in a digest-pinned `manylinux_2_28_x86_64` image, fuses each ABI into one public `termin-graphics` wheel, repairs those two wheels with pinned `auditwheel`, embeds the complete release-license inventory, and installs the repaired candidates into clean offline venvs. A SHA-256-pinned Mesa lavapipe build proves the Vulkan headless showcase without a host GPU; SDL-offscreen OpenGL is checked too. The two-wheel candidate and provenance manifest are published atomically under `dist/graphics-python-manylinux`. |
| Graphics Python publication preflight | `task publish:graphics:python` | Performs a network-free, exact-manifest check of the complete 0.5.2 candidate: one distribution, two ABI wheels, manylinux tags, public dependency/license metadata and SHA-256. Add `-- --check` for Twine metadata checks or `-- --remote-status` for read-only filename/digest reconciliation with PyPI. Actual upload additionally requires `--upload --confirm-version 0.5.2` and safely resumes a matching partial release with 429 backoff. |
| Relocated standalone Graphics SDK | `scripts/smoke-installed-graphics-consumers --sdk-root sdk --slangc "$TERMIN_SLANGC"` | Copies the composed Graphics SDK out of the checkout, clears source/runtime overlays, verifies its recorded Core identity, proves a missing installed GLB package fails, then builds a native CMake consumer and runs isolated Python, material/Slang, MCP readback and animated skinned GLB showcase consumers. |
| Headless editor MCP/readback | `scripts/smoke-editor-mcp-offscreen` | Two real installed editors run concurrently without `DISPLAY`, publish distinct agent-owned MCP sessions, execute an editor command, return non-empty Vulkan offscreen PNG captures, avoid window modules, remove their descriptors and shut down cleanly. |
| Virtual-display editor E2E | `scripts/smoke-editor-virtual-display` | Xvfb starts on a unique display, Mesa llvmpipe exposes OpenGL 4.6/GLSL 4.60, the real SDL editor publishes an isolated MCP session, project/scene state is reachable, and MCP requests a clean shutdown. |
| Built-in render pass shaders | `ctest --test-dir build/Release -R '^termin_render_passes_builtin_shader_sources_test$' --output-on-failure` | Built-in shader sources/catalog entries and render-pass shader templates remain loadable. |
| DebugTrianglePass pixel smoke | `ctest --test-dir build/Release -R '^termin_render_passes_debug_triangle_pixel_smoke$' --output-on-failure` | Vulkan offscreen execution of a real `termin-render-passes` FramePass, built-in shader catalog lookup, RenderContext2 pass recording, texture output, and pixel readback work. |
| ColorPass mesh/material pixel smoke | `ctest --test-dir build/Release -R '^termin_render_passes_color_pass_pixel_smoke$' --output-on-failure` | Vulkan offscreen `ColorPass` rendering of a scene `MeshRenderer`, opaque material phase routing, material UBO color binding, mesh bridge draw, and pixel readback work. |

For a deterministic native UI desktop capture, build the examples and request
one frame. The output is a binary 800×600 PPM by default and the process exits
after successful readback:

```bash
cmake -S termin-gui-native -B build/termin-gui-native-examples \
  -DCMAKE_BUILD_TYPE=Release -DCMAKE_PREFIX_PATH="$PWD/sdk" \
  -DTERMIN_BUILD_TESTS=OFF -DTERMIN_GUI_NATIVE_BUILD_EXAMPLES=ON
cmake --build build/termin-gui-native-examples -j
TERMIN_GUI_NATIVE_SCREENSHOT=/tmp/termin-gui-native-showcase.ppm \
  build/termin-gui-native-examples/termin_gui_native_showcase
```

On a headless Linux host, set `SDL_VIDEODRIVER=offscreen` and
`TERMIN_BACKEND=opengl`. A Vulkan-capable window driver or display should use
the normal default backend; unsupported SDL/backend combinations return the
example skip code `77` with an error message.

## Packaged Runtime Matrix

| Area | Command | What It Proves |
| --- | --- | --- |
| Runtime package exporter/loader | `task test:python -- --full termin-project-build/tests/test_runtime_package_exporter.py` and `ctest --test-dir build/Release -R termin_runtime_package_loader_test --output-on-failure` | Runtime manifests, shader artifacts, assets, and the canonical native loader remain coherent. |
| Desktop build profile path | `task test:python -- termin-project-build/tests/test_project_build_profile_backend.py termin-project-build/tests/test_project_build_target_common.py termin-project-build/tests/test_project_build_target_preflight.py` | Build profile dispatch, target preflight, and host/tool checks remain deterministic. |
| D3D11 native player scene on Windows | `.\sdk\bin\termin_python.exe .\scripts\smoke-windows-d3d11-player.py` | A strict D3D11-only desktop bundle loads the repository fixture and its real resources, presents 30 frames in the native player with no debug-layer errors or backend fallback, and shuts down cleanly. |
| D3D11 WPF scene on Windows | `.\sdk\bin\termin_python.exe .\scripts\smoke-windows-d3d11-wpf-scene.py` | `SceneApp` builds without OpenGL, creates a display-owned D3D11 offscreen texture, presents 30 frames through D3DImage, rejects debug-layer errors, and destroys display resources before the shared graphics host. |
| Relocated editor SDK | Run `scripts/smoke-relocated-sdk` on Linux or `scripts/smoke-relocated-sdk.ps1` on Windows after an SDK build. | A copied SDK passes artifact, runtime and app-payload manifests and starts bundled Python/editor/launcher diagnostics without checkout or ambient Python. |
| Relocatable desktop project bundle | Run the project-specific relocated bundle smoke, for example the Chess bundle smoke tracked separately. | The packaged project host can run outside the source tree with bundled assets, Python packages, and shader artifacts. |

## CI Jobs To Watch

The GitHub Actions workflow keeps the same checks split by cost and platform:

- `lint-cpp` keeps the native static-analysis gate from regressing;
  `plan-pr-linux` runs the repository check profile, including source-size
  policy, manifest validation, and orphan detection.
- `build-cpp-libs`, `test-cpp-libs`, `build-bindings`, `test-termin`, and
  `test-pip-packages` cover the Linux SDK build and test path.
- `tgfx2-d3d11-bound-windows` covers the Windows D3D11 backend smoke.
- `smoke-build-system-windows` covers the Windows build-tool entry points.
