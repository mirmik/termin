"""Test basic Entity component iteration."""

print("1. Importing termin.entity...")
from termin.entity import Entity, Component

print("2. Creating entity...")
entity = Entity(name="TestEntity")
print(f"   entity.name = {entity.name}")

print("3. Checking component_count on fresh entity...")
count = len(entity.components)
print(f"   component count = {count}")

print("4. Calling get_component on fresh entity...")
result = entity.get_component(Component)
print(f"   result = {result}")

print("5. Test PASSED!")
