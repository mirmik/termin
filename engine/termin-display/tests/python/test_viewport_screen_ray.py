import subprocess
import sys
import textwrap


def test_viewport_screen_ray_preserves_checked_miss_and_unexpected_error_contracts():
    code = textwrap.dedent(
        """
        import gc

        import termin.bootstrap
        from termin.geombase import Rect2, Vec2
        from termin.render_framework import render_target_new
        from termin.scene import ComponentRegistry, PythonComponent, TcScene
        from termin.viewport import Viewport

        termin.bootstrap.bootstrap_player()

        class ProbeCamera(PythonComponent):
            def __init__(self):
                super().__init__()
                self.fail_unexpectedly = False

            def try_screen_point_to_ray(self, screen_point, viewport):
                assert type(screen_point) is Vec2
                assert (screen_point.x, screen_point.y) == (400.0, 300.0)
                assert type(viewport) is Rect2
                assert (viewport.x, viewport.y, viewport.width, viewport.height) == (0.0, 0.0, 800.0, 600.0)
                if self.fail_unexpectedly:
                    raise RuntimeError("camera binding contract failed")
                return None

        registry = ComponentRegistry.instance()
        assert registry.register_python(
            "ProbeCamera",
            ProbeCamera,
            "termin-display-screen-ray-test",
            "CameraComponent",
        )

        scene = TcScene.create("viewport-screen-ray-contract")
        entity = scene.create_entity("camera")
        camera = ProbeCamera()
        entity.add_component(camera)
        target = render_target_new("viewport-screen-ray-contract")
        target.scene = scene
        target.camera = camera
        viewport = Viewport(
            "viewport-screen-ray-contract",
            scene,
            camera,
            pixel_rect=(0, 0, 800, 600),
        )
        viewport.render_target = target

        assert viewport.screen_point_to_ray(400.0, 300.0) is None

        camera.fail_unexpectedly = True
        try:
            viewport.screen_point_to_ray(400.0, 300.0)
        except RuntimeError as error:
            assert "camera binding contract failed" in str(error)
        else:
            raise AssertionError("viewport adapter suppressed an unexpected camera exception")

        viewport.render_target = None
        viewport.destroy()
        target.camera = None
        target.scene = None
        target.free()
        scene.destroy()
        del camera
        del entity
        del scene
        gc.collect()
        assert registry.unregister_python("ProbeCamera")
        termin.bootstrap.shutdown_player()
        """
    )

    subprocess.run([sys.executable, "-c", code], check=True)
