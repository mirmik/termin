import subprocess
import sys
import textwrap


def _run_python(code: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        check=True,
        capture_output=True,
        text=True,
    )


def test_python_lifecycle_overrides_and_class_replacement_reindex_scene() -> None:
    _run_python(
        """
        import termin.bootstrap
        from termin.scene import PythonComponent, TcScene

        termin.bootstrap.bootstrap_player()
        calls = {"update": 0, "fixed": 0, "before": 0}

        class EmptyLifecycleProbe(PythonComponent):
            pass

        class FullLifecycleProbe(PythonComponent):
            def update(self, dt):
                calls["update"] += 1

            def fixed_update(self, dt):
                calls["fixed"] += 1

            def before_render(self):
                calls["before"] += 1

        scene = TcScene.create("python-lifecycle-indexes")
        scene.fixed_timestep = 1.0
        empty_entity = scene.create_entity("empty")
        full_entity = scene.create_entity("full")
        empty = EmptyLifecycleProbe()
        full = FullLifecycleProbe()
        empty_entity.add_component(empty)

        assert scene.update_list_count == 0
        assert scene.fixed_update_list_count == 0
        assert scene.before_render_list_count == 0

        full_entity.add_component(full)
        assert scene.update_list_count == 1
        assert scene.fixed_update_list_count == 1
        assert scene.before_render_list_count == 1

        scene.update(1.0)
        scene.before_render()
        assert calls == {"update": 1, "fixed": 1, "before": 1}

        full.has_update = False
        full.has_fixed_update = False
        full.has_before_render = False
        assert scene.update_list_count == 0
        assert scene.fixed_update_list_count == 0
        assert scene.before_render_list_count == 0

        scene.update(1.0)
        scene.before_render()
        assert calls == {"update": 1, "fixed": 1, "before": 1}

        class ReloadedLifecycleProbe(PythonComponent):
            def before_render(self):
                calls["before"] += 1

        full.__class__ = ReloadedLifecycleProbe
        full.refresh_lifecycle_capabilities()
        assert scene.update_list_count == 0
        assert scene.fixed_update_list_count == 0
        assert scene.before_render_list_count == 1

        scene.before_render()
        assert calls == {"update": 1, "fixed": 1, "before": 2}

        scene.destroy()
        termin.bootstrap.shutdown_player()
        """
    )


def test_python_before_render_exception_is_logged() -> None:
    completed = _run_python(
        """
        import termin.bootstrap
        from termin.scene import PythonComponent, TcScene

        termin.bootstrap.bootstrap_player()

        class FailingBeforeRenderProbe(PythonComponent):
            def before_render(self):
                raise RuntimeError("before-render-probe-error")

        scene = TcScene.create("python-before-render-error")
        entity = scene.create_entity("entity")
        entity.add_component(FailingBeforeRenderProbe())
        scene.before_render()
        scene.destroy()
        termin.bootstrap.shutdown_player()
        """
    )

    output = completed.stdout + completed.stderr
    assert "PythonComponent::before_render" in output
    assert "before-render-probe-error" in output
