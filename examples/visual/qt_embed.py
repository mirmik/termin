"""Embed termin 3D view inside a PyQt6 application.

Uses Display + RenderEngine directly (no Visualization wrapper).
The QOpenGLWidget drives rendering via paintGL().
"""

from __future__ import annotations

import sys
import numpy as np
from PyQt6 import QtWidgets, QtCore

from termin.visualization.core.scene import Scene
from termin.visualization.core.entity import Entity
from termin.visualization.core.camera import PerspectiveCameraComponent, OrbitCameraController
from termin.visualization.core.display import Display
from termin.visualization.core.material import Material
from termin.visualization.render.components import MeshRenderer
from termin.mesh.mesh import UVSphereMesh
from termin.mesh import TcMesh
from termin.geombase import Pose3
from tgfx import TcShader
from termin._native.render import RenderEngine
from termin.graphics import OpenGLGraphicsBackend
from termin.visualization.platform.backends.qt import QtWindowBackend, QtGLWindowHandle


VERT = """
#version 330 core
layout(location = 0) in vec3 a_position;
layout(location = 1) in vec3 a_normal;

uniform mat4 u_model;
uniform mat4 u_view;
uniform mat4 u_projection;

out vec3 v_normal;

void main() {
    v_normal = mat3(transpose(inverse(u_model))) * a_normal;
    gl_Position = u_projection * u_view * u_model * vec4(a_position, 1.0);
}
"""


FRAG = """
#version 330 core
in vec3 v_normal;
uniform vec4 u_color;

out vec4 FragColor;

void main() {
    vec3 n = normalize(v_normal);
    float ndotl = max(dot(n, vec3(0.2, 0.6, 0.5)), 0.0);
    vec3 color = u_color.rgb * (0.25 + 0.75 * ndotl);
    FragColor = vec4(color, u_color.a);
}
"""


def make_preview_pipeline():
    """Create a simple render pipeline: Skybox -> Color -> Present."""
    from termin.visualization.render.framegraph import (
        ColorPass,
        PresentToScreenPass,
        RenderPipeline,
    )
    from termin.visualization.render.framegraph.passes.skybox import SkyBoxPass

    passes = [
        SkyBoxPass(input_res="empty", output_res="skybox", pass_name="Skybox"),
        ColorPass(
            input_res="skybox",
            output_res="color",
            shadow_res=None,
            pass_name="Color",
            phase_mark="opaque",
        ),
        PresentToScreenPass(
            input_res="color",
            pass_name="Present",
        ),
    ]
    return RenderPipeline(name="qt_embed", _init_passes=passes)


class QtEmbedRenderer:
    """Render callback installed as user_ptr on QtGLWindowHandle.

    paintGL() calls self.render(from_backend=True).
    """

    def __init__(
        self,
        handle: QtGLWindowHandle,
        display: Display,
        engine: RenderEngine,
        graphics: OpenGLGraphicsBackend,
        viewport,
        scene: Scene,
        camera: PerspectiveCameraComponent,
    ):
        self.handle = handle
        self.display = display
        self.engine = engine
        self.graphics = graphics
        self.viewport = viewport
        self.scene = scene
        self.camera = camera

    def render(self, from_backend: bool = False) -> None:
        self.display.make_current()
        self.graphics.ensure_ready()

        width, height = self.display.get_size()
        if width <= 0 or height <= 0:
            return

        surface = self.display.surface
        if surface is None:
            return
        display_fbo = surface.get_framebuffer()

        self.camera.set_aspect(width / float(max(1, height)))

        pipeline = self.viewport.pipeline
        if pipeline is None:
            return

        self.engine.render_view_to_fbo(
            pipeline,
            display_fbo,
            width,
            height,
            self.scene,
            self.camera,
            self.viewport,
            self.viewport.effective_layer_mask,
        )

        self.display.present()


def build_scene() -> tuple[Scene, PerspectiveCameraComponent]:
    """Create a simple scene with a sphere and orbit camera."""
    shader = TcShader.from_sources(VERT, FRAG, "", "QtEmbedShader")
    material = Material(
        name="QtEmbedMaterial",
        shader=shader,
        color=np.array([0.3, 0.7, 0.9, 1.0], dtype=np.float32),
    )

    mesh3 = UVSphereMesh(radius=1.0, n_meridians=32, n_parallels=16)
    tc_mesh = TcMesh.from_mesh3(mesh3, "QtEmbedSphere")

    sphere = Entity(pose=Pose3.identity(), name="sphere")
    sphere.add_component(MeshRenderer(tc_mesh, material))

    scene = Scene.create(name="qt_embed")
    scene.add(sphere)

    cam_entity = Entity(
        pose=Pose3.looking_at([0, -4, 0], [0, 0, 0]),
        name="camera",
    )
    camera = PerspectiveCameraComponent()
    cam_entity.add_component(camera)
    cam_entity.add_component(OrbitCameraController(radius=4.0))
    scene.add(cam_entity)

    # Start component lifecycle (on_added, first update)
    scene.update(0)

    return scene, camera


def main():
    graphics = OpenGLGraphicsBackend.get_instance()
    qt_backend = QtWindowBackend(graphics=graphics)

    scene, camera = build_scene()

    # Build Qt UI first — widget must be created with correct parent
    # to avoid reparenting (which destroys/recreates the GL context)
    main_window = QtWidgets.QMainWindow()
    central = QtWidgets.QWidget()
    layout = QtWidgets.QVBoxLayout(central)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    # Create QOpenGLWidget with parent so it's never reparented
    handle = qt_backend.create_window(
        width=800, height=600, title="termin Qt embed", parent=central
    )
    layout.addWidget(handle.widget)

    quit_btn = QtWidgets.QPushButton("Close")
    quit_btn.clicked.connect(main_window.close)
    layout.addWidget(quit_btn)

    main_window.setCentralWidget(central)
    main_window.resize(900, 700)
    main_window.setWindowTitle("Qt + termin visualization")

    # Create Display + RenderEngine after widget has its final parent
    display = Display(handle)
    viewport = display.create_viewport(scene=scene, camera=camera, name="main")
    viewport.pipeline = make_preview_pipeline()
    engine = RenderEngine(graphics)

    # Install render callback
    renderer = QtEmbedRenderer(handle, display, engine, graphics, viewport, scene, camera)
    handle.set_user_pointer(renderer)

    main_window.show()

    # Qt main loop
    sys.exit(qt_backend.app.exec())


if __name__ == "__main__":
    main()
