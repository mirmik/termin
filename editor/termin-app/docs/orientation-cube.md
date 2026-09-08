# Viewport orientation cube

The native editor shows an orientation cube below the camera mode buttons in
the top-right corner of the scene viewport. Left-click a face for an axial
view, a beveled edge for a two-axis diagonal, or a corner for an isometric view.
Hover highlights the target and shows the camera side below the cube; pressing
highlights it in amber. Releasing outside the pressed region cancels the click.

Labels describe the **camera's side**, rather than its viewing direction:

| Face | Camera side | Looks toward |
| --- | --- | --- |
| N | North, +Y | −Y |
| S | South, −Y | +Y |
| E | East, +X | −X |
| W | West, −X | +X |
| TOP | Up, +Z | −Z |
| BOTTOM | Down, −Z | +Z |

Edges combine two signed axes with equal weight; corners combine three.
For example, `TOP_NORTH_EAST` puts the camera along normalized `(1, 1, 1)`
relative to its orbit target. World directions remain fixed as the camera
rotates. Top view has north at the top of the screen; bottom view has south
at the top.

Snapping preserves the orbit target, radius, projection mode and orthographic
size, and resets camera roll deterministically. Normal orbit, pan and zoom
continue from the snapped state. The cube follows the active camera, including
fly-mode roll, and rebinds when the editor switches scenes.

Implementation uses `NativeOrientationCube`, an ordinary GUI overlay containing
a `SceneView3D`. Its private `TcVisualScene3D` owns 26 `PrimitiveItem3D` regions
with embedded label triangles. Native item ray tests and generic scene pointer
capture handle interaction. The cube camera samples only the editor camera's
rotation; only an activation calls `OrbitCameraController.snap_view(ViewDirection)`.
No cube geometry enters the edited scene or its picking passes.

Verification: `task build`, `task test`. Focused Python checks live in
`test_orientation_cube_geometry.py`, `test_native_orientation_cube.py`, and
`test_native_editor_viewport.py`; C++ controller tests cover all 26 directions
in perspective and orthographic modes. For a visual check, open a project with
`sdk/bin/termin_editor`, click faces, edges and corners, orbit the camera,
resize the viewport, and switch scenes.
