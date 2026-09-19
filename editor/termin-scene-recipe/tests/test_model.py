"""Three-way merge compatibility tests from the original ChronoSquad prototype."""

import copy
import unittest
from termin.scene_recipe.model import normalize, plan, identity, equal

NS = "e8dc4116-b591-43a5-8aba-28d38f7584fd"
PREFAB = "64323ec8-a734-5003-bf60-6cd3d453c25c"


class MergeTests(unittest.TestCase):
    def setUp(self):
        self.recipe = normalize(
            dict(version=1, namespace=NS, objects=[dict(id="cover", prefab=PREFAB)])
        )
        self.base = self.recipe["objects"]["cover"]
        self.ledger = plan(self.recipe, dict(version=1, namespace=NS, objects={}), {})[
            "ledger"
        ]
        self.live = {
            "cover": dict(
                spec=copy.deepcopy(self.base), protected=[], replacement_blocks=[]
            )
        }

    def test_source_update_and_local_name(self):
        self.live["cover"]["spec"]["name"] = "У входа"
        self.recipe["objects"]["cover"]["position"] = [2, 0, 0]
        result = plan(self.recipe, self.ledger, self.live)
        self.assertFalse(result["conflicts"])
        self.assertEqual(result["actions"][0]["after"]["name"], "У входа")
        self.assertEqual(result["actions"][0]["after"]["position"], [2, 0, 0])
        self.assertEqual(
            result["ledger"]["objects"]["cover"]["uuid"], identity(NS, "cover")
        )

    def test_conflict_and_resolution_advances_baseline(self):
        self.live["cover"]["spec"]["position"] = [4, 0, 0]
        self.recipe["objects"]["cover"]["position"] = [2, 0, 0]
        self.assertEqual(
            plan(self.recipe, self.ledger, self.live)["conflicts"][0]["field"],
            "position",
        )
        result = plan(
            self.recipe, self.ledger, self.live, {"cover": {"position": "scene"}}
        )
        self.assertFalse(result["actions"])
        self.assertEqual(
            result["ledger"]["objects"]["cover"]["base"]["position"], [2, 0, 0]
        )
        self.assertFalse(plan(self.recipe, result["ledger"], self.live)["conflicts"])

    def test_manual_delete_tombstone(self):
        self.assertFalse(plan(self.recipe, self.ledger, {"cover": None})["actions"])
        self.recipe["objects"]["cover"]["name"] = "New name"
        self.assertTrue(plan(self.recipe, self.ledger, {"cover": None})["conflicts"])
        result = plan(
            self.recipe,
            self.ledger,
            {"cover": None},
            {"cover": {"existence": "recipe"}},
        )
        self.assertEqual(result["actions"][0]["op"], "create")

    def test_recipe_delete_or_detach(self):
        self.recipe["objects"] = {}
        self.assertEqual(
            plan(self.recipe, self.ledger, self.live)["actions"][0]["op"], "delete"
        )
        self.live["cover"]["spec"]["name"] = "Keep me"
        self.assertTrue(plan(self.recipe, self.ledger, self.live)["conflicts"])
        result = plan(
            self.recipe, self.ledger, self.live, {"cover": {"existence": "scene"}}
        )
        self.assertFalse(result["actions"])
        self.assertFalse(result["ledger"]["objects"])

    def test_protection_cannot_be_overridden(self):
        self.recipe["objects"] = {}
        self.live["cover"]["protected"] = ["Gameplay reference"]
        result = plan(
            self.recipe, self.ledger, self.live, {"cover": {"existence": "recipe"}}
        )
        self.assertEqual(result["conflicts"][0]["field"], "safety")
        self.assertFalse(result["actions"])

    def test_collision_and_stale_resolution(self):
        self.assertTrue(
            plan(self.recipe, dict(version=1, namespace=NS, objects={}), self.live)[
                "conflicts"
            ]
        )
        with self.assertRaises(ValueError):
            plan(self.recipe, self.ledger, self.live, {"cover": {"name": "scene"}})

    def test_quaternion_and_tolerance(self):
        recipe = normalize(
            dict(
                version=1,
                namespace=NS,
                objects=[dict(id="cover", prefab=PREFAB, rotation=[0, 0, 0, -2])],
            )
        )
        self.assertTrue(equal(recipe, self.recipe))
        self.live["cover"]["spec"]["position"][0] = 1e-8
        self.recipe["objects"] = {}
        self.assertFalse(plan(self.recipe, self.ledger, self.live)["conflicts"])

    def test_invalid_recipe(self):
        for change in (
            {"position": [float("nan"), 0, 0]},
            {"rotation": [0] * 4},
            {"scale": [0, 1, 1]},
            {"oops": 1},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                normalize(
                    dict(
                        version=1,
                        namespace=NS,
                        objects=[dict(id="cover", prefab=PREFAB, **change)],
                    )
                )


if __name__ == "__main__":
    unittest.main()
