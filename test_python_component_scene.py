"""
Test PythonComponent with Scene integration.

Tests that pure Python components:
1. Can be added to entities
2. Get registered with the scene
3. Receive start() and update() calls
"""

from termin.visualization.core.python_component import PythonComponent
from termin.visualization.core.scene import Scene
from termin.entity import Entity


class TestComponent(PythonComponent):
    """Test component that tracks lifecycle calls."""

    def __init__(self):
        super().__init__()
        self.start_called = False
        self.update_count = 0
        self.last_dt = 0.0

    def start(self):
        print(f"  {self.type_name()}.start() called")
        self.start_called = True

    def update(self, dt: float):
        self.update_count += 1
        self.last_dt = dt
        print(f"  {self.type_name()}.update({dt:.3f}) called, count={self.update_count}")


print("=== Test: PythonComponent with Scene ===\n")

# Create scene
scene = Scene()
print("1. Scene created")

# Create entity
entity = Entity(name="TestEntity")
print("2. Entity created")

# Create component
component = TestComponent()
print(f"3. TestComponent created: type_name={component.type_name()}")
print(f"   enabled={component.enabled}, is_native={component.is_native}")
print(f"   has_update={component.has_update}, has_fixed_update={component.has_fixed_update}")

# Add component to entity
entity.add_component(component)
print("4. Component added to entity")
print(f"   component.entity = {component.entity}")

# Add entity to scene
scene.add(entity)
print("5. Entity added to scene")
print(f"   scene.pending_start_count = {scene._tc_scene.pending_start_count}")
print(f"   scene.update_list_count = {scene._tc_scene.update_list_count}")

# Run first update (should call start() then update())
print("\n6. First scene.update(0.016):")
scene.update(0.016)
print(f"   start_called = {component.start_called}")
print(f"   update_count = {component.update_count}")

# Run second update
print("\n7. Second scene.update(0.016):")
scene.update(0.016)
print(f"   update_count = {component.update_count}")

# Verify
assert component.start_called, "start() should have been called"
assert component.update_count == 2, f"update() should have been called twice, got {component.update_count}"

print("\n=== Test PASSED! ===")
print("PythonComponent is fully integrated with Scene.")
