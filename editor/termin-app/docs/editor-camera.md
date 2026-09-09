# Editor camera and navigation cube

The editor viewport owns an `EditorCameraComponent`, derived from the runtime
`CameraComponent`. It lives in the standalone editor-entity hierarchy, outside
the edited scene. Its owner supplies `request_render_callback`; the callback
requests the existing global engine render and host UI composition. Detaching
the camera clears the callback.

`NativeEditorEventLoop` advances the viewport camera after input processing,
before UI composition, using monotonic elapsed time. This update is independent
of pending render requests and honors the component's enabled/editor-update
flags. The standalone `internal_entities` hierarchy does not have a general
scene update traversal; this is an explicit update of the viewport-owned camera.

## Navigation

- Clicking a cube face aligns the camera with that axis and starts a temporary
  orthographic projection transition (0.2 seconds by default).
- The next change of camera orientation returns to the preceding free-view
  projection. Mouse orbit, touch rotation and SpaceMouse rotation therefore use
  the same behavior. Pan and zoom keep the axis view.
- Clicking an edge or corner selects that direction and returns to free-view
  projection. Repeated face clicks retain the original free-view settings.
- A camera explicitly configured as orthographic remains orthographic when
  rotated. Explicit projection selection cancels a temporary transition.
- A reverse transition can start before the forward transition finishes.
  Every changing update requests a frame, including the final update; an idle
  camera stops requesting frames.

Zoom in a settled axis view transfers to orbit distance when perspective
resumes, preserving the target and camera rotation. If zoom is applied during
the entry animation and that animation is immediately reversed, its scale
instead eases back to perspective at the existing distance.

## Projection contract

Let `P` be the perspective matrix and `d` the distance to the orbit target.
Construct an orthographic matrix `O` with the same horizontal and vertical
scale as `P` on the camera-facing plane at distance `d`. Blend the homogeneous
matrices as `(1-t) P/d + t O`, using a smoothstep time weight. On that plane both
matrices have homogeneous `w = 1`, so screen X/Y remain fixed throughout the
transition. Near and far clipping retain the engine's zero-to-one depth
convention. Both FOV axes are matched, including independent-axis FOV mode.

The camera capability, rendering and screen-ray/picking helpers all obtain the
matrix through virtual `compute_projection_matrix`. No separate picking
projection is maintained. The ground grid uses view-space depth for fading,
which also works with intermediate projections.

The editor's saved camera state retains the free-view projection parameters
and the temporary axis view separately. Restoring an axis view settles at its
orthographic endpoint. Old editor metadata containing a `CameraComponent`
envelope is applied to the new `EditorCameraComponent` without discarding its
camera fields.
