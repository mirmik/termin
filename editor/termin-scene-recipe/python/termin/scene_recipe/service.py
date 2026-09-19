"""Engine-free scene recipe operations over an explicit editor backend."""

from __future__ import annotations

import copy
import logging
from typing import Any, Protocol

from . import model

LOG = logging.getLogger(__name__)
Document = dict[str, Any]


class SceneRecipeBackend(Protocol):
    """The host owns scene access, mutation, and undo transactions.

    Recipes passed to snapshot/reset_transform have been normalized by the
    service. Snapshot returns the persisted ledger and current placements.
    """

    def snapshot(self, recipe: Document) -> tuple[Document | None, Document]: ...

    def commit(self, before: Document | None, result: Document) -> Document: ...

    def reset_transform(
        self, recipe: Document, before: Document, key: str, current: Document
    ) -> Document: ...


class SceneRecipeService:
    def __init__(self, backend: SceneRecipeBackend) -> None:
        self.backend = backend

    def run(
        self,
        action: str,
        recipe: Document,
        resolutions: Document | None = None,
        selector: str | None = None,
        prefab: str | None = None,
    ) -> Document:
        """List, plan, synchronize, replace, or reset a recipe placement."""
        try:
            return self._run(action, recipe, resolutions, selector, prefab)
        except Exception:
            LOG.exception("Scene recipe operation %s failed", action)
            raise

    def _run(self, action, recipe, resolutions=None, selector=None, prefab=None):
        recipe = model.normalize(recipe)
        before, live = self.backend.snapshot(recipe)
        ledger = before or {"version": 1, "namespace": recipe["namespace"], "objects": {}}
        result = model.plan(recipe, ledger, live, resolutions)
        if action == "list":
            return {
                key: dict(value or {}, uuid=model.identity(recipe["namespace"], key))
                for key, value in live.items()
            }
        if action == "plan":
            return result
        if action == "sync":
            return self.backend.commit(before, result)
        if action not in ("replace", "reset-transform"):
            raise ValueError("Unknown recipe operation: " + action)
        if before is None:
            raise ValueError("No tracked placements")
        matches = [
            key
            for key, value in live.items()
            if key in before["objects"]
            and value
            and (key == selector or value["spec"]["name"] == selector)
        ]
        if selector in before["objects"] and live.get(selector):
            matches = [selector]
        if len(matches) != 1:
            raise ValueError(
                "Selector must identify one existing placement: " + str(selector)
            )
        key = matches[0]
        current = live[key]
        if action == "reset-transform":
            return self.backend.reset_transform(recipe, before, key, current)
        if current["replacement_blocks"]:
            return {
                "applied": False,
                "conflicts": [
                    {
                        "id": key,
                        "field": "replacement",
                        "reason": current["replacement_blocks"],
                    }
                ],
            }
        spec = dict(current["spec"], prefab=prefab)
        # Validate replacement UUID and vectors through the same recipe schema.
        spec = model.normalize(
            dict(version=1, namespace=recipe["namespace"], objects=[dict(spec, id=key)])
        )["objects"][key]
        result = {
            "actions": [],
            "conflicts": [],
            "kept": [],
            "ledger": copy.deepcopy(before),
        }
        if spec["prefab"] != current["spec"]["prefab"]:
            result["actions"].append(
                {"op": "update", "id": key, "before": current["spec"], "after": spec}
            )
        return self.backend.commit(before, result)
