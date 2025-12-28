"""Tests for Entity migration between pools/scenes."""

import unittest
import numpy as np

from termin.entity import Entity
from termin.visualization.core.scene import Scene
from termin.visualization.core.component import PythonComponent
from termin.geombase import GeneralTransform3, Vec3, Quat


class SimpleComponent(PythonComponent):
    """Simple test component that stores a value."""

    def __init__(self, value: int = 0):
        super().__init__()
        self.value = value
        self.start_called = False
        self.update_count = 0

    def start(self):
        self.start_called = True

    def update(self, dt: float):
        self.update_count += 1


class MigrationTest(unittest.TestCase):

    def test_entity_created_in_standalone_pool(self):
        """Entity() should create entity in standalone pool."""
        entity = Entity(name="test")
        self.assertTrue(entity.valid())
        self.assertEqual(entity.name, "test")

    def test_transform_created_in_standalone_pool(self):
        """GeneralTransform3() should create transform in standalone pool."""
        transform = GeneralTransform3()
        self.assertTrue(transform.valid())

    def test_transform_local_pose(self):
        """GeneralTransform3 should support setting local pose."""
        transform = GeneralTransform3()

        # Set position
        transform.set_local_position(Vec3(1.0, 2.0, 3.0))
        pos = transform.local_position()
        self.assertAlmostEqual(pos.x, 1.0)
        self.assertAlmostEqual(pos.y, 2.0)
        self.assertAlmostEqual(pos.z, 3.0)

    def test_entity_add_to_scene_migrates(self):
        """Adding entity to scene should migrate it to scene's pool."""
        entity = Entity(name="migrated")
        old_uuid = entity.uuid

        scene = Scene()
        new_entity = scene.add(entity)

        # New entity should be valid
        self.assertTrue(new_entity.valid())
        self.assertEqual(new_entity.name, "migrated")

        # Old entity reference is now invalid (generation bumped)
        # Note: entity and new_entity might point to different pools

    def test_entity_with_component_migrates(self):
        """Entity with component should migrate correctly."""
        entity = Entity(name="with_component")
        comp = SimpleComponent(value=42)
        entity.add_component(comp)

        scene = Scene()
        new_entity = scene.add(entity)

        # Entity should be valid
        self.assertTrue(new_entity.valid())

        # Component should still be attached
        self.assertEqual(len(new_entity.components), 1)

        # Component's entity reference should point to new entity
        migrated_comp = new_entity.components[0]
        self.assertTrue(migrated_comp.entity.valid())
        self.assertEqual(migrated_comp.entity.name, "with_component")

        # Component data should be preserved
        self.assertEqual(migrated_comp.value, 42)

    def test_entity_transform_after_migration(self):
        """Entity transform should work after migration."""
        entity = Entity(name="transform_test")

        # Set transform before adding to scene
        entity.transform.set_local_position(Vec3(1.0, 2.0, 3.0))

        scene = Scene()
        new_entity = scene.add(entity)

        # Transform should be preserved
        pos = new_entity.transform.local_position()
        self.assertAlmostEqual(pos.x, 1.0)
        self.assertAlmostEqual(pos.y, 2.0)
        self.assertAlmostEqual(pos.z, 3.0)

    def test_component_entity_reference_valid_after_migration(self):
        """Component should have valid entity reference after migration."""
        entity = Entity(name="ref_test")
        comp = SimpleComponent(value=100)
        entity.add_component(comp)

        scene = Scene()
        new_entity = scene.add(entity)

        # Get component from migrated entity
        migrated_comp = new_entity.get_component(SimpleComponent)
        self.assertIsNotNone(migrated_comp)

        # Component's entity reference should be valid
        self.assertTrue(migrated_comp.entity.valid())

        # Should be able to access entity's transform through component
        transform = migrated_comp.entity.transform
        self.assertTrue(transform.valid())

    def test_entity_with_children_migrates(self):
        """Entity with children should migrate all children."""
        parent = Entity(name="parent")
        child1 = Entity(name="child1")
        child2 = Entity(name="child2")

        child1.set_parent(parent)
        child2.set_parent(parent)

        scene = Scene()
        new_parent = scene.add(parent)

        # Parent should be valid
        self.assertTrue(new_parent.valid())

        # Children should be migrated too
        children = new_parent.children()
        self.assertEqual(len(children), 2)

        child_names = {c.name for c in children}
        self.assertEqual(child_names, {"child1", "child2"})

    def test_component_on_child_after_migration(self):
        """Component on child entity should work after migration."""
        parent = Entity(name="parent")
        child = Entity(name="child")
        child.set_parent(parent)

        comp = SimpleComponent(value=999)
        child.add_component(comp)

        scene = Scene()
        new_parent = scene.add(parent)

        # Find child
        children = new_parent.children()
        self.assertEqual(len(children), 1)
        new_child = children[0]

        # Component should be attached
        self.assertEqual(len(new_child.components), 1)

        # Component's entity reference should point to new child
        migrated_comp = new_child.components[0]
        self.assertTrue(migrated_comp.entity.valid())
        self.assertEqual(migrated_comp.entity.name, "child")
        self.assertEqual(migrated_comp.value, 999)

    def test_scene_update_after_migration(self):
        """Scene update should work with migrated entities."""
        entity = Entity(name="update_test")
        comp = SimpleComponent(value=0)
        entity.add_component(comp)

        scene = Scene()
        new_entity = scene.add(entity)

        # Update scene
        scene.update(0.016)

        # Component should have been updated
        migrated_comp = new_entity.get_component(SimpleComponent)
        self.assertTrue(migrated_comp.start_called)
        self.assertGreaterEqual(migrated_comp.update_count, 1)


if __name__ == "__main__":
    unittest.main()
