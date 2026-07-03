import subprocess
import sys
import textwrap


def _run_python(code: str) -> None:
    subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        check=True,
    )


def test_unknown_component_upgrade_preserves_python_default_enabled():
    _run_python(
        """
        import termin.bootstrap
        from termin.scene import Entity, PythonComponent, TcScene, upgrade_unknown_components

        termin.bootstrap.bootstrap_player()
        scene = TcScene.create("unknown-python-default-enabled")
        entity = Entity.deserialize(
            {
                "name": "root",
                "components": [
                    {"type": "ProbeUnknownDefaultEnabledComponent", "data": {}},
                ],
            },
            None,
            scene,
        )

        class ProbeUnknownDefaultEnabledComponent(PythonComponent):
            pass

        stats = upgrade_unknown_components(scene)
        restored = entity.get_python_component("ProbeUnknownDefaultEnabledComponent")
        assert stats.upgraded == 1
        assert restored is not None
        assert restored.enabled is True

        scene.destroy()
        termin.bootstrap.shutdown_player()
        """
    )


def test_unknown_component_upgrade_applies_serialized_python_disabled_state():
    _run_python(
        """
        import termin.bootstrap
        from termin.scene import Entity, PythonComponent, TcScene, upgrade_unknown_components

        termin.bootstrap.bootstrap_player()
        scene = TcScene.create("unknown-python-disabled")
        entity = Entity.deserialize(
            {
                "name": "root",
                "components": [
                    {
                        "type": "ProbeUnknownDisabledComponent",
                        "data": {"enabled": False},
                    },
                ],
            },
            None,
            scene,
        )

        class ProbeUnknownDisabledComponent(PythonComponent):
            pass

        stats = upgrade_unknown_components(scene)
        restored = entity.get_python_component("ProbeUnknownDisabledComponent")
        assert stats.upgraded == 1
        assert restored is not None
        assert restored.enabled is False

        scene.destroy()
        termin.bootstrap.shutdown_player()
        """
    )
