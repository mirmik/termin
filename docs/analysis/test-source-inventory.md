# Test Source Inventory

Generated for incremental test-suite pruning.

Scope:
- Includes test source and test-support files under repository test areas.
- Excludes `.venv`, `build`, `sdk`, `termin-thirdparty`, nested `build/`, and `__pycache__`.
- This is a working audit checklist, not a claim that listed tests are useful.

Current source counts:
- Total listed entries: 168
- Current existing listed files: 166
- Pruned entries: 2
- Python-side entries: 123
- C/C++ entries: 44
- CMake test list entries: 1

Status values:
- `pending`: not reviewed in this audit checklist yet
- `reviewed`: reviewed and kept as useful
- `pruned`: source was removed or consolidated
- `needs-work`: contains useful coverage but should be reshaped

## Inventory

| Status | Kind | Path | Notes |
| --- | --- | --- | --- |
| reviewed | c | `termin-app/core_c/tests/test_main.c` | Legacy C runner is broad but concrete: core math, entity pool/hierarchy, inspect dispatch, resource map, vertex layout, and scene extension re-registration. Runner stdout is diagnostic, not debug-only. |
| reviewed | cpp | `termin-app/cpp/tests/main.cpp` | Guard test entrypoint plus render-components dynamic load; no redundant assertions found. |
| reviewed | cpp | `termin-app/cpp/tests/tests_binding.cpp` | Nanobind wrapper for guard C++ tests; support code only. |
| reviewed | cpp | `termin-app/cpp/tests/tests_general_pose3.cpp` | Compact value tests for Termin axes and GeneralPose3 scale/compose/inverse behavior. |
| reviewed | cpp | `termin-app/cpp/tests/tests_inspect_registry.cpp` | Covers C++ inspect registry inheritance, get/set, and action callback behavior with concrete state changes. |
| reviewed | cpp | `termin-app/cpp/tests/tests_orbit_camera_controller.cpp` | Verifies viewport/render-target camera filtering before applying orbit scroll events. |
| reviewed | cpp | `termin-app/cpp/tests/tests_rendering_manager.cpp` | Broad rendering manager/graph compiler regression coverage with concrete resource naming, lifecycle, viewport, render target, and default pipeline assertions. |
| needs-work | cpp | `termin-app/cpp/tests/tests_shader_parser_std140.cpp` | Useful shader/std140 regression coverage, but very large and repeats schema/value helpers and parse-error patterns; should be split or parameterized. |
| reviewed | python-support | `termin-app/termin/tests/__init__.py` | Empty package marker only. |
| reviewed | python | `termin-components/termin-components-kinematic/tests/aabb_test.py` | Replaced private version-counter assertions with behavioral child/parent relocation AABB recompilation checks; child coverage now starts outside the parent and caught/fixed stale TransformAABB cache invalidation. Verified by `./run-tests-python.sh termin-components/termin-components-kinematic/tests/test_general_transform3.py termin-components/termin-components-kinematic/tests/aabb_test.py termin-components/termin-components-kinematic/tests/kinematic_chain_test.py termin-components/termin-components-kinematic/tests/transform_test.py`. |
| pruned | python-support | `termin-app/tests/api.py` | Removed dead standalone unittest runner that imported missing `motor_test`; no repository references besides inventory. |
| needs-work | python | `termin-default-assets/tests/asset_plugin_test.py` | Default asset/plugin/resource type matrices duplicate other manifest/plugin tests; consolidate around one canonical expected table. |
| reviewed | python | `termin-collision/tests/collider_test.py` | Removed stale migration comments and manual runner; remaining collider/ray cases assert concrete distances and contact points. |
| reviewed | python-support | `termin-app/tests/conftest.py` | Empty pytest support file only. |
| reviewed | python | `termin-app/tests/editor_commands_test.py` | Covers real command execution, undo/redo, selection, and scene lifetime behavior. |
| reviewed | python | `termin-render/tests/framegraph_test.py` | Framegraph scheduling coverage now uses shared `tests/framegraph_test_helpers.py` instead of duplicating DummyPass/build_schedule with internal-points tests; keeps concrete ordering/conflict/inplace assertions. Verified by `./run-tests-python.sh termin-render/tests/framegraph_test.py termin-render/tests/test_framegraph_internal_points.py termin-render/tests/test_framegraph_presenter_bindings.py`. |
| reviewed | python | `termin-components/termin-components-kinematic/tests/kinematic_chain_test.py` | Basis sensitivity test now contrasts world-space +Y against basis-local +X and shares chain setup through a helper, making the basis contract explicit. Verified by `./run-tests-python.sh termin-components/termin-components-kinematic/tests/test_general_transform3.py termin-components/termin-components-kinematic/tests/aabb_test.py termin-components/termin-components-kinematic/tests/kinematic_chain_test.py termin-components/termin-components-kinematic/tests/transform_test.py`. |
| reviewed | python | `termin-components/termin-components-kinematic/tests/kinematic_test.py` | Replaced wildcard import and fixed copy-paste child-count assertion; remaining test covers Rotator3 link/parent invariants. |
| reviewed | python | `termin-components/termin-components-kinematic/tests/transform_test.py` | Trent transform tree setup, expected pose dictionaries, and roundtrip assertions now use shared helpers instead of duplicating expected trees across tests. Verified by `./run-tests-python.sh termin-components/termin-components-kinematic/tests/test_general_transform3.py termin-components/termin-components-kinematic/tests/aabb_test.py termin-components/termin-components-kinematic/tests/kinematic_chain_test.py termin-components/termin-components-kinematic/tests/transform_test.py`. |
| reviewed | python | `termin-navmesh/tests/pathfinding_test.py` | Removed unused data/import and manual runner; remaining adjacency, point lookup, A*, graph, and ray-triangle tests have concrete expected results. |
| reviewed | python | `termin-physics/tests/test_energy.py` | Removed debug output/manual runner and unused imports; energy drift tests remain useful integration coverage. |
| reviewed | python | `termin-physics/tests/test_rigid_body.py` | Removed manual runner and unused import; remaining rigid-body tests assert concrete settling, contact, inertia, and static-body contracts. |
| reviewed | python | `termin-base/tests/python/pose2_test.py` | Removed script shebang/manual runner; remaining Pose2 checks cover explicit transform, inverse, interpolation, and helper contracts. |
| needs-work | python | `termin-base/tests/python/pose_test.py` | Removed unused import/variable and same-API expected calculation; looking_at and several roundtrip checks still need stronger independent oracles. |
| reviewed | python | `termin-materials/tests/test_shader_parser.py` | String-heavy but active Slang/material parsing contract rather than debug-only coverage. |
| reviewed | python | `termin-default-assets/tests/test_default_asset_plugin_registry.py` | Moved default asset plugin type/extension registry contract out of termin-app; canonical matrix now lives with termin-default-assets. |
| reviewed | python | `termin-animation/tests/test_canonical_animation_imports.py` | Removed legacy/source/existence migration checks for deleted facade trees; remaining tests keep the canonical animation import boundary. |
| reviewed | python | `termin-engine/tests/test_default_pipeline_specs.py` | Removed self-evident import assert; remaining tests cover default pipeline render-target formats/MSAA and ResolvePass defaults/order. |
| needs-work | python | `termin-navmesh/tests/test_edge_flipping.py` | Removed oracle-free circumcircle boundary test, cocircular len-only flip test, debug prints, and manual runner; several optimized/refined cases still check mostly counts. |
| needs-work | python | `termin-app/tests/test_editor_mcp_server.py` | Useful MCP coverage, but repeats thread/deadline/process_pending loop helpers across several tests. |
| reviewed | python | `termin-app/tests/test_editor_python_executor.py` | Added deadline to external-thread queue test; remaining cases cover output, context refresh, helper injection, and script errors. |
| reviewed | python | `termin-app/tests/test_editor_shader_runtime.py` | Strengthened missing-slangc case to assert error logging and no configure call. |
| reviewed | python | `termin-app/tests/test_framegraph_debugger_model_disconnect.py` | Replaced importlib loader with package import; remaining tests cover debugger disconnect and capture info formatting. |
| reviewed | python | `termin-render/tests/test_framegraph_internal_points.py` | Debug internal-point/window and disabled-pass checks now share the framegraph scheduling helper with `framegraph_test.py`; remaining tests cover schedule/alias behavior around debug configuration rather than source scanning. Verified by `./run-tests-python.sh termin-render/tests/framegraph_test.py termin-render/tests/test_framegraph_internal_points.py termin-render/tests/test_framegraph_presenter_bindings.py`. |
| needs-work | python | `termin-render/tests/test_framegraph_presenter_bindings.py` | Source-scanning C++ strings are brittle; needs behavioral resource layout/bind-by-name contract. |
| needs-work | python | `termin-navmesh/tests/test_funnel_algorithm.py` | Removed debug prints, manual runner, local triarea copy test, and dead geometry assignment; non-convex funnel cases still assert only endpoints instead of no-cut geometry. |
| reviewed | python | `termin-app/tests/test_game_mode_model.py` | Covers real editor/runtime game mode state transitions. |
| reviewed | python | `termin-app/tests/test_game_mode_ui_controller.py` | Covers UI controller state transitions for game mode controls. |
| needs-work | python | `termin-base/tests/python/test_general_pose3.py` | Several copy/matrix/roundtrip tests check only partial value state and need fuller rotation/scale assertions. |
| reviewed | python | `termin-components/termin-components-kinematic/tests/test_general_transform3.py` | Direction helper coverage now parameterizes explicit calls for forward/right/up and distance scaling, asserting these helpers return transformed scaled vectors rather than normalized unit axes. Verified by `./run-tests-python.sh termin-components/termin-components-kinematic/tests/test_general_transform3.py termin-components/termin-components-kinematic/tests/aabb_test.py termin-components/termin-components-kinematic/tests/kinematic_chain_test.py termin-components/termin-components-kinematic/tests/transform_test.py`. |
| reviewed | python | `termin-app/tests/test_gltf_drag_drop.py` | Covers UI, viewport, and scene tree GLTF drag/drop routing with concrete expected operations. |
| reviewed | python | `termin-glb/tests/test_glb_loader.py` | Exercises external-bin GLTF loading, texture/material fields, and lazy GLBAsset source loading. |
| reviewed | python | `termin-inspect/tests/test_inspect_singleton_topology.py` | Checks native inspect/kind registry singleton addresses agree across module facades. |
| reviewed | python | `termin-app/tests/test_launcher_process_mode.py` | Uses monkeypatched spawn/exec calls to cover launcher process mode and LD_LIBRARY_PATH wiring. |
| reviewed | python | `termin-default-assets/tests/test_material_asset_texture_persistence.py` | Keeps material texture asset persistence regression coverage. |
| reviewed | python | `termin-app/tests/test_material_inspector_texture.py` | Default texture test now asserts the exact builtin texture UUID for both `white` and `normal` defaults instead of only checking a valid `TcTexture` handle. Verified by `./run-tests-python.sh termin-app/tests/test_material_inspector_texture.py`. |
| reviewed | python | `termin-components/termin-components-render/tests/python/test_material_pass_serialization.py` | Covers material pass texture resource serialization through pipeline copy and material UUID reference loading. |
| reviewed | python | `termin-materials/tests/test_material_registry_copy.py` | Covers material registry copy behavior and runtime asset lifecycle regression. |
| reviewed | python | `termin-player/tests/test_mcp_base.py` | Covers owner-thread Python execution, shared/player MCP tool exposure, config merging, and screenshot response structure. |
| reviewed | python | `termin-default-assets/tests/test_mesh_spec_defaults.py` | Covers default axis conversion and explicit identity axis preservation. |
| reviewed | python | `termin-navmesh/tests/test_navmesh_package_facade.py` | Keeps public facade import boundary lightweight and skips native-dependent export only when SDK library is unavailable. |
| reviewed | python | `termin-components/termin-components-mesh/tests/test_procedural_mesh_component.py` | Covers procedural mesh regeneration reusing the existing TcMesh handle. |
| reviewed | python | `termin-app/tests/test_procedural_mesh_editor_extension.py` | Covers shared document controller wiring, panel state, and viewport drag edits for contour/path/wall operations. |
| reviewed | python | `termin-app/tests/test_project_file_action_controller.py` | Covers scene/prefab activation, text-editor fallback, and inspector routing by extension. |
| reviewed | python | `termin-app/tests/test_project_file_watcher.py` | Covers project file watcher behavior with concrete filesystem events. |
| reviewed | python | `termin-app/tests/test_project_operations.py` | Covers project operation behavior rather than import smoke. |
| reviewed | python | `termin-project/tests/test_project_settings.py` | Compact settings contract with concrete expected values. |
| reviewed | python | `termin-app/tests/test_rendering_model_render_target_restore.py` | Serialization roundtrip cases are now table-driven by restored-field contract while keeping explicit pipeline params, format, clear-setting, and kind assertions. Verified by `./run-tests-python.sh termin-app/tests/test_rendering_model_render_target_restore.py`. |
| reviewed | python | `termin-project-build/tests/test_runtime_package_exporter.py` | Covers runtime package export, desktop bundle contract, shader artifacts, and cleanup of stale broad-copy output. |
| reviewed | python | `termin-app/tests/test_scene_file_model.py` | Replaced dynamic import boilerplate with package import; remaining test checks scene-name stem behavior. |
| reviewed | python | `termin-app/tests/test_scene_manager_viewer.py` | Replaced importlib loader helper with package import; remaining test checks scene handle formatting. |
| reviewed | python | `termin-components/termin-components-render/tests/python/test_screen_point_to_ray.py` | Replaced symmetry/not-NaN smoke checks with finite/unit ray assertions and concrete expected center, horizontal edge, vertical edge, and corner directions for the default Y-forward projection. Verified by `./run-tests-python.sh termin-components/termin-components-render/tests/python/test_screen_point_to_ray.py`. |
| needs-work | python | `termin-app/tests/test_shader_tool_resolution.py` | Linux no-op is now an explicit skip and helper avoids setattr, but test still relies on dynamic source loading for Windows path logic. |
| reviewed | python | `termin-app/tests/test_tcgui_framegraph_debugger_handle.py` | Replaced dynamic source load with package import; remaining tests cover teardown idempotence and capture preview texture parameters. |
| reviewed | python | `termin-app/tests/test_tcgui_pipeline_editor_window.py` | Covers pipeline graph load/save, native/material pass metadata sockets, render-target nodes, and inline param widgets. |
| reviewed | python | `termin-app/tests/test_tcgui_pipeline_inspector.py` | Covers readonly compiled file mode, compile failure display, and spec format defaults. |
| reviewed | python | `termin-app/tests/test_tcgui_project_browser.py` | Covers clipboard copy and STL mesh subtitle classification. |
| reviewed | python | `termin-app/tests/test_tcgui_render_target_inspector.py` | Removed unreachable stub return; remaining inspector tests exercise scene/camera/resource selection behavior. |
| reviewed | python | `termin-app/tests/test_texture_inspector.py` | Covers opening an unregistered texture file and loading saved TextureSpec display flags. |
| reviewed | python | `termin-default-assets/tests/test_texture_lazy_registration.py` | Keeps texture lazy-registration lifecycle regression coverage. |
| reviewed | python | `termin-app/tests/test_vec3_list_field_widget.py` | Covers Vec3 list row edits/rebuilds and factory routing for vec3 lists/enums. |
| reviewed | python | `termin-app/tests/test_voxel_shader.py` | Added timeout to subprocess import-order smoke; remaining checks cover shader catalog/material layout contract. |
| reviewed | python | `termin-app/tests/undo_stack_test.py` | Covers real undo/redo stack scenarios and scene lifetime behavior. |
| reviewed | python | `termin-base/tests/python/util_test.py` | Replaced wildcard import; remaining qslerp test has a concrete halfway quaternion expectation. |
| needs-work | python | `termin-app/tests/voxels_test.py` | Removed unused import/manual runner; voxelizer transform and origin-reset tests still have broad or potentially questionable oracles. |
| reviewed | python | `termin-assets/tests/test_asset_contracts.py` | Removed redundant export smoke covered by module imports; kept registry, spec migration, and entry-point discovery checks. |
| reviewed | python | `termin-base/tests/python/test_python_package_install_order.py` | Keeps shared Python package manifest topological against setup.py/pyproject dependencies. |
| reviewed | python | `termin-base/tests/python/test_tcbase_api.py` | Consolidated overlapping enum binding checks; remaining settings roundtrip covers grouped persistence. |
| reviewed | cpp | `termin-base/tests/test_orbit_camera.cpp` | Covers orbit camera defaults, fit_bounds clip/target update, and center-ray direction with concrete values. |
| reviewed | c | `termin-base/tests/test_tc_value.c` | Removed self-evident struct-literal field echo test; remaining dlist and tc_value tests exercise real container/value behavior. |
| reviewed | python | `termin-build-tools/tests/test_sdk_orchestrator.py` | Build-tool regression coverage for SDK orchestration, package installs, artifact manifests, and duplicate-library checks. |
| reviewed | cpp | `termin-collision/tests/main.cpp` | Guard test entrypoint only. |
| reviewed | cpp | `termin-collision/tests/tests_colliders.cpp` | Covers collider centers, ray hits/misses, analytic distances, scale effects, and cross-type collision dispatch with concrete expected values. |
| reviewed | cpp | `termin-collision/tests/tests_collision.cpp` | Broad BVH/world/manifold/AttachedCollider coverage; assertions check current collider state, query results, ray ordering, and manifold pairs rather than smoke-only behavior. |
| reviewed | cpp | `termin-collision/tests/tests_convex_hull_collider.cpp` | Removed duplicate using declaration; remaining convex-hull support/AABB/GJK/raycast/dispatch tests have concrete expected values. Verified by `ctest --test-dir build/Release-tests -R '^termin_collision_tests$' --output-on-failure`. |
| reviewed | cpp | `termin-collision/tests/tests_gjk.cpp` | Keeps support-function, separated/touching/penetrating, and analytic-comparison checks with explicit distance expectations. |
| reviewed | cpp | `termin-collision/tests/tests_quickhull.cpp` | Removed contradictory exact cube face-count assertion and kept representation-tolerant hull range; remaining QuickHull cases cover vertices, normals, containment, duplicates, and degenerates. Verified by `ctest --test-dir build/Release-tests -R '^termin_collision_tests$' --output-on-failure`. |
| reviewed | python | `termin-components/termin-components-foliage/tests/test_foliage_asset_plugin.py` | Runtime plugin registration covers asset catalog record and native foliage handle registry. |
| reviewed | python | `termin-components/termin-components-render/tests/python/test_render_components_api.py` | LineRenderer mode/material/inspect coverage and depth-pass binding regression have concrete behavioral assertions. |
| reviewed | cmake | `termin-csg/tests/CMakeLists.txt` | Minimal CTest registration for the native CSG smoke/regression executable. |
| reviewed | cpp | `termin-csg/tests/csg_basic_test.cpp` | Compact native API coverage for box/sphere/subtract/extrude/to_mesh3; overlaps Python behavior only enough to keep the C++ facade checked. Verified by `ctest --test-dir build/Release-tests -R '^termin_csg_basic_test$' --output-on-failure`. |
| needs-work | python | `termin-csg/tests/test_csg_python.py` | Broad CAD/CSG regression coverage is useful, but the file mixes document/edit/controller/CadApp layers and repeats boolean/panel workflows. |
| reviewed | cpp | `termin-display/tests/test_backend_window_triangle.cpp` | Backend/window triangle smoke intentionally prints selected backend, timeout, and frame count for CI diagnosis; exercises real SDLBackendWindow/tgfx2 presentation path. Verified by `ctest --test-dir build/Release-tests -R '^(display_input_router_test|backend_window_triangle)$' --output-on-failure`. |
| reviewed | cpp | `termin-display/tests/test_display_input_router.cpp` | Headless routing regression with concrete left/right viewport press/release counts and failure-only stderr. Verified by `ctest --test-dir build/Release-tests -R '^(display_input_router_test|backend_window_triangle)$' --output-on-failure`. |
| reviewed | cpp | `termin-graphics/tests/main.cpp` | Guard test entrypoint shared by `tgfx_tests` and `tgfx2_device_factory_test`. |
| needs-work | python | `termin-graphics/tests/python/test_termin_shaderc_cli.py` | Large shaderc CLI regression file is useful, but fake slangc/reflection builders and POSIX-only skips should be consolidated into portable fixtures. |
| reviewed | python | `termin-graphics/tests/python/test_tgfx_api.py` | Removed self-evident enum/renderer construction checks; remaining binding smoke covers values, shader metadata, material entries, and line params. |
| reviewed | python | `termin-graphics/tests/python/test_tgfx_shader_runtime.py` | Converted Linux no-op Windows case to explicit skip and isolated fake tcbase through monkeypatch. |
| reviewed | c | `termin-graphics/tests/test_mesh.c` | Legacy C harness is stdout-heavy but checks mesh registry, data upload/versioning, vertex layout, and ref-count lifecycle with explicit failure exits. Verified by graphics CTest batch. |
| reviewed | cpp | `termin-graphics/tests/test_per_pipeline_layout.cpp` | Wired into CMake/CTest as `tgfx2_per_pipeline_layout_test`; covers per-pipeline Vulkan descriptor layout creation and bound resource set draw with concrete center-pixel assertion. Verified by `ctest --test-dir build/Release-tests -R '^tgfx2_per_pipeline_layout_test$' --output-on-failure`. |
| reviewed | cpp | `termin-graphics/tests/test_render_context2.cpp` | OpenGL render-context/pipeline-cache regression checks pixels, FSQ, cache reuse, and line depth behavior; diagnostic stdout is tied to pixel failures. Verified by graphics CTest batch. |
| reviewed | cpp | `termin-graphics/tests/test_tgfx2_device_factory.cpp` | Removed three `CHECK(true)` Windows no-op cases by not registering POSIX-only shader-runtime tests there; remaining tests cover backend env parsing, shader metadata/artifact paths, stale artifact invalidation, sidecar layout loading, line mesh, and mesh bridge behavior. Verified by graphics CTest batch. |
| reviewed | cpp | `termin-graphics/tests/test_tgfx2_line_mesh_builder.cpp` | Compact geometry checks for invalid input, straight line quad, duplicate points, and round-cap tessellation counts. Verified through `tgfx2_device_factory_test`. |
| needs-work | cpp | `termin-graphics/tests/test_tgfx2_sdf.cpp` | Added assertions for texture handles, positive measurements, glyph presence/metrics/UVs, and nonzero bitmap/SDF atlas signal; target builds, but runtime verification still needs a GL-capable window/X server environment because local `tgfx2_sdf_test` is CTest-skipped with `GLFW init failed` and Xvfb could not open its display. |
| reviewed | cpp | `termin-graphics/tests/test_tgfx2_smoke.cpp` | OpenGL smoke has concrete readback checks for screen, render texture, and required shader artifacts despite verbose diagnostic output. Verified by graphics CTest batch. |
| reviewed | cpp | `termin-graphics/tests/test_tgfx2_tc_mesh_bridge.cpp` | Focused semantic filtering and standard-location fallback checks for mesh bridge layout conversion. Verified through `tgfx2_device_factory_test`. |
| reviewed | cpp | `termin-graphics/tests/test_tgfx2_vulkan_smoke.cpp` | Offscreen Vulkan smoke checks upload/readback parity, depth readback, triangle pixels, transient vertex ring, and optional Slang artifact path with concrete pass/fail conditions. Verified by graphics CTest batch. |
| reviewed | cpp | `termin-graphics/tests/test_tgfx2_vulkan_window.cpp` | On-screen Vulkan swapchain/present smoke is bounded and CTest-skippable for missing runtime support; keeps end-to-end window/swapchain path covered. Verified by graphics CTest batch. |
| reviewed | cpp | `termin-graphics/tests/tests_log.cpp` | Covers log callback capture, filtering, shorthand levels, formatting, explicit levels, and no-callback branch. Verified through `tgfx_tests`. |
| reviewed | cpp | `termin-graphics/tests/tests_shader_resource_layout.cpp` | Checks resource-layout known-empty state, raw GLSL engine binding inference, and stage entry-point hashing. Verified through `tgfx_tests`. |
| reviewed | cpp | `termin-graphics/tests/tests_vertex_layout.cpp` | Vertex layout stride/offset/max/null/predefined-layout checks are low-level but concrete for the C API. Verified through `tgfx_tests`. |
| reviewed | python-support | `termin-gui/python/tests/__init__.py` | Empty package marker. |
| reviewed | python-support | `termin-gui/python/tests/conftest.py` | Shared layout helpers only; no test logic to prune. |
| needs-work | python | `termin-gui/python/tests/test_clip_stack.py` | Removed mock-only single-clip smoke; remaining mock-heavy clip-stack checks should be consolidated around production UIRenderer paths. |
| needs-work | python | `termin-gui/python/tests/test_combined_layout.py` | Useful editor/layout integration checks, but early nested smoke cases overlap hstack/vstack/editor-style coverage. |
| needs-work | python | `termin-gui/python/tests/test_editor_style_layout.py` | Removed weak Lama content smoke and strengthened narrow viewport invariant; large class groups still need parameterization/consolidation. |
| reviewed | python | `termin-gui/python/tests/test_file_dialog.py` | Consolidated parser cases into a single table while preserving empty, labeled, default, and empty-part inputs. |
| reviewed | python | `termin-gui/python/tests/test_file_grid_widget.py` | Scrollbar drag/wheel/stretch cases are behavioral and selection-sensitive. |
| reviewed | python | `termin-gui/python/tests/test_group_box.py` | Removed unused import; remaining expanded/collapsed/multiple-child/invisible-child layout checks are concrete. |
| reviewed | python | `termin-gui/python/tests/test_hstack_layout.py` | Fixed, stretch, and justify layout cases are now table-driven while keeping explicit rect expectations for each horizontal layout contract. Verified by `./run-tests-python.sh termin-gui/python/tests/test_hstack_layout.py termin-gui/python/tests/test_vstack_layout.py termin-gui/python/tests/test_splitter.py`. |
| reviewed | python | `termin-gui/python/tests/test_label_metrics.py` | Focused baseline/ascent regression with custom renderer double. |
| reviewed | python | `termin-gui/python/tests/test_list_widget.py` | Wheel consumption and scroll offset behavior differs by viewport/content height. |
| reviewed | python | `termin-gui/python/tests/test_menu.py` | Menu height clamp and wheel item lookup are concrete viewport interaction regressions. |
| reviewed | python | `termin-gui/python/tests/test_panel_layout.py` | Removed unused import; padding/compute-size/anchor checks are small and concrete. |
| reviewed | python | `termin-gui/python/tests/test_rich_text_view.py` | HTML/text parsing and clipboard selection behavior are covered with concrete assertions. |
| reviewed | python | `termin-gui/python/tests/test_scroll_area.py` | Scroll sizing, clamping, content placement, and fit behavior are compact layout regressions. |
| reviewed | python | `termin-gui/python/tests/test_splitter.py` | Drag side and min/max constraint cases are now table-driven while preserving target width assertions. Verified by `./run-tests-python.sh termin-gui/python/tests/test_hstack_layout.py termin-gui/python/tests/test_vstack_layout.py termin-gui/python/tests/test_splitter.py`. |
| reviewed | python | `termin-gui/python/tests/test_tabs.py` | Tab change callback and unchanged-index behavior are distinct small interaction checks. |
| reviewed | python | `termin-gui/python/tests/test_text_editing.py` | Copy/cut/paste/delete behavior covers text input and text area selection paths. |
| reviewed | python | `termin-gui/python/tests/test_tree_widget.py` | Scrollbar visibility, drag, and wheel-model sync are concrete behavior checks. |
| reviewed | python | `termin-gui/python/tests/test_ui_root_layout.py` | Root layout edge cases cover anchored computed size, explicit viewport fill, and zero-size fallback. |
| reviewed | python | `termin-gui/python/tests/test_vstack_layout.py` | Fixed, stretch, and justify layout cases are now table-driven while keeping explicit rect expectations for each vertical layout contract. Verified by `./run-tests-python.sh termin-gui/python/tests/test_hstack_layout.py termin-gui/python/tests/test_vstack_layout.py termin-gui/python/tests/test_splitter.py`. |
| reviewed | cpp | `termin-inspect/tests/test_cpp_inspect.cpp` | C++ inspect registry tests cover inherited fields, serialize/deserialize, choices, string enum fields, and accessor choices with concrete state changes. Verified by `ctest --test-dir build/Release-tests -R '^(termin_inspect_c_test|termin_inspect_cpp_test)$' --output-on-failure`. |
| reviewed | c | `termin-inspect/tests/test_main.c` | C vtable dispatch and kind parser tests use guard C checks rather than smoke-only calls. Verified by `ctest --test-dir build/Release-tests -R '^(termin_inspect_c_test|termin_inspect_cpp_test)$' --output-on-failure`. |
| reviewed | cpp | `termin-inspect/tests/test_python_inspect.cpp` | Wired into the active CTest config as `termin_inspect_python_test` without enabling full Python extension builds; covers Python inspect bridge inheritance, get/set, serialization, deserialization, and callable refcount ownership. Verified by `ctest --test-dir build/Release-tests -R '^(termin_inspect_c_test|termin_inspect_cpp_test|termin_inspect_python_test)$' --output-on-failure`. |
| reviewed | python | `termin-mesh/tests/python/test_tmesh_api.py` | Mesh/layout and surface-edge query tests use concrete expected geometry; UUIDs isolate registry handles. |
| reviewed | cpp | `termin-modules/tests/test_module_runtime.cpp` | Runtime descriptor discovery/load-order/unload guard/cycle/missing dependency/dist-ignore coverage uses a fake backend and concrete state/error assertions. Verified by `ctest --test-dir build/Release-tests -R '^termin_modules_runtime_test$' --output-on-failure`. |
| reviewed | python | `termin-nodegraph/tests/test_controller.py` | Small controller contract checks for typed connections, mismatch rejection, and single-input edge replacement. |
| reviewed | python | `termin-nodegraph/tests/test_io.py` | JSON roundtrip covers nodes, edges, groups, and persisted params without redundant smoke checks. |
| needs-work | python | `termin-pga/tests/algeom_test.py` | Removed weak ellipsoid-equation string checks, legacy sys.path hack, and nondeterministic random input; broad generated-shape fixtures could still be helperized. |
| reviewed | python | `termin-pga/tests/baricenter_test.py` | Consolidated triangle reference-point cases; keeps barycentric edge cases, invalid simplex errors, and reconstruction checks. |
| reviewed | python | `termin-pga/tests/motor_test.py` | Removed unused helper; remaining motor factorization/inverse checks are compact and behavioral. |
| reviewed | python | `termin-pga/tests/project_test.py` | Consolidated simple point/plane/line projection cases; segment, AABB, and capsule checks keep concrete expected values. |
| reviewed | python | `termin-pga/tests/screw_test.py` | Removed unused helper, consolidated basic arithmetic/API checks, and pruned duplicate Screw3 twist case; transform/carry checks keep concrete expected vectors. |
| needs-work | python | `termin-qopt/tests/active_set_test.py` | Useful active-set regressions, but iteration-count and active-order assertions are white-box unless solver exposes them as stable API. |
| needs-work | python | `termin-qopt/tests/fem/doll2d_test.py` | Removed commented-out tests and silent exception swallowing; construction/API cases are still small and could be consolidated later. |
| reviewed | python | `termin-qopt/tests/fem/electric2_test.py` | Removed debug prints; resistor/capacitor/inductor/current-source checks have concrete assertions. |
| needs-work | python | `termin-qopt/tests/fem/fem_test.py` | Useful assembler/conditioning coverage, but matrix-conditioning and variable-solution blocks repeat helper setup. |
| pruned | python | `termin-qopt/tests/fem/lagrange_test.py` | Deleted: file was entirely commented out and collected no active tests. |
| needs-work | python | `termin-qopt/tests/fem/mbody2d_test.py` | Removed debug prints and a dormant false rotation-symmetry check; early rigid-body one-step cases could be parameterized. |
| needs-work | python | `termin-qopt/tests/fem/mbody3d_test.py` | Removed debug prints and added missing assertions for outcenter fixed-rotation case; large integration scenarios could be split/parameterized later. |
| needs-work | python | `termin-qopt/tests/fem/mechanic_test.py` | Useful analytical FEM coverage; triangle shear/body-force cases may be consolidated or strengthened. |
| reviewed | python | `termin-qopt/tests/fem/spatial_inertia2d_test.py` | Small, concrete expected-value checks. |
| reviewed | python | `termin-qopt/tests/fem/spatial_inertia3d_test.py` | Removed commented-out tests; remaining active test is a concrete expected-value check. |
| reviewed | python | `termin-qopt/tests/hqp_solver_test.py` | Removed unused import and clarified full-rank priority test; remaining HQP priority/nullspace/equality/inequality cases are concrete. |
| reviewed | python | `termin-qopt/tests/hqtasks_test.py` | Small adapter coverage for tracking, equality, bounds, damping, and soft-limit task construction. |
| reviewed | python | `termin-qopt/tests/qp_solve_test.py` | Consolidated random KKT coverage into deterministic stress test plus analytic equality-QP solution. |
| needs-work | python | `termin-qopt/tests/robot_test.py` | Removed debug print; robot Jacobian/branching/IK regressions are useful, but long iterative IK cases should be shortened or made more diagnostic. |
| needs-work | python | `termin-qopt/tests/subspaces_test.py` | Removed weak nearly-collinear smoke and pytest-unneeded main guard; file still has many repeated projector/basis contract checks that should be parameterized. |
| reviewed | cpp | `termin-render-passes/tests/test_builtin_shader_sources.cpp` | Built-in shader source/catalog tests protect resource-root loading, catalog uuid lookup, migrated engine shader table, Slang skybox material params, explicit entries, and vertex-only templates. Verified by `ctest --test-dir build/Release-tests -R '^termin_render_passes_builtin_shader_sources_test$' --output-on-failure`. |
| reviewed | c | `termin-render/tests/test_drawable_capability.c` | Drawable capability live reindex test checks scene capability count, phase queries, draw dispatch, foreach filtering, and detach behavior. Verified by `ctest --test-dir build/Release-tests -R '^(termin_render_drawable_test|termin_render_drawable_phase_ref_test)$' --output-on-failure`. |
| reviewed | cpp | `termin-render/tests/test_drawable_phase_ref.cpp` | Stable material phase reference regression grows the registry and resolves the original phase by stored identity rather than stale pointer. Verified by `ctest --test-dir build/Release-tests -R '^(termin_render_drawable_test|termin_render_drawable_phase_ref_test)$' --output-on-failure`. |
| reviewed | c | `termin-scene/tests/test_archetype.c` | Removed stale internal-query commentary; remaining SoA archetype/pool migration/query/destroy/swap-remove checks exercise concrete data preservation and counters. Verified by scene CTest batch. |
| reviewed | c | `termin-scene/tests/test_component_capability.c` | Capability registration, attach/detach, scene iteration, and live count behavior are tested through guard C checks. Verified by scene CTest batch. |
| reviewed | c | `termin-scene/tests/test_data_structures.c` | Legacy C harness covers pool generation/growth/iteration/clear, string/u32 maps, and dlist operations with explicit failure exits. Verified by scene CTest batch. |
| reviewed | cpp | `termin-scene/tests/test_unknown_component.cpp` | UnknownComponent degrade/upgrade/filtering, requirements, cycle detection, UnknownOnly deserialization, and custom upgrade strategies have concrete scene/component state assertions. Verified by scene CTest batch. |
