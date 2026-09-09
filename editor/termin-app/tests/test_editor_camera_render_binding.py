"""Exercise the editor camera through the actual target and viewport adapters."""

import subprocess
import sys
import textwrap


def test_editor_camera_target_and_picking_use_interpolated_projection():
    subprocess.run([sys.executable, "-c", textwrap.dedent("""
        import gc
        import termin.bootstrap
        termin.bootstrap.bootstrap_player()
        from termin.editor._editor_native import EditorCameraComponent
        from termin.geombase import Rect2, Vec3
        from termin.render_framework import render_target_new
        from termin.scene import Entity, TcScene
        from termin.viewport import Viewport

        scene = TcScene.create("editor-camera-binding")
        entity = Entity(name="editor-camera")
        entity.add_component_by_name("EditorCameraComponent")
        camera = entity.get_component_by_type("EditorCameraComponent")
        assert isinstance(camera, EditorCameraComponent)
        assert entity.scene is None
        camera.aspect = 4.0 / 3.0
        camera.near_clip = 0.1
        camera.far_clip = 100.0
        renders = []
        camera.request_render_callback = lambda: renders.append(True)
        target = render_target_new("editor-camera-binding")
        target.scene = scene
        target.camera = camera
        assert isinstance(target.camera, EditorCameraComponent)
        assert target.camera.c_component_ptr() == camera.c_component_ptr()
        viewport = Viewport("editor-camera-binding", scene, camera,
                            pixel_rect=(0, 0, 800, 600))
        viewport.render_target = target
        plane_point = Vec3(1.0, 5.0, 0.5)
        rect = Rect2(0.0, 0.0, 800.0, 600.0)
        baseline = camera.try_project_world_point(plane_point, rect)
        assert baseline is not None
        camera.enter_axis_view(5.0)
        for dt in (0.0, 0.05, 0.05, 0.2):
            camera.update(dt)
            projected = camera.try_project_world_point(plane_point, rect)
            assert projected is not None
            ray = viewport.screen_point_to_ray(projected.screen.x, projected.screen.y)
            assert ray is not None
            hit = ray.try_intersect_plane(Vec3(0.0, 5.0, 0.0), Vec3(0.0, 1.0, 0.0))
            assert hit is not None and (hit - plane_point).norm() < 1e-5
            assert abs(projected.screen.x - baseline.screen.x) < 1e-8
            assert abs(projected.screen.y - baseline.screen.y) < 1e-8
        assert renders and not camera.transitioning
        count = len(renders)
        camera.update(0.1)
        assert len(renders) == count
        camera.request_render_callback = None
        viewport.render_target = None
        viewport.destroy()
        target.camera = None
        target.scene = None
        target.free()
        scene.destroy()
        del camera, entity, scene
        gc.collect()
        termin.bootstrap.shutdown_player()
    """)], check=True)
