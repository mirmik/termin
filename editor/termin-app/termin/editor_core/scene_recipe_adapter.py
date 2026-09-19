"""Native scene and undo backend for :mod:`termin.scene_recipe`."""

from __future__ import annotations

import copy
import hashlib
import json
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from termin.scene import Entity
from termin.geombase import GeneralPose3, Vec3, Quat
from termin.prefab import PrefabInstanceState
from termin.prefab.asset import PrefabAsset
from termin.editor_core.editor_commands import (
    AddEntityCommand,
    DeleteEntityCommand,
    TransformEditCommand,
    EntityPropertyEditCommand,
)
from termin.editor_core.prefab_override_capture import capture_entity_property
from termin.editor_core.undo_stack import UndoCommand
from termin.scene_recipe import model
from termin.scene_recipe.service import Document

if TYPE_CHECKING:
    from termin.scene import TcScene
    from termin_assets import AssetRuntimeManager

LOG = logging.getLogger(__name__)


def fingerprint(data):
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def wrapper_properties(data):
    return {
        k: v
        for k, v in data.items()
        if k not in ("uuid", "name", "pose", "scale", "children")
    }


def walk(data):
    yield data
    for child in data["children"]:
        yield from walk(child)


def reference_index(scene):
    """Index registered entity/list[entity] fields using the native kind registry.

    One hierarchy serialization per scene root, one remap per entity. Ordinary
    strings and asset UUIDs are deliberately not treated as gameplay links.
    """
    records = {}
    for entity in scene.get_all_entities():
        if entity.transform.parent is None:
            records.update((node["uuid"], node) for node in walk(entity.serialize()))
    remap = {key: "recipe-reference:" + key for key in records}
    owners = {key: set() for key in records}

    def changed_refs(before, after, owner):
        if isinstance(before, dict) and isinstance(after, dict):
            for key in before:
                changed_refs(before[key], after[key], owner)
        elif isinstance(before, list) and isinstance(after, list):
            for a, b in zip(before, after, strict=True):
                changed_refs(a, b, owner)
        elif isinstance(before, str) and before in remap and after == remap[before]:
            owners[before].add(owner)

    for key, record in records.items():
        shallow = dict(record, children=[])
        changed_refs(shallow, Entity.remap_entity_refs(shallow, remap), key)
    return records, owners


def references(index, targets):
    owners = set()
    for target in targets:
        owners.update(index[target])
    return sorted(owners - targets)


def snapshot(scene, recipe, ledger):
    live = {}
    records, ref_index = reference_index(scene)
    for key in set(recipe["objects"]) | set(ledger["objects"]):
        entry = ledger["objects"].get(key)
        entity = scene.get_entity(model.identity(recipe["namespace"], key))
        if entity is None:
            live[key] = None
            continue
        if entry is None:
            live[key] = {"collision": True}
            continue
        if entry["uuid"] != entity.uuid:
            raise ValueError("Invalid placement identity in ledger: " + key)
        data = records[entity.uuid]
        content = scene.get_entity(entry["content_uuid"])
        invalid = []
        if entity.transform.parent is not None:
            invalid.append("Placement was reparented; root placements are required")
        if (
            content is None
            or content.transform.parent is None
            or content.transform.parent.entity.uuid != entity.uuid
        ):
            invalid.append("Tracked prefab content missing or reparented")
        state = (
            content.get_component(PrefabInstanceState) if content is not None else None
        )
        if state is None:
            invalid.append("Missing PrefabInstanceState")
        elif (
            not state.mapping_valid
            or not state.overrides_valid
            or not state.structural_overrides_valid
        ):
            invalid.append("Invalid native prefab mapping/overrides")
        blocks = list(invalid)
        if len(data["children"]) != 1:
            blocks.append("Placement contains additional children")
        if content is not None:
            content_data = records[content.uuid]
            if fingerprint(content_data) != entry["content_fingerprint"]:
                blocks.append(
                    "Prefab content changed since insertion (including source reloads)"
                )
            targets = {node["uuid"] for node in walk(content_data)}
            refs = references(ref_index, targets)
            if refs:
                blocks.append(
                    "External references into prefab content: " + ", ".join(refs)
                )
        protected = list(blocks)
        if wrapper_properties(data) != entry["wrapper_defaults"]:
            protected.append("Placement has manual components or other properties")
        refs = references(ref_index, {entity.uuid})
        if refs:
            protected.append("External references to placement: " + ", ".join(refs))
        spec = dict(
            entry["labels"],
            name=entity.name,
            prefab=state.prefab_asset_uuid
            if state is not None
            else entry["base"]["prefab"],
            position=data["pose"]["position"],
            rotation=model.rotation(data["pose"]["rotation"]),
            scale=data["scale"],
        )
        live[key] = {
            "spec": spec,
            "invalid": invalid,
            "protected": protected,
            "replacement_blocks": blocks,
        }
    return live


def pose(spec):
    return GeneralPose3(
        lin=Vec3(*spec["position"]),
        ang=Quat(*spec["rotation"]),
        scale=Vec3(*spec["scale"]),
    )


class RecipeCommand(UndoCommand):
    def __init__(self, scene, before, result, assets):
        super().__init__("Synchronize scene recipe")
        self.scene, self.before = scene, copy.deepcopy(before)
        self.after, self.actions = copy.deepcopy(result["ledger"]), result["actions"]
        self.assets, self.commands, self.initialized = assets, [], False

    def metadata(self, value):
        if value is None:
            self.scene.clear_metadata_value(model.STATE_KEY)
        else:
            self.scene.set_metadata_value(model.STATE_KEY, copy.deepcopy(value))

    def apply(self, command):
        command.do()
        self.commands.append(command)

    def insert(self, parent, spec):
        content = self.assets[spec["prefab"]].instantiate(
            scene=self.scene, parent=parent.transform
        )
        if content is None or not content.valid():
            raise RuntimeError("Prefab instantiation returned no entity")
        return content

    def first_do(self):
        for action in self.actions:
            key, op = action["id"], action["op"]
            if op == "delete":
                self.apply(
                    DeleteEntityCommand(
                        self.scene,
                        self.scene.get_entity(self.before["objects"][key]["uuid"]),
                    )
                )
                continue
            entry = self.after["objects"][key]
            spec = action["after"]
            if op == "create":
                root = self.scene.add(Entity(name=spec["name"], uuid=entry["uuid"]))
                # Register rollback before instantiation, which can itself fail.
                self.commands.append(AddEntityCommand(self.scene, root))
                root.transform.set_local_pose(pose(spec))
                content = self.insert(root, spec)
                entry["wrapper_defaults"] = wrapper_properties(root.serialize())
            else:
                root = self.scene.get_entity(entry["uuid"])
                if root.name != spec["name"]:
                    self.apply(
                        EntityPropertyEditCommand(root, "name", root.name, spec["name"])
                    )
                if any(
                    not model.equal(action["before"][f], spec[f])
                    for f in ("position", "rotation", "scale")
                ):
                    self.apply(
                        TransformEditCommand(
                            root.transform, root.transform.local_pose(), pose(spec)
                        )
                    )
                if action["before"]["prefab"] == spec["prefab"]:
                    continue
                old = self.scene.get_entity(entry["content_uuid"])
                content = self.insert(root, spec)
                self.commands.append(AddEntityCommand(self.scene, content))
                self.apply(DeleteEntityCommand(self.scene, old))
            entry["content_uuid"] = content.uuid
            entry["content_fingerprint"] = fingerprint(content.serialize())

    def do(self):
        applied = []
        try:
            if not self.initialized:
                self.first_do()
            else:
                for command in self.commands:
                    command.do()
                    applied.append(command)
            self.metadata(self.after)
            self.initialized = True
        except Exception:
            LOG.exception("Recipe synchronization failed; rolling back")
            for command in reversed(applied if self.initialized else self.commands):
                command.undo()
            self.metadata(self.before)
            raise

    def undo(self):
        undone = []
        try:
            for command in reversed(self.commands):
                command.undo()
                undone.append(command)
            self.metadata(self.before)
        except Exception:
            LOG.exception("Recipe undo failed; restoring applied state")
            for command in reversed(undone):
                command.do()
            self.metadata(self.after)
            raise


class ResetPrefabTransform(TransformEditCommand):
    """Restore source pose and remove only transform override intent."""

    def __init__(self, entity, source_pose):
        super().__init__(entity.transform, entity.transform.local_pose(), source_pose)
        self.captures = [
            capture_entity_property(entity, field, kind)
            for field, kind in (
                ("transform.position", "vec3"),
                ("transform.rotation", "quat"),
                ("transform.scale", "vec3"),
            )
        ]
        if any(capture is None for capture in self.captures):
            raise ValueError("Cannot reset an unmapped prefab entity")

    def do(self):
        super().do()
        try:
            for capture in self.captures:
                capture.state.discard_property_override(
                    capture.source_entity_id, "", capture.field_path
                )
        except Exception:
            LOG.exception(
                "Could not clear transform overrides; restoring previous pose"
            )
            super().undo()
            raise


class SceneRecipeAdapter:
    """Bind recipe operations to explicit editor services and providers."""

    def __init__(
        self,
        *,
        scene_provider: Callable[[], TcScene | None],
        resource_manager: AssetRuntimeManager,
        is_play_mode: Callable[[], bool],
        push_undo_command: Callable[[UndoCommand], None],
        refresh_editor: Callable[[], None],
        request_render_update: Callable[[], None],
    ) -> None:
        self.scene_provider = scene_provider
        self.resource_manager = resource_manager
        self.is_play_mode = is_play_mode
        self.push_undo_command = push_undo_command
        self.refresh_editor = refresh_editor
        self.request_render_update = request_render_update

    def _scene(self) -> TcScene:
        if self.is_play_mode():
            raise RuntimeError("Exit Play mode before changing scene recipes")
        scene = self.scene_provider()
        if scene is None:
            raise RuntimeError("No active scene for scene recipe operations")
        return scene

    def snapshot(self, recipe: Document) -> tuple[Document | None, Document]:
        scene = self._scene()
        before = (
            scene.get_metadata_value(model.STATE_KEY)
            if scene.has_metadata_value(model.STATE_KEY)
            else None
        )
        ledger = before or {"version": 1, "namespace": recipe["namespace"], "objects": {}}
        if ledger["namespace"] != recipe["namespace"]:
            raise ValueError("Another recipe namespace already owns this scene")
        return before, snapshot(scene, recipe, ledger)

    def commit(self, before: Document | None, result: Document) -> Document:
        scene = self._scene()
        if result["conflicts"]:
            return dict(result, applied=False)
        assets = {}
        for action in result["actions"]:
            if action["op"] == "delete":
                continue
            asset_id = action["after"]["prefab"]
            asset = self.resource_manager.get_asset_by_uuid(asset_id)
            if not isinstance(asset, PrefabAsset):
                raise ValueError("Prefab not available: " + asset_id)
            asset.ensure_loaded()
            if asset.root_data is None:
                raise ValueError("Prefab has no root: " + asset_id)
            assets[asset_id] = asset
        if result["actions"] or before != result["ledger"]:
            self.push_undo_command(RecipeCommand(scene, before, result, assets))
            self.refresh_editor()
            self.request_render_update()
        return dict(
            result,
            applied=True,
            ledger=scene.get_metadata_value(model.STATE_KEY),
        )

    def reset_transform(
        self, recipe: Document, before: Document, key: str, current: Document
    ) -> Document:
        """Explicitly reset one placement and its source-owned internal transforms.

        Other recipe changes and conflict resolutions are deliberately not applied.
        Non-transform overrides, names, references and UUIDs are retained.
        """
        scene = self._scene()
        if current["invalid"]:
            raise ValueError("Cannot reset invalid placement: " + str(current["invalid"]))
        incoming = recipe["objects"]
        if key not in incoming:
            raise ValueError("Selected placement is missing from the supplied recipe")
        entry = before["objects"][key]
        content = scene.get_entity(entry["content_uuid"])
        state = content.get_component(PrefabInstanceState)
        if state.structural_override_count:
            raise ValueError("Transform reset requires unchanged prefab structure")
        asset = self.resource_manager.get_asset_by_uuid(state.prefab_asset_uuid)
        if not isinstance(asset, PrefabAsset):
            raise ValueError("Current prefab source is unavailable")
        asset.ensure_loaded()
        if asset.root_data is None:
            raise ValueError("Current prefab has no source root")
        sources = {node["uuid"]: node for node in walk(asset.root_data)}
        commands = []
        root = scene.get_entity(entry["uuid"])
        spec = dict(current["spec"])
        fields = ("position", "rotation", "scale")
        for field in fields:
            spec[field] = incoming[key][field]
        if any(not model.equal(spec[f], current["spec"][f]) for f in fields):
            commands.append(
                TransformEditCommand(
                    root.transform, root.transform.local_pose(), pose(spec)
                )
            )
        for node in walk(content.serialize()):
            entity = scene.get_entity(node["uuid"])
            source_id = state.source_for_entity(entity)
            if source_id not in sources:
                raise ValueError(
                    "Unmapped or outdated prefab structure; cannot reset transforms"
                )
            source = sources[source_id]
            target = dict(source["pose"], scale=source.get("scale", [1, 1, 1]))
            actual = dict(node["pose"], scale=node["scale"])
            overridden = any(
                state.get_property_override(source_id, "", "transform." + field) is not None
                for field in fields
            )
            if not model.equal(actual, target) or overridden:
                commands.append(ResetPrefabTransform(entity, pose(target)))
        after = copy.deepcopy(before)
        for field in fields:
            after["objects"][key]["base"][field] = incoming[key][field]
        result = {
            "actions": [{"op": "reset-transform", "id": key, "transforms": len(commands)}]
            if commands
            else [],
            "conflicts": [],
            "kept": [],
            "ledger": after,
        }
        if commands or before != after:
            command = RecipeCommand(scene, before, result, {})
            command.text = "Reset placement transforms: " + root.name
            command.commands = commands
            command.initialized = True
            self.push_undo_command(command)
            self.refresh_editor()
            self.request_render_update()
        return dict(result, applied=True)
