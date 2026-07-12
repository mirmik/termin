import subprocess
import sys
import textwrap


def test_scene_destroy_runs_component_removal_lifecycle_with_external_reference():
    subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import termin.bootstrap
                from termin.scene import PythonComponent, TcScene

                termin.bootstrap.bootstrap_player()
                events = []

                class SceneDestroyLifecycleProbe(PythonComponent):
                    def on_destroy(self):
                        events.append("destroy")

                    def on_removed(self):
                        events.append("removed")

                    def on_removed_from_entity(self):
                        events.append("removed_from_entity")

                scene = TcScene.create("scene-destroy-lifecycle")
                entity = scene.create_entity("entity")
                component = SceneDestroyLifecycleProbe()
                entity.add_component(component)

                scene.destroy()

                assert events == ["destroy", "removed", "removed_from_entity"]
                assert component.entity is None
                termin.bootstrap.shutdown_player()
                """
            ),
        ],
        check=True,
    )
