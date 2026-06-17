# Test Source Inventory

Generated for incremental test-suite pruning.

Scope:
- Includes test source and test-support files under repository test areas.
- Excludes `.venv`, `build`, `sdk`, `termin-thirdparty`, nested `build/`, and `__pycache__`.
- This is a working audit checklist, not a claim that listed tests are useful.

Current source counts:
- Total listed entries: 168
- Current existing listed files: 167
- Pruned entries: 1
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
| pending | c | `termin-app/core_c/tests/test_main.c` | |
| pending | cpp | `termin-app/cpp/tests/main.cpp` | |
| pending | cpp | `termin-app/cpp/tests/tests_binding.cpp` | |
| pending | cpp | `termin-app/cpp/tests/tests_general_pose3.cpp` | |
| pending | cpp | `termin-app/cpp/tests/tests_inspect_registry.cpp` | |
| pending | cpp | `termin-app/cpp/tests/tests_orbit_camera_controller.cpp` | |
| pending | cpp | `termin-app/cpp/tests/tests_rendering_manager.cpp` | |
| pending | cpp | `termin-app/cpp/tests/tests_shader_parser_std140.cpp` | |
| pending | python-support | `termin-app/termin/tests/__init__.py` | |
| pending | python | `termin-app/tests/aabb_test.py` | |
| pending | python-support | `termin-app/tests/api.py` | |
| pending | python | `termin-app/tests/asset_plugin_test.py` | |
| pending | python | `termin-app/tests/collider_test.py` | |
| pending | python-support | `termin-app/tests/conftest.py` | |
| pending | python | `termin-app/tests/editor_commands_test.py` | |
| pending | python | `termin-app/tests/framegraph_test.py` | |
| pending | python | `termin-app/tests/kinematics/kinematic_chain_test.py` | |
| pending | python | `termin-app/tests/kinematics/kinematic_test.py` | |
| pending | python | `termin-app/tests/kinematics/transform_test.py` | |
| pending | python | `termin-app/tests/pathfinding_test.py` | |
| pending | python | `termin-app/tests/physics/test_energy.py` | |
| pending | python | `termin-app/tests/physics/test_rigid_body.py` | |
| pending | python | `termin-app/tests/pose2_test.py` | |
| pending | python | `termin-app/tests/pose_test.py` | |
| pending | python | `termin-app/tests/shader_parser_test.py` | |
| pending | python | `termin-app/tests/test_asset_default_plugins.py` | |
| pending | python | `termin-app/tests/test_canonical_animation_imports.py` | |
| pending | python | `termin-app/tests/test_default_pipeline_specs.py` | |
| pending | python | `termin-app/tests/test_edge_flipping.py` | |
| pending | python | `termin-app/tests/test_editor_mcp_server.py` | |
| pending | python | `termin-app/tests/test_editor_python_executor.py` | |
| pending | python | `termin-app/tests/test_editor_shader_runtime.py` | |
| pending | python | `termin-app/tests/test_framegraph_debugger_model_disconnect.py` | |
| pending | python | `termin-app/tests/test_framegraph_internal_points.py` | |
| pending | python | `termin-app/tests/test_framegraph_presenter_bindings.py` | |
| pending | python | `termin-app/tests/test_funnel_algorithm.py` | |
| pending | python | `termin-app/tests/test_game_mode_model.py` | |
| pending | python | `termin-app/tests/test_game_mode_ui_controller.py` | |
| pending | python | `termin-app/tests/test_general_pose3.py` | |
| pending | python | `termin-app/tests/test_general_transform3.py` | |
| pending | python | `termin-app/tests/test_gltf_drag_drop.py` | |
| pending | python | `termin-app/tests/test_gltf_loader.py` | |
| pending | python | `termin-app/tests/test_inspect_singleton_topology.py` | |
| pending | python | `termin-app/tests/test_launcher_process_mode.py` | |
| pending | python | `termin-app/tests/test_material_asset_texture_persistence.py` | |
| pending | python | `termin-app/tests/test_material_inspector_texture.py` | |
| pending | python | `termin-app/tests/test_material_pass_serialization.py` | |
| pending | python | `termin-app/tests/test_material_registry_copy.py` | |
| pending | python | `termin-app/tests/test_mcp_base.py` | |
| pending | python | `termin-app/tests/test_mesh_spec_defaults.py` | |
| pending | python | `termin-app/tests/test_navmesh_package_facade.py` | |
| pending | python | `termin-app/tests/test_player_manifest_assets.py` | |
| pending | python | `termin-app/tests/test_procedural_mesh_component.py` | |
| pending | python | `termin-app/tests/test_procedural_mesh_editor_extension.py` | |
| pending | python | `termin-app/tests/test_project_builder.py` | |
| pending | python | `termin-app/tests/test_project_file_action_controller.py` | |
| pending | python | `termin-app/tests/test_project_file_watcher.py` | |
| pending | python | `termin-app/tests/test_project_operations.py` | |
| pending | python | `termin-app/tests/test_project_settings.py` | |
| pending | python | `termin-app/tests/test_rendering_model_render_target_restore.py` | |
| pending | python | `termin-app/tests/test_runtime_package_exporter.py` | |
| pending | python | `termin-app/tests/test_scene_file_model.py` | |
| pending | python | `termin-app/tests/test_scene_manager_viewer.py` | |
| pending | python | `termin-app/tests/test_screen_point_to_ray.py` | |
| pending | python | `termin-app/tests/test_shader_tool_resolution.py` | |
| pending | python | `termin-app/tests/test_tcgui_framegraph_debugger_handle.py` | |
| pending | python | `termin-app/tests/test_tcgui_pipeline_editor_window.py` | |
| pending | python | `termin-app/tests/test_tcgui_pipeline_inspector.py` | |
| pending | python | `termin-app/tests/test_tcgui_project_browser.py` | |
| pending | python | `termin-app/tests/test_tcgui_render_target_inspector.py` | |
| pending | python | `termin-app/tests/test_texture_inspector.py` | |
| pending | python | `termin-app/tests/test_texture_lazy_registration.py` | |
| pending | python | `termin-app/tests/test_vec3_list_field_widget.py` | |
| pending | python | `termin-app/tests/test_voxel_shader.py` | |
| pending | python | `termin-app/tests/undo_stack_test.py` | |
| pending | python | `termin-app/tests/util_test.py` | |
| pending | python | `termin-app/tests/voxels_test.py` | |
| pending | python | `termin-assets/tests/test_asset_contracts.py` | |
| pending | python | `termin-base/tests/python/test_python_package_install_order.py` | |
| pending | python | `termin-base/tests/python/test_tcbase_api.py` | |
| pending | cpp | `termin-base/tests/test_orbit_camera.cpp` | |
| pending | c | `termin-base/tests/test_tc_value.c` | |
| pending | python | `termin-build-tools/tests/test_sdk_orchestrator.py` | |
| pending | cpp | `termin-collision/tests/main.cpp` | |
| pending | cpp | `termin-collision/tests/tests_colliders.cpp` | |
| pending | cpp | `termin-collision/tests/tests_collision.cpp` | |
| pending | cpp | `termin-collision/tests/tests_convex_hull_collider.cpp` | |
| pending | cpp | `termin-collision/tests/tests_gjk.cpp` | |
| pending | cpp | `termin-collision/tests/tests_quickhull.cpp` | |
| pending | python | `termin-components/termin-components-foliage/tests/test_foliage_asset_plugin.py` | |
| pending | python | `termin-components/termin-components-render/tests/python/test_render_components_api.py` | |
| pending | cmake | `termin-csg/tests/CMakeLists.txt` | |
| pending | cpp | `termin-csg/tests/csg_basic_test.cpp` | |
| pending | python | `termin-csg/tests/test_csg_python.py` | |
| pending | cpp | `termin-display/tests/test_backend_window_triangle.cpp` | |
| pending | cpp | `termin-display/tests/test_display_input_router.cpp` | |
| pending | cpp | `termin-graphics/tests/main.cpp` | |
| pending | python | `termin-graphics/tests/python/test_termin_shaderc_cli.py` | |
| pending | python | `termin-graphics/tests/python/test_tgfx_api.py` | |
| pending | python | `termin-graphics/tests/python/test_tgfx_shader_runtime.py` | |
| pending | c | `termin-graphics/tests/test_mesh.c` | |
| pending | cpp | `termin-graphics/tests/test_per_pipeline_layout.cpp` | |
| pending | cpp | `termin-graphics/tests/test_render_context2.cpp` | |
| pending | cpp | `termin-graphics/tests/test_tgfx2_device_factory.cpp` | |
| pending | cpp | `termin-graphics/tests/test_tgfx2_line_mesh_builder.cpp` | |
| pending | cpp | `termin-graphics/tests/test_tgfx2_sdf.cpp` | |
| pending | cpp | `termin-graphics/tests/test_tgfx2_smoke.cpp` | |
| pending | cpp | `termin-graphics/tests/test_tgfx2_tc_mesh_bridge.cpp` | |
| pending | cpp | `termin-graphics/tests/test_tgfx2_vulkan_smoke.cpp` | |
| pending | cpp | `termin-graphics/tests/test_tgfx2_vulkan_window.cpp` | |
| pending | cpp | `termin-graphics/tests/tests_log.cpp` | |
| pending | cpp | `termin-graphics/tests/tests_shader_resource_layout.cpp` | |
| pending | cpp | `termin-graphics/tests/tests_vertex_layout.cpp` | |
| pending | python-support | `termin-gui/python/tests/__init__.py` | |
| pending | python-support | `termin-gui/python/tests/conftest.py` | |
| pending | python | `termin-gui/python/tests/test_clip_stack.py` | |
| pending | python | `termin-gui/python/tests/test_combined_layout.py` | |
| pending | python | `termin-gui/python/tests/test_editor_style_layout.py` | |
| pending | python | `termin-gui/python/tests/test_file_dialog.py` | |
| pending | python | `termin-gui/python/tests/test_file_grid_widget.py` | |
| pending | python | `termin-gui/python/tests/test_group_box.py` | |
| pending | python | `termin-gui/python/tests/test_hstack_layout.py` | |
| pending | python | `termin-gui/python/tests/test_label_metrics.py` | |
| pending | python | `termin-gui/python/tests/test_list_widget.py` | |
| pending | python | `termin-gui/python/tests/test_menu.py` | |
| pending | python | `termin-gui/python/tests/test_panel_layout.py` | |
| pending | python | `termin-gui/python/tests/test_rich_text_view.py` | |
| pending | python | `termin-gui/python/tests/test_scroll_area.py` | |
| pending | python | `termin-gui/python/tests/test_splitter.py` | |
| pending | python | `termin-gui/python/tests/test_tabs.py` | |
| pending | python | `termin-gui/python/tests/test_text_editing.py` | |
| pending | python | `termin-gui/python/tests/test_tree_widget.py` | |
| pending | python | `termin-gui/python/tests/test_ui_root_layout.py` | |
| pending | python | `termin-gui/python/tests/test_vstack_layout.py` | |
| pending | cpp | `termin-inspect/tests/test_cpp_inspect.cpp` | |
| pending | c | `termin-inspect/tests/test_main.c` | |
| pending | cpp | `termin-inspect/tests/test_python_inspect.cpp` | |
| pending | python | `termin-mesh/tests/python/test_tmesh_api.py` | |
| pending | cpp | `termin-modules/tests/test_module_runtime.cpp` | |
| pending | python | `termin-nodegraph/tests/test_controller.py` | |
| pending | python | `termin-nodegraph/tests/test_io.py` | |
| pending | python | `termin-pga/tests/algeom_test.py` | |
| pending | python | `termin-pga/tests/baricenter_test.py` | |
| pending | python | `termin-pga/tests/motor_test.py` | |
| pending | python | `termin-pga/tests/project_test.py` | |
| pending | python | `termin-pga/tests/screw_test.py` | |
| pending | python | `termin-qopt/tests/active_set_test.py` | |
| needs-work | python | `termin-qopt/tests/fem/doll2d_test.py` | Removed commented-out tests and silent exception swallowing; construction/API cases are still small and could be consolidated later. |
| reviewed | python | `termin-qopt/tests/fem/electric2_test.py` | Removed debug prints; resistor/capacitor/inductor/current-source checks have concrete assertions. |
| needs-work | python | `termin-qopt/tests/fem/fem_test.py` | Useful assembler/conditioning coverage, but matrix-conditioning and variable-solution blocks repeat helper setup. |
| pruned | python | `termin-qopt/tests/fem/lagrange_test.py` | Deleted: file was entirely commented out and collected no active tests. |
| needs-work | python | `termin-qopt/tests/fem/mbody2d_test.py` | Removed debug prints and a dormant false rotation-symmetry check; early rigid-body one-step cases could be parameterized. |
| needs-work | python | `termin-qopt/tests/fem/mbody3d_test.py` | Removed debug prints and added missing assertions for outcenter fixed-rotation case; large integration scenarios could be split/parameterized later. |
| needs-work | python | `termin-qopt/tests/fem/mechanic_test.py` | Useful analytical FEM coverage; triangle shear/body-force cases may be consolidated or strengthened. |
| reviewed | python | `termin-qopt/tests/fem/spatial_inertia2d_test.py` | Small, concrete expected-value checks. |
| reviewed | python | `termin-qopt/tests/fem/spatial_inertia3d_test.py` | Removed commented-out tests; remaining active test is a concrete expected-value check. |
| pending | python | `termin-qopt/tests/hqp_solver_test.py` | |
| pending | python | `termin-qopt/tests/hqtasks_test.py` | |
| pending | python | `termin-qopt/tests/qp_solve_test.py` | |
| pending | python | `termin-qopt/tests/robot_test.py` | |
| pending | python | `termin-qopt/tests/subspaces_test.py` | |
| pending | cpp | `termin-render-passes/tests/test_builtin_shader_sources.cpp` | |
| pending | c | `termin-render/tests/test_drawable_capability.c` | |
| pending | cpp | `termin-render/tests/test_drawable_phase_ref.cpp` | |
| pending | c | `termin-scene/tests/test_archetype.c` | |
| pending | c | `termin-scene/tests/test_component_capability.c` | |
| pending | c | `termin-scene/tests/test_data_structures.c` | |
| pending | cpp | `termin-scene/tests/test_unknown_component.cpp` | |
