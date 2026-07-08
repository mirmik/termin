# Function Parameter Count Lint Audit

Date: 2026-07-07

This audit checks how noisy a "more than seven parameters" lint gate would be
for Python and C/C++ sources.

The repository configuration was not changed during this audit. The current
Python Ruff baseline in `ruff.toml` selects only `B`, `E9`, and `F`; it does
not enable `PLR0913`.

## Summary

- Python/Ruff `PLR0913` with `lint.pylint.max-args = 7`: 52 diagnostics
  after the first editor menu cleanup, down from the original 54.
- Original C/C++/clang-tidy `readability-function-size.ParameterThreshold = 7`
  baseline: 84 diagnostics total.
- Of the original C/C++ diagnostics, 64 were in repository-owned code and 20
  were in `termin-thirdparty` headers included through repository translation
  units.
- After the first C++ cleanup, geometry type rename, `tcplot` API cleanup,
  Canvas2D quad cleanup, immediate solid primitive cleanup, texture/FBO
  descriptor cleanup, text draw options cleanup, indexed-instanced draw
  command cleanup, mesh interleaved create-info cleanup, frame graph presenter
  draw command cleanup, scene mount request cleanup, render-pass execute
  data/config cleanup, and shadow-pass request cleanup on 2026-07-07,
  the C/C++ source baseline dropped to 9 repository-owned diagnostics with the
  tightened third-party header filter.
- Follow-up cleanup on 2026-07-08 resolved those 9 source diagnostics in
  engine/graphics/mesh. Targeted checks over the touched translation units now
  report no remaining source diagnostics; the visible repeated diagnostics are
  header-only `termin-inspect` registration helpers.
- A later 2026-07-08 pass resolved the `termin-inspect` header helpers plus
  the newly visible repository-owned `termin-display` input-event and
  `termin-render` shadow-array helpers. The C/C++ repository-owned parameter
  baseline is now zero with this check; remaining output is third-party noise.

The result is small enough to enable eventually, but not as a drive-by config
change. The editor menu/controller constructors and several rendering/graphics
APIs need deliberate API shape work before this becomes a clean CI rule.

## Cleanup Progress

2026-07-07:

- Moved `Color4` and `Size2i` from `termin-graphics/include/tgfx/types.hpp`
  to `termin-base/include/termin/geom`.
- Renamed the min/max `Rect2i` shape to `Bounds2i` and kept it in
  `termin-base/include/termin/geom`.
- Renamed the render x/y/width/height rectangle shape to `Rect2i` and moved it from
  `termin-render/include/termin/render/frame_pass.hpp` into
  `termin-base/include/termin/geom`.
- Kept `tgfx/types.hpp` as a compatibility include for existing graphics users.
- Updated `tgfx2::IRenderDevice::blit_to_texture` to take source/destination
  `Bounds2i` values.
- Updated `tgfx2::IRenderDevice::clear_texture` to take `Color4` and `Bounds2i`.
- Updated OpenGL, Vulkan, D3D11 declarations/implementations and current call
  sites.
- Updated `tcplot` C++ APIs and helpers to use series/surface option structs
  instead of flat scalar style arguments.
- Added `Bounds2f` and `Rect2f` to `termin-base` geometry types and used them
  to collapse `Canvas2DRenderer` quad/UV helper parameters.
- Updated `tgfx2::ImmediateRenderer::torus_solid` and `arrow_solid` to take
  typed `TorusSolidSpec`/`ArrowSolidSpec` values while keeping the Python
  binding call shape compatible.
- Updated `tgfx2::TexturePool` and `RenderTargetPool` to take existing
  descriptor structs instead of flat texture/render-target scalar sets.
- Updated `TcTexture::from_data` to take `TcTextureCreateInfo` with typed pixel
  data and transform fields while keeping the Python binding call shape
  compatible.
- Updated `tgfx2::Text2DRenderer::draw` and `Text3DRenderer::draw` to take
  typed draw option structs while keeping the Python binding call shape
  compatible.
- Updated `tgfx2::RenderContext2::draw_indexed_instanced` to take a typed
  `IndexedInstancedDraw` command struct.
- Updated `TcMesh::from_interleaved` to take a typed `TcMeshCreateInfo`, kept
  the Python binding call shape compatible, and collapsed the primitive mesh
  vertex helper to a typed local vertex value.
- Updated `FrameGraphPresenter::render` and `render_in_current_pass` to take a
  typed `FrameGraphPresenterDraw` command while keeping the Python binding call
  shape compatible.
- Updated `RenderingManager::mount_scene` to take a typed `SceneMountRequest`.
- Re-ran the C++ baseline after merging the neighboring render-pass changes;
  the count stayed at 14 and line numbers were refreshed.
- Updated `DepthPass::execute_with_data_tgfx2` to take a typed
  `DepthPassExecuteData` value.
- Updated `ColorPass` construction to take `ColorPassConfig` and
  `ColorPass::execute_with_data` to take `ColorPassExecuteData`, while keeping
  Python and C# binding call shapes compatible.
- Updated `LightingUBO::update_from_lights` to take `std::span<const Light>` so
  render-pass execute data can carry non-owning light views.
- Updated `fit_shadow_frustum_for_cascade` to take a typed
  `ShadowCascadeFitRequest`.
- Updated `ShadowPass::execute_shadow_pass_tgfx2` to take a typed
  `ShadowPassExecuteData` with non-owning light views.
- C++ repository-owned diagnostics dropped from 64 to 9.

2026-07-08:

- Updated mesh query/raycast APIs so points, directions, normals, and hit
  locations use `Vec3f`/`tc_vec3f` instead of domain `float[3]` arrays.
- Updated shader registry APIs to use `tc_shader_source_desc` and
  `tc_shader_create_desc` instead of flat source/name/path/entry/language
  argument lists.
- Updated `termin::TcShader` to use `TcShaderSources` and
  `TcShaderCreateInfo`; Python bindings keep the old call shape as a
  compatibility adapter.
- Updated `tc_shader_bridge` stage artifact compilation to take an
  `EngineShaderStageCompileRequest`.
- Updated `TcMaterial::add_phase_from_sources` to take
  `TcMaterialPhaseFromSourcesInfo` and moved material binding internals to
  option/descriptor structs.
- Updated `termin-inspect` C++ field registration helpers to use
  `InspectFieldSpec` descriptors while keeping macro/direct-call compatibility.
- Updated input event source initializers to take event init descriptor structs.
- Updated `ShadowMapArrayResource::add_entry` to take a `ShadowMapArrayEntry`
  value instead of a flat shadow entry argument list.
- Rebuilt SDK with `./build-sdk.sh --no-wheels` and refreshed the editable test
  venv with `./setup-test-venv.sh --force`.
- Updated Python editor menu wiring so `build_editor_menu_spec` and
  `MenuBarControllerTcgui.__init__` take typed action/state/config objects
  instead of 60- and 54-argument flat dependency lists. Python `PLR0913`
  diagnostics dropped from 54 to 52.

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

Current diagnostics by area:

| Count | Area |
|---:|---|
| 11 | `termin-project-build` |
| 9 | `termin-navmesh` |
| 9 | `termin-app/termin/editor_tcgui` |
| 5 | `termin-qopt` |
| 4 | `termin-gui` |
| 4 | `termin-csg` |
| 3 | `termin-glb` |
| 2 | `termin-player` |
| 2 | `termin-components/termin-components-voxels` |
| 1 | `scripts` |
| 1 | `termin-audio` |
| 1 | `termin-inspect` |

Remaining notable highest-count definitions:

| Parameters | Definition |
|---:|---|
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

Current result: zero repository-owned C/C++ parameter-count diagnostics.

The full check was rerun over the `build/Release-lint/compile_commands.json`
repository translation units on 2026-07-08. Filtering out `/termin-thirdparty/`
from the resulting `warning: function` lines leaves no diagnostics.

The default `./run-lint-cpp.sh` clang-tidy baseline now includes
`readability-function-size` with only `ParameterThreshold = 7` enabled. The
script also passes `--exclude-header-filter` for `termin-thirdparty`, so the
rule applies to repository-owned C/C++ code without turning third-party headers
into lint failures.

After enabling the rule, the full default C/C++ lint command
`./run-lint-cpp.sh --no-configure --jobs 4` passed over all 282 matched
translation units.

The 9 source diagnostics listed in the previous baseline were resolved by the
2026-07-08 cleanup. Targeted clang-tidy checks over the touched translation
units reported no remaining source diagnostics in:

```text
termin-graphics/src/resources/tc_shader_registry.c
termin-graphics/src/tgfx2/tc_shader_bridge.cpp
termin-materials/python/bindings/material_bindings.cpp
termin-navmesh/src/detour_navmesh_asset_utils.cpp
termin-runtime/src/runtime_package.cpp
termin-display/src/tc_viewport_input_manager.c
termin-render-passes/src/shadow_pass.cpp
termin-components/termin-components-render/src/depth_pass.cpp
termin-components/termin-components-render/src/normal_pass.cpp
```

The one-off exploratory audit command used before the script change still let
some `termin-thirdparty` headers and sources through. That run found 67
third-party `warning: function` lines. Earlier examples included:

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
- The normal `run-lint-cpp.sh` flow now excludes `termin-thirdparty` both from
  translation units and from header diagnostics.
- Header diagnostics from template/header-only helpers repeat once per
  translation unit. The current C/C++ table above intentionally reports unique
  repository-owned `.c`/`.cpp` source diagnostics, not repeated header hits.
- Several findings are public or semi-public C/C++ APIs where immediate
  signature changes would be breaking. Those should probably move toward typed
  parameter objects or option structs rather than local suppressions.
- The Python editor menu wiring is the most obvious architectural smell. The
  callbacks should likely be grouped into menu/action models instead of passed
  as dozens of flat constructor arguments.

## Suggested Cleanup Order

1. Refactor the Python editor menu/controller callback bundles. This removes
   the largest outliers and gives the rule a cleaner baseline.
2. Convert build pipeline functions to typed option/context objects.
3. Audit graphics/rendering APIs separately, because many are public wrapper or
   backend interfaces and may need compatibility planning.
