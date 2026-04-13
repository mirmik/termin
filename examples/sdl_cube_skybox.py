#!/usr/bin/env python

"""SDL2 window with a rotating cube over a gradient skybox.

Pipeline:
    SkyBoxPass      → writes 'color' (inplace over 'empty', gradient sky)
    ColorPass       → writes 'color' (cube over sky)
    PresentToScreen → reads  'color'

Visual verification target for Stage 4 of the tgfx2 migration. SkyBoxPass
is the first production pass that draws through RenderContext2 end-to-end:
hand-written std140 UBO with view/projection matrices + skybox colors,
packed via std140_pack and bound via bind_material_ubo.

Imports only from subpackages — does NOT require termin-app.
"""

from __future__ import annotations

import sys
import numpy as np

from termin.entity import Entity, TcScene
from termin.entity._entity_native import OrbitCameraController, scene_render_state
from termin.render_components import PerspectiveCameraComponent, MeshRenderer
from termin.display.display import Display
from termin.display.sdl_backend import SDLWindowBackend
from termin.geombase import Pose3
from tgfx import TcShader
from termin._native.render import (
    RenderEngine,
    ColorPass,
    PresentToScreenPass,
    SkyBoxPass,
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


def make_skybox_pipeline():
    passes = [
        SkyBoxPass(input_res="empty", output_res="color", pass_name="Skybox"),
        ColorPass(
            input_res="color", output_res="color",
            shadow_res="", pass_name="Color", phase_mark="opaque",
        ),
        PresentToScreenPass(input_res="color", pass_name="Present"),
    ]
    return RenderPipeline(name="sdl_cube_skybox", _init_passes=passes)


def build_scene() -> tuple[TcScene, PerspectiveCameraComponent]:
    shader = TcShader.from_sources(VERT, FRAG, "", "SDLCubeSkyShader")
    material = TcMaterial(
        name="SDLCubeSkyMaterial",
        shader=shader,
        color=np.array([0.3, 0.6, 0.8, 1.0], dtype=np.float32),
    )

    mesh3 = CubeMesh()
    tc_mesh = TcMesh.from_mesh3(mesh3, "SDLCubeSky")

    cube = Entity(pose=Pose3.identity(), name="cube")
    cube.add_component(MeshRenderer(tc_mesh, material))

    scene = TcScene.create(name="sdl_cube_skybox")
    scene.add(cube)

    # Configure scene skybox — SkyBoxPass reads these fields.
    rs = scene_render_state(scene)
    rs.set_skybox_type(1)  # TC_SKYBOX_GRADIENT
    rs.set_skybox_top_color(0.4, 0.6, 0.9)     # sky blue
    rs.set_skybox_bottom_color(0.9, 0.6, 0.4)  # warm horizon

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
        width=800, height=600, title="termin SDL cube — skybox (tgfx2)",
    )
    display = Display(handle)
    viewport = display.create_viewport(scene=scene, camera=camera, name="main")

    from termin.render_framework import render_target_new
    rt = render_target_new("main")
    rt.scene = scene
    rt.camera = camera
    rt.pipeline = make_skybox_pipeline()
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
