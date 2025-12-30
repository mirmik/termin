print("Test 1: Import entity module")
from termin.visualization.core.entity import Entity
print("  OK")

print("Test 2: Import ComponentRegistry")
from termin.entity._entity_native import ComponentRegistry
reg = ComponentRegistry.instance()
print("  OK")

print("Test 3: Create MeshRenderer via registry")
mr = reg.create("MeshRenderer")
print(f"  OK: {mr}")

print("Test 4: Entity deserialize with MeshRenderer")
e = Entity.deserialize({
    "name": "test",
    "components": [
        {"type": "MeshRenderer", "data": {}}
    ]
}, None)
print(f"  OK: {e}")

print("All tests passed!")
