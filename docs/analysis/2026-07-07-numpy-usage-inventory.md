# NumPy Usage Inventory

Date: 2026-07-07

This inventory lists project Python files that import NumPy directly. It excludes
virtual environments, build outputs, the SDK bundle, and third-party sources.

Reproduce:

```bash
rg -l "^\s*(import numpy\b|from numpy\b)" \
  --glob '*.py' \
  --glob '!**/.venv/**' \
  --glob '!**/build/**' \
  --glob '!sdk/**' \
  --glob '!termin-thirdparty/**' | sort
```

Total files: 159

## Reading Notes

- `keep ndarray`: NumPy is part of a dense buffer, parser, image, mesh, or solver boundary.
- `heavy linalg`: NumPy is doing linear algebra where replacement needs a real math backend decision.
- `Vec3/Quat/Mat44 candidate`: mostly small 2D/3D geometry that can likely move to native geometry types.
- `tests only` and `examples only`: lower priority for runtime dependency reduction.

## Resolved Quick Wins

- `termin-components/termin-components-physics/python/termin/physics_components/rigid_body_component.py`: collider extents moved to `Vec3`.
- `termin-components/termin-components-tween/python/termin/tween/component.py`: annotation-only NumPy import removed.
- `termin-pga/python/termin/ga201/convex_body.py`: `np.argmin` replaced by list/min selection.
- `termin-tween/python/termin/tween/manager.py`: annotation-only NumPy import removed.

## Annotated Files

| File | NumPy use | Reduction note |
|---|---|---|
| `examples/sdl_cube.py` | material camera vectors | Vec3/Color candidate |
| `tcplot/examples/demo_3d_helix.py` | generated plot arrays | examples only |
| `tcplot/examples/demo_3d_surface.py` | surface meshgrid arrays | examples keep ndarray |
| `tcplot/examples/demo_multi.py` | plot curve arrays | examples only |
| `tcplot/examples/demo_scatter.py` | random plot arrays | examples only |
| `tcplot/examples/demo_sin.py` | trigonometric plot arrays | examples only |
| `tcplot/python/tcplot/plot3d.py` | surface buffer flattening | keep ndarray boundary |
| `termin-animation/python/termin/animation/channel.py` | animation key arrays | Vec3/Quat candidate |
| `termin-app/termin/editor_core/editor_commands.py` | undo snapshot arrays | keep copy boundary |
| `termin-app/termin/editor_core/gizmo/base.py` | ray collider math | Vec3 candidate |
| `termin-app/termin/editor_core/prefab_persistence.py` | JSON numpy encoding | serialization boundary |
| `termin-app/termin/editor_tcgui/dialogs/scene_inspector.py` | color value arrays | Color/Vec3 candidate |
| `termin-app/termin/editor_tcgui/framegraph_debugger_service.py` | frame image buffers | keep ndarray |
| `termin-app/termin/editor_tcgui/surface_edge_debug_tool.py` | mesh vertex conversion | Vec3 candidate |
| `termin-app/termin/editor_tcgui/texture_inspector.py` | texture preview buffers | keep ndarray |
| `termin-app/termin/editor_tcgui/viewport_geometry_controller.py` | projection matrix multiply | Mat44 candidate |
| `termin-app/termin/editor_tcgui/widgets/texture_picker.py` | texture preview buffers | keep ndarray |
| `termin-app/tests/editor_commands_test.py` | undo expected arrays | tests only |
| `termin-audio/python/termin/audio/components/audio_source.py` | spatial audio vector math | Vec3 candidate |
| `termin-base/python/termin/geombase/pose2.py` | Pose2 vector matrices | Vec2/Mat33 candidate |
| `termin-base/python/termin/geombase/quaternion.py` | quaternion array math | Quat candidate |
| `termin-base/python/termin/geombase/screw.py` | screw vector algebra | Vec3/Screw native candidate |
| `termin-base/python/termin/geombase/transform_aabb.py` | AABB corner transform | Mat34 candidate |
| `termin-base/tests/python/pose2_test.py` | Pose2 expected arrays | tests only |
| `termin-base/tests/python/pose_test.py` | Pose3 matrix assertions | tests only |
| `termin-base/tests/python/test_general_pose3.py` | GeneralPose3 matrix tests | tests only |
| `termin-base/tests/python/util_test.py` | quaternion slerp assertions | tests only |
| `termin-collision/tests/collider_test.py` | collider point assertions | tests only |
| `termin-components/termin-components-kinematic/python/termin/kinematic/conditions.py` | normal equation matrices | heavy linalg |
| `termin-components/termin-components-kinematic/python/termin/kinematic/from_trent.py` | Trent pose arrays | Vec3/Quat candidate |
| `termin-components/termin-components-kinematic/python/termin/kinematic/kinchain.py` | Jacobian matrix assembly | keep ndarray |
| `termin-components/termin-components-kinematic/python/termin/kinematic/kinematic.py` | kinematic axis arrays | Vec3 candidate |
| `termin-components/termin-components-kinematic/python/termin/kinematic/transform.py` | transform direction arrays | Vec3 candidate |
| `termin-components/termin-components-kinematic/tests/aabb_test.py` | AABB expected arrays | tests only |
| `termin-components/termin-components-kinematic/tests/kinematic_chain_test.py` | kinematic test vectors | tests only |
| `termin-components/termin-components-kinematic/tests/kinematic_test.py` | transform test vectors | tests only |
| `termin-components/termin-components-kinematic/tests/test_general_transform3.py` | transform assertion arrays | tests only |
| `termin-components/termin-components-kinematic/tests/transform_test.py` | pose test vectors | tests only |
| `termin-components/termin-components-mesh/python/termin/mesh/mesh.py` | mesh arrays | keep ndarray mesh buffers |
| `termin-components/termin-components-render/python/termin/render_components/camera.py` | camera target annotation | Vec3 candidate |
| `termin-components/termin-components-render/python/termin/render_components/skybox_renderer.py` | view matrix copy | Mat44 candidate |
| `termin-components/termin-components-render/tests/python/test_screen_point_to_ray.py` | ray assertion arrays | tests only |
| `termin-components/termin-components-voxels/python/termin_voxel_components/display_component.py` | voxel display buffers | keep ndarray mesh buffers |
| `termin-components/termin-components-voxels/python/termin_voxel_components/visualization.py` | voxel visualizer buffers | keep ndarray mesh buffers |
| `termin-components/termin-components-voxels/python/termin_voxel_components/voxelizer_actions.py` | root matrix inverse | Mat44 candidate |
| `termin-components/termin-components-voxels/python/termin_voxel_components/voxelizer_component.py` | voxel mesh generation | keep ndarray mesh buffers |
| `termin-components/termin-components-voxels/python/termin_voxel_components/voxelizer_debug_draw.py` | shader uniform vectors | keep ndarray uniforms |
| `termin-csg/examples/demo_csg_wireframe.py` | wireframe plot arrays | examples only |
| `termin-csg/python/termin/csg/cad_app.py` | screen projection vector | Mat44 candidate |
| `termin-csg/python/termin/csg/cad_viewer.py` | preview mesh buffers | keep ndarray GPU buffers |
| `termin-csg/python/termin/csg/document_eval.py` | CSG mesh evaluation | keep ndarray geometry core |
| `termin-csg/python/termin/csg/document_mesh.py` | document mesh assembly | keep ndarray geometry core |
| `termin-csg/python/termin/csg/document_raycast.py` | raycast mesh arrays | keep ndarray geometry core |
| `termin-csg/python/termin/csg/preview.py` | preview GPU buffers | keep ndarray GPU buffers |
| `termin-csg/python/termin/csg/solid_render.py` | immediate solid triangles | keep ndarray mesh buffers |
| `termin-csg/python/termin/csg/viewer_camera.py` | orbit camera matrices | Mat44/Vec3 candidate |
| `termin-default-assets/python/termin/default_assets/mesh/mesh_spec.py` | axis remap arrays | Vec3 batch candidate |
| `termin-default-assets/python/termin/default_assets/mesh/obj_loader.py` | OBJ mesh arrays | keep ndarray contract |
| `termin-default-assets/python/termin/default_assets/mesh/stl_loader.py` | STL mesh arrays | keep ndarray contract |
| `termin-default-assets/python/termin/default_assets/render/texture_asset.py` | image pixel buffers | keep ndarray |
| `termin-default-assets/tests/asset_plugin_test.py` | mesh reload assertions | tests only |
| `termin-default-assets/tests/test_default_mesh_asset_plugin.py` | Mesh3 test fixtures | tests only |
| `termin-default-assets/tests/test_material_asset_texture_persistence.py` | texture test pixels | tests only |
| `termin-default-assets/tests/test_mesh_spec_defaults.py` | mesh spec fixtures | tests only |
| `termin-default-assets/tests/test_texture_lazy_registration.py` | texture test pixels | tests only |
| `termin-glb/python/termin/glb/instantiator.py` | GLB vertex buffers | keep ndarray geometry |
| `termin-glb/python/termin/glb/loader.py` | GLB accessor arrays | keep ndarray parser |
| `termin-glb/tests/test_glb_instantiator_hierarchy.py` | transform test vectors | tests only |
| `termin-glb/tests/test_glb_loader.py` | GLB transform assertions | tests only |
| `termin-graphics/examples/demo_lines.py` | line mesh buffers | example only |
| `termin-graphics/python/tgfx/text3d.py` | camera basis arrays | Mat44 Vec3 candidate |
| `termin-gui/examples/sdl_canvas_demo.py` | demo image generation | example only |
| `termin-gui/python/tcgui/widgets/canvas.py` | canvas image buffers | keep ndarray |
| `termin-gui/python/tcgui/widgets/color_dialog.py` | color picker textures | keep ndarray |
| `termin-gui/python/tcgui/widgets/icon_theme.py` | icon pixel buffers | keep ndarray |
| `termin-gui/python/tcgui/widgets/renderer.py` | UI render buffers | keep ndarray plus Mat44 |
| `termin-mcp/termin/mcp/screenshot.py` | framebuffer readback buffer | keep ndarray |
| `termin-mesh/python/tmesh/primitives.py` | primitive mesh generation | keep mesh arrays |
| `termin-mesh/tests/python/test_tmesh_api.py` | mesh API fixtures | tests only |
| `termin-navmesh/python/termin/navmesh/agent_component.py` | path waypoint vectors | Vec3 candidate |
| `termin-navmesh/python/termin/navmesh/builder_component.py` | navmesh mesh assembly | heavy ndarray geometry |
| `termin-navmesh/python/termin/navmesh/contour_extraction.py` | distance fields contours | keep ndarray masks |
| `termin-navmesh/python/termin/navmesh/display_component.py` | debug mesh ribbons | keep mesh arrays |
| `termin-navmesh/python/termin/navmesh/material_component.py` | navmesh display meshes | keep mesh arrays |
| `termin-navmesh/python/termin/navmesh/pathfinding.py` | A* geometry math | Vec3 ndarray hybrid |
| `termin-navmesh/python/termin/navmesh/pathfinding_world_component.py` | world path transforms | Mat44 Vec3 candidate |
| `termin-navmesh/python/termin/navmesh/persistence.py` | navmesh binary serialization | keep ndarray IO |
| `termin-navmesh/python/termin/navmesh/polygon_builder.py` | polygon linalg geometry | heavy linalg |
| `termin-navmesh/python/termin/navmesh/region_growing.py` | surface normal clustering | Vec3 candidate |
| `termin-navmesh/python/termin/navmesh/registry.py` | navmesh merge defaults | keep ndarray |
| `termin-navmesh/python/termin/navmesh/triangulation.py` | polygon geometry arrays | keep ndarray |
| `termin-navmesh/python/termin/navmesh/types.py` | navmesh data buffers | keep ndarray |
| `termin-navmesh/tests/pathfinding_test.py` | navmesh fixture arrays | tests only |
| `termin-navmesh/tests/test_edge_flipping.py` | triangle quality math | tests only |
| `termin-navmesh/tests/test_funnel_algorithm.py` | funnel fixture arrays | tests only |
| `termin-navmesh/tests/test_recast_builder_component.py` | mesh fixture buffers | tests only |
| `termin-navmesh/tests/test_voxelizer_debug_draw.py` | debug bounds arrays | tests only |
| `termin-pga/python/termin/algeom.py` | quadric fitting linalg | heavy linalg |
| `termin-pga/python/termin/closest.py` | segment distance math | Vec3 candidate |
| `termin-pga/python/termin/ga201/motor.py` | motor vector arrays | Vec2 candidate |
| `termin-pga/python/termin/ga201/screw.py` | screw vector arrays | Vec2 candidate |
| `termin-pga/python/termin/geomalgo/baricenter.py` | barycentric linear solve | heavy linalg |
| `termin-pga/python/termin/geomalgo/project.py` | geometric projection math | Vec3 candidate |
| `termin-pga/python/termin/solve.py` | least squares solve | heavy linalg |
| `termin-pga/tests/algeom_test.py` | quadric fitting fixtures | tests only |
| `termin-pga/tests/baricenter_test.py` | barycentric test arrays | tests only |
| `termin-pga/tests/project_test.py` | projection test arrays | tests only |
| `termin-pga/tests/screw_test.py` | screw array assertions | tests only |
| `termin-physics-fem/python/termin/physics_fem/fem_fixed_joint_component.py` | anchor vector math | Vec3 candidate |
| `termin-physics-fem/python/termin/physics_fem/fem_physics_world_component.py` | FEM solve energy | heavy linalg |
| `termin-physics-fem/python/termin/physics_fem/fem_revolute_joint_component.py` | joint vector math | Vec3 candidate |
| `termin-physics-fem/python/termin/physics_fem/fem_rigid_body_component.py` | inertia vector math | Vec3 candidate |
| `termin-physics/tests/test_energy.py` | energy vector fixture | tests only |
| `termin-player/termin/player/runtime_package_loader.py` | mesh buffer loading | keep ndarray |
| `termin-prefab/python/termin/prefab/asset.py` | prefab JSON arrays | serialization boundary |
| `termin-prefab/python/termin/prefab/instance_marker.py` | override array serialization | serialization boundary |
| `termin-prefab/python/termin/prefab/property_path.py` | transform array comparison | Vec3/Quat candidate |
| `termin-project-build/python/termin/project_build/runtime_package/meshes.py` | mesh buffer flattening | keep ndarray |
| `termin-project-build/tests/test_runtime_package_exporter.py` | runtime mesh fixtures | tests only |
| `termin-qopt/python/termin/fem/assembler.py` | FEM matrix assembly | heavy linalg |
| `termin-qopt/python/termin/fem/doll2d.py` | 2D multibody dynamics | keep ndarray |
| `termin-qopt/python/termin/fem/dynamic_assembler.py` | dynamic system matrices | heavy linalg |
| `termin-qopt/python/termin/fem/electrical_2.py` | circuit element matrices | keep solver ndarray |
| `termin-qopt/python/termin/fem/inertia2d.py` | 2D spatial inertia math | Vec2 plus small matrices |
| `termin-qopt/python/termin/fem/inertia3d.py` | 3D inertia eigensystem math | Vec3/Quat plus linalg |
| `termin-qopt/python/termin/fem/mechanic.py` | FEM stiffness assembly | keep ndarray FEM core |
| `termin-qopt/python/termin/fem/multibody2d_3.py` | 2D rigid constraint matrices | keep ndarray, Vec2 candidate |
| `termin-qopt/python/termin/fem/multibody3d_3.py` | 3D rigid quaternion dynamics | Vec3/Quat, keep matrices |
| `termin-qopt/python/termin/linalg/solve.py` | QP KKT active-set solve | heavy linalg keep ndarray |
| `termin-qopt/python/termin/linalg/subspaces.py` | subspace projector linalg | heavy SVD/QR keep ndarray |
| `termin-qopt/python/termin/robot/hqsolver.py` | hierarchical QP matrices | heavy linalg keep ndarray |
| `termin-qopt/python/termin/robot/hqtasks.py` | HQT task matrix builders | keep ndarray task API |
| `termin-qopt/python/termin/robot/robot.py` | robot Jacobian assembly | Jacobian ndarray, Vec3 candidate |
| `termin-qopt/tests/active_set_test.py` | active-set QP fixtures | tests only |
| `termin-qopt/tests/fem/doll2d_test.py` | 2D multibody fixtures | tests only |
| `termin-qopt/tests/fem/electric2_test.py` | circuit solve fixtures | tests only |
| `termin-qopt/tests/fem/fem_test.py` | FEM assembler fixtures | tests only |
| `termin-qopt/tests/fem/mbody2d_test.py` | 2D dynamics simulations | tests only |
| `termin-qopt/tests/fem/mbody3d_test.py` | 3D dynamics simulations | tests only |
| `termin-qopt/tests/fem/mechanic_test.py` | mechanics FEM fixtures | tests only |
| `termin-qopt/tests/fem/spatial_inertia2d_test.py` | 2D inertia assertions | tests only |
| `termin-qopt/tests/fem/spatial_inertia3d_test.py` | 3D inertia assertions | tests only |
| `termin-qopt/tests/hqp_solver_test.py` | HQP solver fixtures | tests only |
| `termin-qopt/tests/hqtasks_test.py` | HQT matrix fixtures | tests only |
| `termin-qopt/tests/qp_solve_test.py` | QP solve fixtures | tests only |
| `termin-qopt/tests/robot_test.py` | robot Jacobian fixtures | tests only |
| `termin-qopt/tests/subspaces_test.py` | subspace linalg fixtures | tests only |
| `termin-render-passes/python/termin/render_passes/highlight.py` | uniform byte buffer | replaceable bytearray view |
| `termin-render-passes/tests/test_shadow_camera_api.py` | shadow vector fixture | tests only |
| `termin-render/python/termin/render/texture.py` | texture image buffers | keep ndarray boundary |
| `termin-render/python/termin/render/texture_handle.py` | 1x1 texture pixels | tiny ndarray boundary |
| `termin-tween/python/termin/tween/tween.py` | Vec3/quaternion interpolation | Vec3/Quat candidate |
| `termin-tween/tests/test_tween_core.py` | tween vector fixtures | tests only |
| `termin-voxels/python/termin/voxels/chunk.py` | voxel chunk storage | keep ndarray dense grid |
| `termin-voxels/python/termin/voxels/intersection.py` | triangle AABB math | Vec3 candidate |
| `termin-voxels/python/termin/voxels/native_voxelizer.py` | native mesh array conversion | keep ndarray ABI boundary |
| `termin-voxels/python/termin/voxels/voxel_mesh.py` | mesh vertex buffers | keep ndarray render boundary |
| `termin-voxels/python/termin/voxels/voxelizer.py` | mesh voxelization geometry | keep ndarray, Vec3 candidate |
| `termin-voxels/tests/voxels_test.py` | voxel geometry fixtures | tests only |
