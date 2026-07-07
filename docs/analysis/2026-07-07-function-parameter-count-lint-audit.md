# Function Parameter Count Lint Audit

Date: 2026-07-07

This audit checks how noisy a "more than seven parameters" lint gate would be
for Python and C/C++ sources.

The repository configuration was not changed during this audit. The current
Python Ruff baseline in `ruff.toml` selects only `B`, `E9`, and `F`; it does
not enable `PLR0913`.

## Summary

- Python/Ruff `PLR0913` with `lint.pylint.max-args = 7`: 54 diagnostics.
- C/C++/clang-tidy `readability-function-size.ParameterThreshold = 7`: 84
  diagnostics total.
- Of the C/C++ diagnostics, 64 are in repository-owned code and 20 are in
  `termin-thirdparty` headers included through repository translation units.

The result is small enough to enable eventually, but not as a drive-by config
change. The editor menu/controller constructors and several rendering/graphics
APIs need deliberate API shape work before this becomes a clean CI rule.

## Reproduction

Python:

```bash
python3 -m ruff check \
  --select PLR0913 \
  --config 'lint.pylint.max-args = 7' \
  .
```

C/C++ configure:

```bash
./run-lint-cpp.sh --configure-only --jobs 1
```

C/C++ audit check:

```bash
clang-tidy <source-file> \
  -p build/Release-lint \
  --checks=-*,readability-function-size \
  --warnings-as-errors= \
  --header-filter='^/home/mirmik/project/termin-dev2/(termin-|tcplot|cmake|scripts|tools|CMakeLists\.txt)' \
  --config='{CheckOptions: [{key: readability-function-size.ParameterThreshold, value: 7}, {key: readability-function-size.StatementThreshold, value: none}, {key: readability-function-size.LineThreshold, value: none}, {key: readability-function-size.BranchThreshold, value: none}, {key: readability-function-size.VariableThreshold, value: none}, {key: readability-function-size.NestingThreshold, value: none}]}'
```

The C/C++ audit was run across all 280 repository-owned translation units from
`build/Release-lint/compile_commands.json`.

## Python Results

Diagnostics by area:

| Count | Area |
|---:|---|
| 11 | `termin-project-build` |
| 10 | `termin-app/termin/editor_tcgui` |
| 9 | `termin-navmesh` |
| 5 | `termin-qopt` |
| 4 | `termin-csg` |
| 4 | `termin-gui` |
| 3 | `termin-glb` |
| 2 | `termin-components/termin-components-voxels` |
| 2 | `termin-player` |
| 1 | `scripts` |
| 1 | `termin-app/termin/editor_core` |
| 1 | `termin-audio` |
| 1 | `termin-inspect` |

Notable highest-count definitions:

| Parameters | Definition |
|---:|---|
| 60 | `termin-app/termin/editor_core/menu_bar_model.py:19` `build_editor_menu_spec` |
| 54 | `termin-app/termin/editor_tcgui/menu_bar_controller.py:25` `MenuBarController.__init__` |
| 26 | `termin-navmesh/python/termin/navmesh/builder_component.py:100` `NavMeshBuilderComponent.__init__` |
| 23 | `termin-components/termin-components-voxels/python/termin_voxel_components/voxelizer_component.py:117` `VoxelizerComponent.__init__` |
| 22 | `termin-app/termin/editor_tcgui/editor_dialog_launcher.py:12` `EditorDialogLauncher.__init__` |
| 19 | `termin-app/termin/editor_tcgui/scene_file_controller.py:20` `SceneFileController.__init__` |
| 18 | `termin-navmesh/python/termin/navmesh/polygon_builder.py:851` `triangulate_region` |
| 14 | `termin-inspect/python/termin/inspect/inspect_field.py:93` `InspectField.__init__` |
| 14 | `termin-project-build/python/termin/project_build/quest_openxr_build.py:58` `build_quest_openxr_project` |
| 13 | `termin-project-build/python/termin/project_build/android_build.py:47` `build_android_project` |

Lower-count Python diagnostics are mostly:

- build orchestration functions with repeated target/package/runtime options;
- navmesh and CSG geometry helpers carrying coordinate tuples as flat scalar
  parameters;
- tcgui render helpers carrying rectangle/texture dimensions as scalar
  parameters;
- QP/FEM solver helpers carrying matrix blocks independently instead of a
  typed problem/context object.

## C/C++ Results

Diagnostics by repository-owned area:

| Count | Area |
|---:|---|
| 23 | `termin-graphics` |
| 15 | `tcplot` |
| 7 | `termin-inspect` |
| 6 | `termin-mesh` |
| 4 | `termin-render` |
| 4 | `termin-render-passes` |
| 2 | `termin-display` |
| 2 | `termin-engine` |
| 1 | `termin-components/termin-components-render` |

Repository-owned C/C++ diagnostics:

```text
tcplot/src/engine2d.cpp:117:20: plot_colormap: 9 parameters
tcplot/src/engine3d.cpp:180:13: push_surface_vertex: 14 parameters
tcplot/src/engine3d.cpp:276:20: surface: 10 parameters
tcplot/src/engine3d.cpp:90:6: bind_plot3d_draw_data: 9 parameters
tcplot/src/plot_view2d.cpp:101:18: scatter: 9 parameters
tcplot/src/plot_view2d.cpp:77:18: plot: 9 parameters
tcplot/src/plot_view2d.cpp:86:18: plot_colormap: 10 parameters
tcplot/src/plot_view2d_multi.cpp:125:22: add_line_colormap: 11 parameters
tcplot/src/plot_view2d_multi.cpp:154:22: add_scatter: 10 parameters
tcplot/src/plot_view2d_multi.cpp:98:22: add_line: 10 parameters
tcplot/src/plot_view3d.cpp:111:18: plot: 10 parameters
tcplot/src/plot_view3d.cpp:122:18: scatter: 10 parameters
tcplot/src/plot_view3d.cpp:133:18: surface: 11 parameters
tcplot/src/plot_view3d.cpp:142:18: surface_colormap: 13 parameters
tcplot/src/plot_view3d.cpp:193:18: set_surface_grid: 9 parameters
termin-components/termin-components-render/src/depth_pass.cpp:152:17: execute_with_data_tgfx2: 8 parameters
termin-display/include/tc_input_event.h:131:20: tc_mouse_button_event_init_source: 8 parameters
termin-display/include/tc_input_event.h:182:20: tc_scroll_event_init_source: 8 parameters
termin-engine/src/render_target_context_builder.cpp:198:6: build_render_target_contexts: 12 parameters
termin-engine/src/rendering_manager.cpp:357:38: mount_scene: 9 parameters
termin-graphics/include/tgfx/tgfx_material_handle.hpp:186:24: add_phase_from_sources: 13 parameters
termin-graphics/include/tgfx/tgfx_shader_handle.hpp:250:10: set_sources_with_entries: 8 parameters
termin-graphics/include/tgfx/tgfx_shader_handle.hpp:286:21: from_sources: 10 parameters
termin-graphics/include/tgfx2/i_render_device.hpp:168:18: blit_to_texture: 10 parameters
termin-graphics/include/tgfx2/i_render_device.hpp:181:18: clear_texture: 9 parameters
termin-graphics/src/resources/tc_shader_registry.c:231:13: tc_shader_compute_identity_hash: 9 parameters
termin-graphics/src/resources/tc_shader_registry.c:595:6: tc_shader_set_sources_with_entries: 9 parameters
termin-graphics/src/resources/tc_shader_registry.c:668:18: tc_shader_from_sources_ex: 8 parameters
termin-graphics/src/resources/tc_shader_registry.c:692:18: tc_shader_from_sources_with_entries_ex: 11 parameters
termin-graphics/src/tgfx2/canvas2d_renderer.cpp:442:24: push_quad_: 8 parameters
termin-graphics/src/tgfx2/canvas2d_renderer.cpp:467:24: append_textured_quad_: 10 parameters
termin-graphics/src/tgfx2/immediate_renderer.cpp:423:25: torus_solid: 8 parameters
termin-graphics/src/tgfx2/immediate_renderer.cpp:467:25: arrow_solid: 9 parameters
termin-graphics/src/tgfx2/opengl/opengl_render_device.cpp:1396:26: blit_to_texture: 10 parameters
termin-graphics/src/tgfx2/opengl/opengl_render_device.cpp:1465:26: clear_texture: 9 parameters
termin-graphics/src/tgfx2/render_context.cpp:1442:22: draw_indexed_instanced: 9 parameters
termin-graphics/src/tgfx2/tc_shader_bridge.cpp:1107:13: compile_engine_shader_stage_artifact: 8 parameters
termin-graphics/src/tgfx2/text2d_renderer.cpp:178:22: draw: 9 parameters
termin-graphics/src/tgfx2/text3d_renderer.cpp:142:22: draw: 8 parameters
termin-graphics/src/tgfx2/texture_pool.cpp:119:24: ensure: 8 parameters
termin-graphics/src/tgfx2/vulkan/vulkan_render_device.cpp:1505:26: blit_to_texture: 10 parameters
termin-graphics/src/tgfx2/vulkan/vulkan_render_device.cpp:1642:26: clear_texture: 9 parameters
termin-graphics/src/tgfx_texture_handle.cpp:9:22: from_data: 10 parameters
termin-inspect/include/tc_inspect_cpp.hpp:1015:5: InspectAccessorFieldChoicesRegistrar<C, T>: 9 parameters
termin-inspect/include/tc_inspect_cpp.hpp:490:10: add: 8 parameters
termin-inspect/include/tc_inspect_cpp.hpp:530:10: add_with_callbacks: 9 parameters
termin-inspect/include/tc_inspect_cpp.hpp:826:6: register_inspect_field: 8 parameters
termin-inspect/include/tc_inspect_cpp.hpp:932:5: InspectFieldRegistrar<C, T>: 8 parameters
termin-inspect/include/tc_inspect_cpp.hpp:950:5: InspectFieldCallbackRegistrar<C, T>: 9 parameters
termin-inspect/include/tc_inspect_cpp.hpp:969:5: InspectAccessorFieldRegistrar<C, T>: 8 parameters
termin-mesh/src/resources/tc_mesh.c:653:13: tc_mesh_find_surface_edge_filtered: 10 parameters
termin-mesh/src/resources/tc_mesh.c:955:6: tc_mesh_find_surface_edge_aligned: 8 parameters
termin-mesh/src/resources/tc_mesh.c:979:6: tc_mesh_find_surface_edge_aligned_metric: 9 parameters
termin-mesh/src/resources/tc_primitive_mesh.c:37:13: set_vertex: 10 parameters
termin-mesh/src/tgfx_mesh_handle.cpp:175:16: from_interleaved: 8 parameters
termin-mesh/src/tgfx_mesh_handle.cpp:225:16: from_interleaved_with_submeshes: 9 parameters
termin-render-passes/src/color_pass.cpp:146:12: ColorPass: 8 parameters
termin-render-passes/src/color_pass.cpp:582:17: execute_with_data: 12 parameters
termin-render-passes/src/shadow_camera.cpp:385:20: fit_shadow_frustum_for_cascade: 9 parameters
termin-render-passes/src/shadow_pass.cpp:417:42: execute_shadow_pass_tgfx2: 8 parameters
termin-render/include/termin/lighting/shadow.hpp:65:10: add_entry: 8 parameters
termin-render/src/fbo_pool.cpp:6:15: ensure_native: 8 parameters
termin-render/src/frame_graph_debugger_core.cpp:222:27: render_in_current_pass: 8 parameters
termin-render/src/frame_graph_debugger_core.cpp:267:27: render: 9 parameters
```

Third-party header diagnostics observed during the same run:

```text
termin-thirdparty/manifold/include/manifold/linalg.h:2581:30: frustum_matrix: 8 parameters
termin-thirdparty/stb/stb_truetype.h:1227:12: stbtt__close_shape: 10 parameters
termin-thirdparty/stb/stb_truetype.h:1560:16: stbtt_GetGlyphBitmapBoxSubpixel: 10 parameters
termin-thirdparty/stb/stb_truetype.h:1578:16: stbtt_GetGlyphBitmapBox: 8 parameters
termin-thirdparty/stb/stb_truetype.h:1583:16: stbtt_GetCodepointBitmapBoxSubpixel: 10 parameters
termin-thirdparty/stb/stb_truetype.h:1588:16: stbtt_GetCodepointBitmapBox: 8 parameters
termin-thirdparty/stb/stb_truetype.h:2252:13: stbtt__rasterize: 12 parameters
termin-thirdparty/stb/stb_truetype.h:2317:12: stbtt__tesselate_curve: 10 parameters
termin-thirdparty/stb/stb_truetype.h:2407:16: stbtt_Rasterize: 12 parameters
termin-thirdparty/stb/stb_truetype.h:2424:26: stbtt_GetGlyphBitmapSubpixel: 10 parameters
termin-thirdparty/stb/stb_truetype.h:2464:26: stbtt_GetGlyphBitmap: 8 parameters
termin-thirdparty/stb/stb_truetype.h:2469:16: stbtt_MakeGlyphBitmapSubpixel: 10 parameters
termin-thirdparty/stb/stb_truetype.h:2488:16: stbtt_MakeGlyphBitmap: 8 parameters
termin-thirdparty/stb/stb_truetype.h:2493:26: stbtt_GetCodepointBitmapSubpixel: 10 parameters
termin-thirdparty/stb/stb_truetype.h:2498:16: stbtt_MakeCodepointBitmapSubpixel: 10 parameters
termin-thirdparty/stb/stb_truetype.h:2503:26: stbtt_GetCodepointBitmap: 8 parameters
termin-thirdparty/stb/stb_truetype.h:2508:16: stbtt_MakeCodepointBitmap: 8 parameters
termin-thirdparty/stb/stb_truetype.h:2519:15: stbtt_BakeFontBitmap: 9 parameters
termin-thirdparty/stb/stb_truetype.h:2565:16: stbtt_GetBakedQuad: 8 parameters
termin-thirdparty/stb/stb_truetype.h:3018:16: stbtt_GetPackedQuad: 8 parameters
```

## Observations

- Ruff can enforce the Python rule directly with `PLR0913` and
  `[lint.pylint] max-args = 7`.
- clang-tidy can enforce the C/C++ rule through
  `readability-function-size.ParameterThreshold`.
- The current `run-lint-cpp.sh` translation-unit filter excludes
  `termin-thirdparty`, but the `HEADER_FILTER` still matches
  `termin-thirdparty` because it starts with `termin-`. If this check is added
  to the normal C/C++ lint flow, the header filter should be tightened or an
  exclude filter should be introduced first.
- Several findings are public or semi-public C/C++ APIs where immediate
  signature changes would be breaking. Those should probably move toward typed
  parameter objects or option structs rather than local suppressions.
- The Python editor menu wiring is the most obvious architectural smell. The
  callbacks should likely be grouped into menu/action models instead of passed
  as dozens of flat constructor arguments.

## Suggested Cleanup Order

1. Fix the C/C++ header filter so future exploratory checks do not report
   third-party headers.
2. Refactor the Python editor menu/controller callback bundles. This removes
   the largest outliers and gives the rule a cleaner baseline.
3. Convert build pipeline functions to typed option/context objects.
4. Audit graphics/rendering APIs separately, because many are public wrapper or
   backend interfaces and may need compatibility planning.
5. Enable the rule only after the baseline is close to zero, or add a narrow
   per-file ignore list with explicit cleanup tasks.
