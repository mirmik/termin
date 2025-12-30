from termin._native.inspect import InspectRegistry
from termin._native.render import MeshRenderer

reg = InspectRegistry.instance()

print("Type parents:")
for name in ["MeshRenderer", "SkinnedMeshRenderer", "SkeletonController", "CXXRotatorComponent"]:
    parent = reg.get_type_parent(name)
    print(f"  {name} -> {parent!r}")

print("\nMeshRenderer fields:")
for f in reg.all_fields("MeshRenderer"):
    print(f"  {f.path}: {f.kind}")

print("\nComponent fields:")
for f in reg.all_fields("Component"):
    print(f"  {f.path}: {f.kind}")

# Check actual type name
mr = MeshRenderer()
print(f"\ntype(mr).__name__ = {type(mr).__name__!r}")
print(f"type(mr).__module__ = {type(mr).__module__!r}")

# Try to get enabled
print("\nTrying registry.get(mr, 'enabled'):")
try:
    val = reg.get(mr, "enabled")
    print(f"  Success: {val}")
except Exception as e:
    print(f"  Error: {e}")
