#!/usr/bin/env python

"""Reproduce the "tonemap blacks out" regression from editor default pipeline.

Mirrors the editor pipeline config for HDR + bloom + tonemap chain:
    SkyBox → Color → Resolve → PostFX → Bloom → Tonemap(NONE) → Present

TonemapPass is configured with method=2 (NONE) — same as editor pipeline.
If this shows the cube, the editor bug is elsewhere. If it shows black,
we have a local repro for tonemap-specific failure.
"""

from __future__ import annotations

import numpy as np

from termin.entity import Entity, TcScene
from termin.entity._entity_native import OrbitCameraController, scene_render_state
from termin.render_components import PerspectiveCameraComponent, MeshRenderer
from termin.display.display import Display
from termin.display.sdl_backend import SDLWindowBackend
from termin.geombase import Pose3
from tgfx import TcShader, OpenGLGraphicsBackend
from termin._native.render import (
    RenderEngine,
    ColorPass,
    PresentToScreenPass,
    SkyBoxPass,
    BloomPass,
    TonemapPass,
    TcMaterial,
    ResourceSpec,
)
from termin.visualization.render.framegraph.passes.present import ResolvePass
from termin.render_framework import RenderPipeline
from tmesh import TcMesh, CubeMesh


VERT = """
#version 330 core
layout(location=0) in vec3 a_position;
layout(location=1) in vec3 a_normal;
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
    // HDR-ish cube so bloom has something to pick up.
    FragColor = vec4(u_color.rgb * (0.5 + 2.5 * ndotl), u_color.a);
}
"""


def make_pipeline():
    passes = [
        SkyBoxPass(input_res="empty", output_res="skybox", pass_name="Skybox"),
        ColorPass(
            input_res="skybox", output_res="color",
            shadow_res="", pass_name="Color", phase_mark="opaque",
        ),
        ResolvePass(input_res="color", output_res="color_resolved", pass_name="Resolve"),
        BloomPass(
            input_res="color_resolved", output_res="color_bloom",
            threshold=1.0, soft_threshold=0.5, intensity=1.0, mip_levels=5,
        ),
        TonemapPass(
            input_res="color_bloom", output_res="color_tonemapped",
            method=2,  # NONE — same as editor default
        ),
        PresentToScreenPass(input_res="color_tonemapped", pass_name="Present"),
    ]
    specs = [
        ResourceSpec(
            resource="empty",
            samples=4,
            format="rgba16f",
            clear_color=(0.2, 0.2, 0.2, 1.0),
            clear_depth=1.0,
        ),
        ResourceSpec(resource="color_resolved", format="rgba16f"),
        ResourceSpec(resource="color_tonemapped", format="rgba16f"),
    ]
    return RenderPipeline(name="repro", _init_passes=passes, _init_specs=specs)


def build_scene():
    shader = TcShader.from_sources(VERT, FRAG, "", "ReproShader")
    material = TcMaterial(
        name="ReproMaterial",
        shader=shader,
        color=np.array([0.8, 0.3, 0.2, 1.0], dtype=np.float32),
    )
    mesh3 = CubeMesh()
    tc_mesh = TcMesh.from_mesh3(mesh3, "ReproCube")

    cube = Entity(pose=Pose3.identity(), name="cube")
    cube.add_component(MeshRenderer(tc_mesh, material))

    scene = TcScene.create(name="repro")
    scene.add(cube)

    rs = scene_render_state(scene)
    rs.set_skybox_type(1)
    rs.set_skybox_top_color(0.2, 0.5, 0.9)
    rs.set_skybox_bottom_color(0.95, 0.6, 0.3)

    cam_entity = Entity(pose=Pose3.looking_at([0, -4, 0], [0, 0, 0]), name="camera")
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

    handle = sdl_backend.create_window(width=800, height=600, title="tonemap repro")
    display = Display(handle)
    viewport = display.create_viewport(scene=scene, camera=camera, name="main")

    from termin.render_framework import render_target_new
    rt = render_target_new("main")
    rt.scene = scene
    rt.camera = camera
    rt.pipeline = make_pipeline()
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

        engine.render_view_to_fbo(
            pipeline, display_fbo, width, height,
            scene, camera, viewport,
            viewport.layer_mask,
        )
        display.present()

    sdl_backend.terminate()


if __name__ == "__main__":
    main()
