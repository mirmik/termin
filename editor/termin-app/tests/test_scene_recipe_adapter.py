"""Exercise the extracted service against real native scenes and prefab instances."""
import copy
import uuid

import pytest
from termin.bootstrap import bootstrap_player, shutdown_player
from termin.scene import TcScene, PythonComponent, publish_python_component
from termin.inspect import InspectField
from termin.prefab.asset import PrefabAsset
from termin.prefab import PrefabInstanceState
from termin.editor_core import scene_recipe_adapter as recipe_editor
from termin.editor_core.undo_stack import UndoStack
from termin.editor_core.editor_commands import (
    EntityPropertyEditCommand, TransformEditCommand, DeleteEntityCommand,
)
from termin.scene_recipe import SceneRecipeService
from termin.scene_recipe import model


class AssetLookup:
    def __init__(self, assets):
        self.assets = {asset.uuid: asset for asset in assets}
        self.ids = list(self.assets)

    def get_asset_by_uuid(self, uuid):
        return self.assets.get(uuid)


@pytest.fixture
def recipe_assets():
    bootstrap_player()
    source = TcScene.create("recipe-test-prefabs")
    try:
        assets = []
        for name in ("Cover", "Vent"):
            root = source.create_entity(name)
            child = source.create_entity(name + " child")
            child.transform.set_parent(root.transform)
            assets.append(PrefabAsset.from_entity(root))
        yield AssetLookup(assets)
    finally:
        source.destroy()
        shutdown_player()


def make_service(scene, stack, assets, is_play_mode=lambda: False):
    return SceneRecipeService(recipe_editor.SceneRecipeAdapter(
        scene_provider=lambda: scene,
        resource_manager=assets,
        is_play_mode=is_play_mode,
        push_undo_command=stack.push,
        refresh_editor=lambda: None,
        request_render_update=lambda: None,
    ))


class RecipeReferenceProbe(PythonComponent):
    inspect_fields = {
        "target": InspectField(path="target", label="Target", kind="entity")
    }

    def __init__(self):
        super().__init__()
        self.target = None

def test_recipe_lifecycle(recipe_assets):
    publish_python_component(RecipeReferenceProbe, owner="recipe-sync-verification")
    test_scene = TcScene.create("recipe-sync-verification")
    stack = UndoStack()
    service = make_service(test_scene, stack, recipe_assets)
    cover, vent = recipe_assets.ids
    recipe = dict(
        version=1,
        namespace="ba5bd7be-daba-4ae1-89e8-9321ee1a2530",
        objects=[
            dict(id=key, prefab=cover, position=[i * 3, 0, 0])
            for i, key in enumerate(("a", "b", "c"))
        ],
    )
    checks = []

    def run(action="sync", value=None, **kwargs):
        return service.run(action, value or recipe, **kwargs)

    def root(key):
        return test_scene.get_entity(model.identity(recipe["namespace"], key))

    def ledger():
        return test_scene.get_metadata_value(model.STATE_KEY)

    def move(key, x):
        entity = root(key)
        spec = run("list")[key]["spec"]
        spec["position"] = [x, 0, 0]
        stack.push(
            TransformEditCommand(
                entity.transform,
                entity.transform.local_pose(),
                recipe_editor.pose(spec),
            )
        )

    try:
        initial = run()
        assert initial["applied"] and initial["ledger"] == ledger()
        assert not run("plan")["actions"]
        stack.undo()
        assert test_scene.entity_count() == 0 and not test_scene.has_metadata_value(
            model.STATE_KEY
        )
        stack.redo()
        assert not run("list")["a"]["replacement_blocks"]
        checks.append("create, idempotence, undo/redo metadata and hierarchy")
        move("a", 7)
        stack.push(EntityPropertyEditCommand(root("a"), "name", "a", "South cover"))
        stack.push(DeleteEntityCommand(test_scene, root("b")))
        recipe["objects"][2]["position"] = [9, 0, 0]
        assert run()["applied"]
        assert (
            root("a").name == "South cover"
            and root("a").transform.local_pose().lin.x == 7
        )
        assert root("b") is None and root("c").transform.local_pose().lin.x == 9
        checks.append(
            "manual move/rename/delete preserved; independent source edit applied"
        )
        recipe["objects"][0]["position"] = [11, 0, 0]
        recipe["objects"].append(dict(id="d", prefab=cover, position=[0, 3, 0]))
        before = test_scene.serialize()
        assert not run()["applied"] and test_scene.serialize() == before
        assert root("d") is None
        assert run(resolutions={"a": {"position": "scene"}})["applied"]
        assert root("a").transform.local_pose().lin.x == 7 and root("d") is not None
        assert not run("plan")["conflicts"]
        checks.append("conflict is atomic; explicit scene resolution advances baseline")
        recipe["objects"][0]["position"] = [12, 0, 0]
        assert run(resolutions={"a": {"position": "recipe"}})["applied"]
        assert root("a").transform.local_pose().lin.x == 12
        checks.append("explicit recipe resolution")
        watcher = test_scene.create_entity("reference owner")
        reference = RecipeReferenceProbe()
        reference.target = root("a")
        watcher.add_component(reference)
        marker = RecipeReferenceProbe()
        marker.target = root("c")
        root("a").add_component(marker)
        old_content = ledger()["objects"]["a"]["content_uuid"]
        original_uuid = root("a").uuid
        assert run("replace", selector="South cover", prefab=vent)["applied"]
        assert (
            root("a").uuid == original_uuid and reference.target.uuid == original_uuid
        )
        assert (
            root("a").get_component(RecipeReferenceProbe).target.uuid == root("c").uuid
        )
        assert root("a").transform.local_pose().lin.x == 12
        assert not run("plan")["actions"]
        stack.undo()
        assert (
            ledger()["objects"]["a"]["content_uuid"] == old_content
            and test_scene.get_entity(old_content) is not None
        )
        stack.redo()
        assert not run("list")["a"]["replacement_blocks"]
        checks.append(
            "replacement preserves wrapper, pose, name, components and wrapper references; undo/redo"
        )
        reference.target = test_scene.get_entity(
            ledger()["objects"]["a"]["content_uuid"]
        )
        assert not run("replace", selector="a", prefab=cover)["applied"]
        reference.target = root("a")
        content = test_scene.get_entity(ledger()["objects"]["a"]["content_uuid"])
        stack.push(
            EntityPropertyEditCommand(
                content, "name", content.name, "manual content edit"
            )
        )
        assert not run("replace", selector="a", prefab=cover)["applied"]
        stack.undo()
        checks.append("replacement blocked by internal references and native overrides")
        removed = copy.deepcopy(recipe)
        removed["objects"] = [
            item for item in recipe["objects"] if item["id"] not in ("a", "d")
        ]
        assert not run(value=removed)["applied"]
        assert run(value=removed, resolutions={"a": {"existence": "scene"}})["applied"]
        assert (
            root("a") is not None
            and root("d") is None
            and "a" not in ledger()["objects"]
        )
        assert run("plan", value=recipe)["conflicts"][0]["field"] == "identity"
        stack.undo()
        assert "a" in ledger()["objects"] and root("d") is not None
        checks.append(
            "safe deletion, keep-and-detach, detached identity collision, undo"
        )
        saved = test_scene.serialize()
        restored = TcScene.create("recipe-sync-roundtrip")
        try:
            restored.load_from_data(saved)
            loaded_service = make_service(restored, UndoStack(), recipe_assets)
            report = loaded_service.run("plan", recipe)
            assert not report["conflicts"] and not report["actions"], report
            assert not loaded_service.run("list", recipe)["a"][
                "replacement_blocks"
            ]
        finally:
            restored.destroy()
        checks.append(
            "serialized scene reload preserves baseline and content fingerprints"
        )
        invalid = copy.deepcopy(recipe)
        invalid["objects"].append(dict(id="unavailable", prefab=str(uuid.uuid4())))
        before = test_scene.serialize()
        try:
            run(value=invalid)
        except ValueError:
            pass
        else:
            raise AssertionError("Missing prefab accepted")
        assert test_scene.serialize() == before
        checks.append("missing prefab fails preflight without mutation")
        failing = copy.deepcopy(recipe)
        failing["objects"] = [item for item in failing["objects"] if item["id"] != "d"]
        failing["objects"].append(dict(id="z-failure", prefab=cover))
        original_insert = recipe_editor.RecipeCommand.insert
        before_ledger = copy.deepcopy(ledger())
        before_entities = {e.uuid: e.serialize() for e in test_scene.get_all_entities()}
        before_undo_count = len(stack.done_commands)

        def fail_insert(command, parent, spec):
            raise RuntimeError("Injected instantiation failure")

        recipe_editor.RecipeCommand.insert = fail_insert
        try:
            try:
                run(value=failing)
            except RuntimeError as exc:
                assert str(exc) == "Injected instantiation failure"
            else:
                raise AssertionError("Injected failure did not propagate")
        finally:
            recipe_editor.RecipeCommand.insert = original_insert
        assert ledger() == before_ledger
        assert {
            e.uuid: e.serialize() for e in test_scene.get_all_entities()
        } == before_entities
        assert len(stack.done_commands) == before_undo_count
        checks.append(
            "mid-transaction failure restores deleted entities, new roots and ledger"
        )
        assert len(checks) == 10
    finally:
        stack.clear()
        test_scene.destroy()


def test_selected_transform_reset(recipe_assets):
    test = TcScene.create("selected-reset-test")
    stack = UndoStack()
    service = make_service(test, stack, recipe_assets)
    recipe = dict(
        version=1,
        namespace="bd2d4268-7531-4318-b45f-ddaa3a6922e1",
        objects=[
            dict(
                id=key,
                prefab=recipe_assets.ids[0],
                position=[i * 3, 0, 0],
            )
            for i, key in enumerate(("a", "b"))
        ],
    )
    try:
        service.run( "sync", recipe)
        a, b = [
            test.get_entity(model.identity(recipe["namespace"], key))
            for key in ("a", "b")
        ]
        child = a.transform.children[0].entity.transform.children[0].entity
        for entity, xyz in ((a, [2, 3, 0]), (b, [5, 6, 0]), (child, [0, 14, 0])):
            stack.push(
                TransformEditCommand(
                    entity.transform,
                    entity.transform.local_pose(),
                    recipe_editor.pose(
                        dict(position=xyz, rotation=[0, 0, 0, 1], scale=[1, 1, 1])
                    ),
                )
            )
        stack.push(
            EntityPropertyEditCommand(child, "name", child.name, "Custom inner name")
        )
        before_a, before_b = a.serialize(), b.serialize()
        ledger = copy.deepcopy(test.get_metadata_value(model.STATE_KEY))
        changed_recipe = copy.deepcopy(recipe)
        changed_recipe["objects"][1]["position"] = [
            99,
            0,
            0,
        ]  # Other object's unresolved conflict must not be applied.
        result = service.run( "reset-transform", changed_recipe, selector="a"
        )
        assert result["applied"] and len(result["actions"]) == 1
        assert (
            a.transform.local_pose().lin.x == 0
            and child.transform.local_pose().lin.y == 0
        )
        assert child.name == "Custom inner name" and b.serialize() == before_b
        assert test.get_metadata_value(model.STATE_KEY) == ledger
        state = a.transform.children[0].entity.get_component(PrefabInstanceState)
        assert state.property_override_count == 1  # Only the name override remains.
        after_a = a.serialize()
        stack.undo()
        assert a.serialize() == before_a and b.serialize() == before_b
        stack.redo()
        assert a.serialize() == after_a and b.serialize() == before_b
        assert not service.run( "reset-transform", recipe, selector="a")[
            "actions"
        ]
        print(
            "PASS: selected root and internal transforms reset; other object/name override/ledger preserved; Undo/Redo; idempotence"
        )
    finally:
        stack.clear()
        test.destroy()
