"""SDL2 window with a rotating cube.

Uses Display + RenderEngine directly with SDL backend.
"""

from __future__ import annotations

import sys
import numpy as np

from termin.visualization.core.scene import Scene
from termin.visualization.core.entity import Entity
from termin.visualization.core.camera import PerspectiveCameraComponent, OrbitCameraController
from termin.visualization.core.display import Display
from termin.visualization.core.material import Material
from termin.visualization.render.components import MeshRenderer
from termin.mesh.mesh import CubeMesh
from termin.mesh import TcMesh
from termin.geombase import Pose3
from termin._native.render import TcShader, RenderEngine
from termin.graphics import OpenGLGraphicsBackend
from termin.visualization.platform.backends.sdl import SDLWindowBackend


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
    from termin.visualization.render.framegraph import (
        ColorPass, PresentToScreenPass, RenderPipeline,
    )
    from termin.visualization.render.framegraph.passes.skybox import SkyBoxPass

    passes = [
        SkyBoxPass(input_res="empty", output_res="skybox", pass_name="Skybox"),
        ColorPass(
            input_res="skybox", output_res="color",
            shadow_res=None, pass_name="Color", phase_mark="opaque",
        ),
        PresentToScreenPass(input_res="color", pass_name="Present"),
    ]
    return RenderPipeline(name="sdl_cube", _init_passes=passes)


def build_scene() -> tuple[Scene, PerspectiveCameraComponent]:
    shader = TcShader.from_sources(VERT, FRAG, "", "SDLCubeShader")
    material = Material(
        name="SDLCubeMaterial",
        shader=shader,
        color=np.array([0.3, 0.6, 0.8, 1.0], dtype=np.float32),
    )

    mesh3 = CubeMesh()
    tc_mesh = TcMesh.from_mesh3(mesh3, "SDLCube")

    cube = Entity(pose=Pose3.identity(), name="cube")
    cube.add_component(MeshRenderer(tc_mesh, material))

    scene = Scene.create(name="sdl_cube")
    scene.add(cube)

    cam_entity = Entity(
        pose=Pose3.looking_at([0, -4, 0], [0, 0, 0]),
        name="camera",
    )
    camera = PerspectiveCameraComponent()
    cam_entity.add_component(camera)
    cam_entity.add_component(OrbitCameraController(radius=4.0))
    scene.add(cam_entity)

    scene.update(0)
    return scene, camera


def main():
    graphics = OpenGLGraphicsBackend.get_instance()
    sdl_backend = SDLWindowBackend(graphics=graphics)

    scene, camera = build_scene()

    handle = sdl_backend.create_window(width=800, height=600, title="termin SDL cube")
    display = Display(handle)
    viewport = display.create_viewport(scene=scene, camera=camera, name="main")
    viewport.pipeline = make_preview_pipeline()
    engine = RenderEngine(graphics)

    while not handle.should_close():
        sdl_backend.poll_events()

        display.make_current()
        graphics.ensure_ready()

        width, height = display.get_size()
        if width <= 0 or height <= 0:
            continue

        surface = display.surface
        if surface is None:
            continue
        display_fbo = surface.get_framebuffer()

        camera.set_aspect(width / float(max(1, height)))

        pipeline = viewport.pipeline
        if pipeline is None:
            continue

        engine.render_view_to_fbo(
            pipeline, display_fbo, width, height,
            scene, camera, viewport,
            viewport.effective_layer_mask,
        )

        display.present()

    sdl_backend.terminate()


if __name__ == "__main__":
    main()
