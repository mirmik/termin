"""SDL2 window with a rotating cube rendered through a grayscale post-process.

Pipeline:
    ColorPass       → writes 'color'
    GrayscalePass   → reads  'color', writes 'gray'
    PresentToScreen → reads  'gray'

Intended as the visual baseline for the legacy tgfx path of GrayscalePass,
against which the upcoming tgfx2 rewrite will be compared. Should display a
cube drawn in grayscale (luminance = dot(rgb, (0.2126, 0.7152, 0.0722))).

Imports only from subpackages — does NOT require termin-app.
"""

from __future__ import annotations

import sys
import numpy as np

from termin.entity import Entity, TcScene
from termin.entity._entity_native import OrbitCameraController
from termin.render_components import PerspectiveCameraComponent, MeshRenderer
from termin.display.display import Display
from termin.display.sdl_backend import SDLWindowBackend
from termin.geombase import Pose3
from tgfx import TcShader
from termin._native.render import (
    RenderEngine,
    ColorPass,
    PresentToScreenPass,
    GrayscalePass,
    TcMaterial,
)
from tgfx import OpenGLGraphicsBackend
from termin.render_framework import RenderPipeline
from tmesh import TcMesh, CubeMesh


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


def make_grayscale_pipeline():
    """Color → Grayscale → Present.

    Framegraph forbids two passes writing the same resource, so GrayscalePass
    reads 'color' and writes 'gray', and Present reads 'gray'.
    """
    passes = [
        ColorPass(
            input_res="empty", output_res="color",
            shadow_res="", pass_name="Color", phase_mark="opaque",
        ),
        GrayscalePass(
            input_res="color", output_res="gray",
            strength=1.0,
        ),
        PresentToScreenPass(input_res="gray", pass_name="Present"),
    ]
    return RenderPipeline(name="sdl_cube_grayscale", _init_passes=passes)


def build_scene() -> tuple[TcScene, PerspectiveCameraComponent]:
    shader = TcShader.from_sources(VERT, FRAG, "", "SDLCubeGrayShader")
    material = TcMaterial(
        name="SDLCubeGrayMaterial",
        shader=shader,
        color=np.array([0.3, 0.6, 0.8, 1.0], dtype=np.float32),
    )

    mesh3 = CubeMesh()
    tc_mesh = TcMesh.from_mesh3(mesh3, "SDLCubeGray")

    cube = Entity(pose=Pose3.identity(), name="cube")
    cube.add_component(MeshRenderer(tc_mesh, material))

    scene = TcScene.create(name="sdl_cube_grayscale")
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

    handle = sdl_backend.create_window(
        width=800, height=600, title="termin SDL cube — grayscale post-process",
    )
    display = Display(handle)
    viewport = display.create_viewport(scene=scene, camera=camera, name="main")

    from termin.render_framework import render_target_new
    rt = render_target_new("main")
    rt.scene = scene
    rt.camera = camera
    rt.pipeline = make_grayscale_pipeline()
    viewport.render_target = rt

    engine = RenderEngine(graphics)

    display.connect_input()

    pipeline = rt.pipeline

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

        if pipeline is None:
            continue

        engine.render_view_to_fbo(
            pipeline, display_fbo, width, height,
            scene, camera, viewport,
            viewport.layer_mask,
        )

        display.present()

    sdl_backend.terminate()


if __name__ == "__main__":
    main()
