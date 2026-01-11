"""
EditorSceneAttachment — manages editor connection to a scene.

Handles:
- Creating/destroying EditorEntities in the scene
- Creating/removing editor viewport
- Saving/restoring editor state (camera position, UI state)

Does NOT own EditorViewportFeatures — that's managed by EditorWindow
and updated via set_scene/set_camera when attachment changes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Optional

if TYPE_CHECKING:
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.camera import CameraComponent
    from termin.visualization.core.display import Display
    from termin.visualization.core.viewport import Viewport
    from termin.visualization.core.entity import Entity
    from termin.visualization.platform.backends.base import BackendWindow
    from termin.visualization.render.framegraph import RenderPipeline
    from termin.editor.rendering_controller import RenderingController
    from termin.editor.editor_camera import EditorCameraManager
    from termin.editor.editor_viewport_features import EditorViewportFeatures


class EditorSceneAttachment:
    """
    Manages editor attachment to a scene.

    One attachment = one scene being edited in one display.

    Lifecycle:
    - attach(scene): Create EditorEntities, viewport
    - detach(): Save state, remove EditorEntities, cleanup

    Properties:
    - scene: Currently attached scene (or None)
    - camera: Editor camera component (or None)
    - editor_entities: Root entity for editor objects (or None)
    - viewport: Editor viewport (or None)
    """

    def __init__(
        self,
        display: "Display",
        rendering_controller: "RenderingController",
        make_editor_pipeline: Callable[[], "RenderPipeline"],
    ):
        """
        Initialize EditorSceneAttachment.

        Args:
            display: Display to create viewport in.
            rendering_controller: Controller for viewport management.
            make_editor_pipeline: Factory for creating editor pipeline.
        """
        self._display = display
        self._rendering_controller = rendering_controller
        self._make_editor_pipeline = make_editor_pipeline

        # State (set when attached)
        self._attached_scene: "Scene | None" = None
        self._camera_manager: "EditorCameraManager | None" = None
        self._viewport: "Viewport | None" = None
        self._pipeline: "RenderPipeline | None" = None

    # --- Properties ---

    @property
    def scene(self) -> "Scene | None":
        """Currently attached scene."""
        return self._attached_scene

    @property
    def camera(self) -> "CameraComponent | None":
        """Editor camera component."""
        if self._camera_manager is None:
            return None
        return self._camera_manager.camera

    @property
    def editor_entities(self) -> "Entity | None":
        """Root entity for editor objects."""
        if self._camera_manager is None:
            return None
        return self._camera_manager.editor_entities

    @property
    def viewport(self) -> "Viewport | None":
        """Editor viewport."""
        return self._viewport

    @property
    def is_attached(self) -> bool:
        """True if currently attached to a scene."""
        return self._attached_scene is not None

    @property
    def camera_manager(self) -> "EditorCameraManager | None":
        """EditorCameraManager instance."""
        return self._camera_manager

    # --- Attach/Detach ---

    def attach(
        self,
        scene: "Scene",
        restore_state: bool = True,
        transfer_camera_state: bool = False,
    ) -> None:
        """
        Attach editor to a scene.

        Creates EditorEntities in the scene and creates viewport.

        Args:
            scene: Scene to attach to.
            restore_state: If True, restore editor state from scene.editor_entities_data.
            transfer_camera_state: If True, transfer camera state from previous scene
                                   (ignores restore_state).
        """
        # Save state from previous scene for potential transfer
        old_camera_data = None
        if transfer_camera_state and self._camera_manager is not None:
            old_camera_data = self._camera_manager.get_camera_data()

        if self._attached_scene is not None:
            self.detach(save_state=True)

        from termin.editor.editor_camera import EditorCameraManager

        # Create EditorEntities in scene
        self._camera_manager = EditorCameraManager()
        self._camera_manager.attach_to_scene(scene)

        # Restore state
        if transfer_camera_state and old_camera_data is not None:
            # Transfer from previous scene
            self._camera_manager.set_camera_data(old_camera_data)
        elif restore_state and scene.editor_entities_data is not None:
            # Restore from scene's stored data
            self._camera_manager.set_camera_data(scene.editor_entities_data)

        # Remove any existing viewports from this display
        self._remove_display_viewports()

        # Create editor viewport
        self._pipeline = self._make_editor_pipeline()
        self._viewport = self._display.create_viewport(
            scene=scene,
            camera=self._camera_manager.camera,
            rect=(0.0, 0.0, 1.0, 1.0),
        )
        self._viewport.name = "(Editor)"
        self._viewport.pipeline = self._pipeline
        self._camera_manager.camera.add_viewport(self._viewport)

        self._attached_scene = scene

        # Notify components that scene is active
        scene.notify_scene_active()

        # Refresh viewport list
        self._rendering_controller._viewport_list.refresh()

    def detach(self, save_state: bool = True) -> None:
        """
        Detach editor from current scene.

        Saves state to scene.editor_entities_data, removes EditorEntities,
        and cleans up viewport.

        Args:
            save_state: If True, save editor state to scene.editor_entities_data.
        """
        if self._attached_scene is None:
            return

        # Save state to scene
        if save_state and self._camera_manager is not None:
            self._attached_scene.editor_entities_data = self._camera_manager.get_camera_data()

        # Remove viewport
        if self._viewport is not None:
            # Remove from camera
            if self._camera_manager is not None and self._camera_manager.camera is not None:
                self._camera_manager.camera.remove_viewport(self._viewport)

            # Make GL context current before destroying GPU resources
            self._display.surface.make_current()

            # Destroy pipeline
            if self._pipeline is not None:
                self._pipeline.destroy()
                self._pipeline = None

            # Clear viewport state FBOs
            state = self._rendering_controller.get_viewport_state(self._viewport)
            if state is not None:
                state.clear_fbos()
                self._rendering_controller._manager.remove_viewport_state(self._viewport)

            self._display.remove_viewport(self._viewport)
            self._viewport = None

        # Remove EditorEntities from scene
        if self._camera_manager is not None:
            self._camera_manager.detach_from_scene()
            self._camera_manager = None

        self._attached_scene = None

        # Refresh viewport list
        self._rendering_controller._viewport_list.refresh()

    # --- State management ---

    def save_state(self) -> None:
        """Save current editor state to scene.editor_entities_data."""
        if self._attached_scene is None or self._camera_manager is None:
            return
        self._attached_scene.editor_entities_data = self._camera_manager.get_camera_data()

    def get_camera_data(self) -> dict | None:
        """Get current camera data for serialization."""
        if self._camera_manager is None:
            return None
        return self._camera_manager.get_camera_data()

    def set_camera_data(self, data: dict) -> None:
        """Apply camera data."""
        if self._camera_manager is None:
            return
        self._camera_manager.set_camera_data(data)

    # --- Internal helpers ---

    def _remove_display_viewports(self) -> None:
        """Remove all viewports from this display."""
        for vp in list(self._display.viewports):
            # Remove from camera
            if vp.camera is not None:
                vp.camera.remove_viewport(vp)
            # Destroy pipeline
            if vp.pipeline is not None:
                vp.pipeline.destroy()
            # Clear FBO state
            state = self._rendering_controller.get_viewport_state(vp)
            if state is not None:
                state.clear_fbos()
                self._rendering_controller._manager.remove_viewport_state(vp)
            self._display.remove_viewport(vp)
