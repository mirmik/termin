"""Pure three-way placement merge. No engine imports or scene mutations."""

import copy
import math
import uuid

FIELDS = ("name", "prefab", "position", "rotation", "scale", "role", "zone")
STATE_KEY = "scene_recipe_v1"


def equal(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(equal(a[key], b[key]) for key in a)
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)):
        return len(a) == len(b) and all(equal(x, y) for x, y in zip(a, b, strict=True))
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return math.isclose(a, b, rel_tol=1e-7, abs_tol=1e-6)
    return a == b


def rotation(values):
    values = [float(x) for x in values]
    length = math.sqrt(sum(x * x for x in values))
    if length < 1e-10:
        raise ValueError("Zero quaternion")
    result = [x / length for x in values]
    # q and -q represent the same rotation.
    if next((x for x in reversed(result) if abs(x) > 1e-10), 1) < 0:
        result = [-x for x in result]
    return result


def normalize(recipe):
    if recipe.get("version") != 1:
        raise ValueError("Unsupported recipe version")
    namespace = str(uuid.UUID(recipe["namespace"]))
    objects = {}
    for item in recipe["objects"]:
        if set(item) - set(FIELDS) - {"id"}:
            raise ValueError("Unknown recipe fields")
        key = item["id"]
        if not isinstance(key, str) or not key or key in objects:
            raise ValueError("Empty or duplicate placement ID: " + str(key))
        spec = {
            "name": item.get("name", key),
            "prefab": str(uuid.UUID(item["prefab"])),
            "position": item.get("position", [0, 0, 0]),
            "rotation": item.get("rotation", [0, 0, 0, 1]),
            "scale": item.get("scale", [1, 1, 1]),
            "role": item.get("role", ""),
            "zone": item.get("zone", ""),
        }
        for field, size in (("position", 3), ("rotation", 4), ("scale", 3)):
            values = spec[field]
            if len(values) != size or not all(
                isinstance(x, (int, float)) and math.isfinite(x) for x in values
            ):
                raise ValueError(f"Invalid {field} in {key}")
            spec[field] = list(map(float, values))
        if any(x <= 0 for x in spec["scale"]):
            raise ValueError("Placement scale must be positive")
        spec["rotation"] = rotation(spec["rotation"])
        if not all(isinstance(spec[f], str) for f in ("name", "role", "zone")):
            raise ValueError("Name/role/zone must be strings")
        objects[key] = spec
    return {"version": 1, "namespace": namespace, "objects": objects}


def identity(namespace, key):
    return str(uuid.uuid5(uuid.UUID(namespace), "placement/" + key))


def plan(recipe, ledger, live, resolutions=None):
    """live[id] = {spec, protected: [reasons], replacement_blocks: [reasons]}.

    None means a manually deleted wrapper. Conflict resolution is per ID/field;
    no partial application when conflicts remain. Keeping a removed object
    detaches it from recipe ownership.
    """
    resolutions = resolutions or {}
    recipe = copy.deepcopy(recipe)
    if ledger["version"] != 1 or ledger["namespace"] != recipe["namespace"]:
        raise ValueError("Recipe namespace does not own this scene ledger")
    result = {
        "actions": [],
        "conflicts": [],
        "kept": [],
        "ledger": copy.deepcopy(ledger),
    }
    used = set()

    def conflict(key, field, base, current, incoming):
        choice = resolutions.get(key, {}).get(field)
        if choice not in (None, "scene", "recipe"):
            raise ValueError("Resolution must be scene or recipe")
        if choice:
            used.add((key, field))
            return choice
        result["conflicts"].append(
            {
                "id": key,
                "field": field,
                "base": base,
                "scene": current,
                "recipe": incoming,
            }
        )
        return None

    for key in sorted(set(ledger["objects"]) | set(recipe["objects"])):
        entry = ledger["objects"].get(key)
        incoming = recipe["objects"].get(key)
        current = live.get(key)
        if entry is None:
            if current is not None:
                result["conflicts"].append(
                    {
                        "id": key,
                        "field": "identity",
                        "reason": "Untracked UUID already exists",
                    }
                )
                continue
            result["actions"].append({"op": "create", "id": key, "after": incoming})
            result["ledger"]["objects"][key] = {
                "uuid": identity(recipe["namespace"], key),
                "base": incoming,
                "labels": {"role": incoming["role"], "zone": incoming["zone"]},
            }
            continue
        base = entry["base"]
        if incoming is None:
            if current is not None:
                changed = not equal(current["spec"], base) or current["protected"]
                choice = (
                    conflict(key, "existence", base, current["spec"], None)
                    if changed
                    else "recipe"
                )
                if choice is None:
                    continue
                if choice == "scene":
                    result["kept"].append({"id": key, "reason": "Detached from recipe"})
                elif current["protected"]:
                    result["conflicts"].append(
                        {"id": key, "field": "safety", "reason": current["protected"]}
                    )
                    continue
                else:
                    result["actions"].append({"op": "delete", "id": key})
            del result["ledger"]["objects"][key]
            continue
        if current is None:
            choice = (
                conflict(key, "existence", base, None, incoming)
                if not equal(base, incoming)
                else "scene"
            )
            if choice is None:
                continue
            if choice == "recipe":
                result["actions"].append({"op": "create", "id": key, "after": incoming})
                result["ledger"]["objects"][key]["labels"] = {
                    f: incoming[f] for f in ("role", "zone")
                }
            else:
                result["kept"].append(
                    {"id": key, "reason": "Manual deletion preserved"}
                )
            result["ledger"]["objects"][key]["base"] = incoming
            continue
        values = copy.deepcopy(current["spec"])
        for field in FIELDS:
            old, actual, new = base[field], values[field], incoming[field]
            if equal(actual, new) or equal(new, old):
                continue
            if equal(actual, old):
                choice = "recipe"
            else:
                choice = conflict(key, field, old, actual, new)
            if choice == "recipe":
                values[field] = copy.deepcopy(new)
        if not equal(values, current["spec"]):
            if current.get("invalid"):
                result["conflicts"].append(
                    {"id": key, "field": "safety", "reason": current["invalid"]}
                )
            elif (
                values["prefab"] != current["spec"]["prefab"]
                and current["replacement_blocks"]
            ):
                result["conflicts"].append(
                    {
                        "id": key,
                        "field": "replacement",
                        "reason": current["replacement_blocks"],
                    }
                )
            else:
                result["actions"].append(
                    {
                        "op": "update",
                        "id": key,
                        "before": current["spec"],
                        "after": values,
                    }
                )
        result["ledger"]["objects"][key]["base"] = incoming
        result["ledger"]["objects"][key]["labels"] = {
            f: values[f] for f in ("role", "zone")
        }
    supplied = {(key, field) for key, fields in resolutions.items() for field in fields}
    if supplied - used:
        raise ValueError(
            "Unused/stale conflict resolutions: " + str(sorted(supplied - used))
        )
    return result
