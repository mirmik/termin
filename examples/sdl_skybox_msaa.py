#!/usr/bin/env python

"""SDL2 window with a skybox rendered into an MSAA + HDR target.

This reproduces the editor pipeline's output-target configuration:
    samples = 4
    format = rgba16f
    + ResolvePass to resolve MSAA before Present

Used to diagnose the "editor window goes black" regression after Stage 6.
If this script shows the sky correctly, the editor issue is about pass
interactions, not the MSAA/HDR attachment itself.
"""

from __future__ import annotations

from termin.entity import Entity, TcScene
from termin.entity._entity_native import OrbitCameraController, scene_render_state
from termin.render_components import PerspectiveCameraComponent
from termin.display.display import Display
from termin.display.sdl_backend import SDLWindowBackend
from termin.geombase import Pose3
from termin._native.render import (
    RenderEngine,
    PresentToScreenPass,
    SkyBoxPass,
    ResourceSpec,
)
from termin.visualization.render.framegraph.passes.present import ResolvePass
from tgfx import OpenGLGraphicsBackend
from termin.render_framework import RenderPipeline


def make_pipeline():
    passes = [
        SkyBoxPass(input_res="empty", output_res="color", pass_name="Skybox"),
        ResolvePass(input_res="color", output_res="color_resolved", pass_name="Resolve"),
        PresentToScreenPass(input_res="color_resolved", pass_name="Present"),
    ]

    specs = [
        ResourceSpec(
            resource="empty",
            samples=4,
            format="rgba16f",
            clear_color=(0.2, 0.2, 0.2, 1.0),
            clear_depth=1.0,
        ),
        ResourceSpec(
            resource="color_resolved",
            format="rgba16f",
        ),
    ]

    return RenderPipeline(name="sdl_skybox_msaa", _init_passes=passes, _init_specs=specs)


def build_scene():
    scene = TcScene.create(name="sdl_skybox_msaa")
    rs = scene_render_state(scene)
    rs.set_skybox_type(1)  # GRADIENT
    rs.set_skybox_top_color(0.2, 0.5, 0.9)
    rs.set_skybox_bottom_color(0.95, 0.6, 0.3)

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

    handle = sdl_backend.create_window(width=800, height=600, title="termin skybox — MSAA+HDR")
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
