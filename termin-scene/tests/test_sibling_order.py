import subprocess
import sys
import textwrap


def test_sibling_order_is_domain_owned_and_survives_scene_roundtrip() -> None:
    subprocess.run(
        [
            sys.executable,
            "-c",
            textwrap.dedent(
                """
                import termin.bootstrap
                from termin.scene import TcScene

                termin.bootstrap.bootstrap_player()
                scene = TcScene.create("sibling-order-source")
                first = scene.create_entity("first")
                second = scene.create_entity("second")
                third = scene.create_entity("third")
                events = []
                subscription = scene.subscribe_event(
                    "tc.scene.structure_changed", events.append
                )

                assert [entity.name for entity in scene.root_entities] == [
                    "first", "second", "third"
                ]
                third.sibling_index = 0
                assert third.sibling_index == 0
                assert events[-1]["kind_name"] == "sibling_order_changed"
                assert [entity.name for entity in scene.root_entities] == [
                    "third", "first", "second"
                ]

                child_a = first.create_child("child-a")
                child_b = first.create_child("child-b")
                child_c = first.create_child("child-c")
                child_c.sibling_index = 1
                assert [entity.name for entity in first.children()] == [
                    "child-a", "child-c", "child-b"
                ]

                payload = scene.serialize()
                assert [entity["name"] for entity in payload["entities"]] == [
                    "third", "first", "second"
                ]
                assert [entity["name"] for entity in payload["entities"][1]["children"]] == [
                    "child-a", "child-c", "child-b"
                ]

                restored = TcScene.create("sibling-order-restored")
                assert restored.load_from_data(payload) == 6
                assert [entity.name for entity in restored.root_entities] == [
                    "third", "first", "second"
                ]
                restored_first = restored.find_entity_by_name("first")
                assert [entity.name for entity in restored_first.children()] == [
                    "child-a", "child-c", "child-b"
                ]

                restored.destroy()
                subscription.unsubscribe()
                scene.destroy()
                termin.bootstrap.shutdown_player()
                """
            ),
        ],
        check=True,
    )
