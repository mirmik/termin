"""
Тесты сериализации/десериализации.
От малого к большому: MaterialPhase -> Material -> MeshDrawable -> Entity -> Scene -> ResourceManager
"""

import json
import numpy as np
import pytest


# ============== MaterialPhase ==============

def test_material_phase_serialize_deserialize():
    """MaterialPhase должен сериализоваться и десериализоваться."""
    from termin.visualization.core.material import MaterialPhase
    from termin.visualization.render.shader import ShaderProgram
    from termin.visualization.render.renderpass import RenderState

    shader = ShaderProgram(
        vertex_source="void main() { gl_Position = vec4(0); }",
        fragment_source="void main() { gl_FragColor = vec4(1); }",
    )
    phase = MaterialPhase(
        shader_programm=shader,
        phase_mark="forward",
        priority=10,
        color=np.array([1.0, 0.5, 0.25, 1.0], dtype=np.float32),
    )
    phase.uniforms["test_float"] = 1.5
    phase.uniforms["test_vec"] = np.array([1.0, 2.0, 3.0], dtype=np.float32)

    data = phase.serialize()

    assert data["phase_mark"] == "forward"
    assert data["priority"] == 10
    assert data["color"] == [1.0, 0.5, 0.25, 1.0]
    assert data["uniforms"]["test_float"] == 1.5
    assert data["uniforms"]["test_vec"] == [1.0, 2.0, 3.0]
    assert "vertex" in data["shader"]
    assert "fragment" in data["shader"]

    # Десериализация
    restored = MaterialPhase.deserialize(data)
    assert restored.phase_mark == "forward"
    assert restored.priority == 10
    assert np.allclose(restored.color, [1.0, 0.5, 0.25, 1.0])


def test_material_phase_json_serializable():
    """MaterialPhase.serialize() должен быть JSON-сериализуемым."""
    from termin.visualization.core.material import MaterialPhase
    from termin.visualization.render.shader import ShaderProgram

    shader = ShaderProgram(
        vertex_source="void main() {}",
        fragment_source="void main() {}",
    )
    phase = MaterialPhase(shader_programm=shader, color=np.array([1, 0, 0, 1], dtype=np.float32))

    data = phase.serialize()

    # Конвертер numpy типов
    def numpy_encoder(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    # Не должно бросать исключение
    json_str = json.dumps(data, default=numpy_encoder)
    assert len(json_str) > 0


# ============== Material ==============

def test_material_serialize_inline():
    """Material без source_path сериализуется inline."""
    from termin.visualization.core.material import Material

    mat = Material(color=np.array([0.5, 0.5, 0.5, 1.0], dtype=np.float32))
    mat.name = "test_material"

    data = mat.serialize()

    assert data["type"] == "inline"
    assert data["name"] == "test_material"
    assert "phases" in data
    assert len(data["phases"]) > 0


def test_material_serialize_file_reference():
    """Material с source_path сериализуется как ссылка на файл."""
    from termin.visualization.core.material import Material

    mat = Material(color=np.array([1, 0, 0, 1], dtype=np.float32))
    mat.name = "file_material"
    mat.source_path = "/path/to/material.shader"

    data = mat.serialize()

    assert data["type"] == "file"
    assert data["source_path"] == "/path/to/material.shader"
    assert data["name"] == "file_material"


def test_material_deserialize_inline():
    """Material десериализуется из inline данных."""
    from termin.visualization.core.material import Material

    mat = Material(color=np.array([0.8, 0.2, 0.1, 1.0], dtype=np.float32))
    mat.name = "original"

    data = mat.serialize()
    restored = Material.deserialize(data)

    assert restored.name == "original"
    assert len(restored.phases) == len(mat.phases)


# ============== MeshDrawable ==============

def test_mesh_drawable_serialize_inline():
    """MeshDrawable без source_id сериализуется inline."""
    from termin.visualization.core.mesh import MeshDrawable
    from termin.mesh.mesh import Mesh3

    vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
    triangles = np.array([[0, 1, 2]], dtype=np.int32)
    mesh = Mesh3(vertices=vertices, triangles=triangles)

    drawable = MeshDrawable(mesh, name="test_mesh")

    data = drawable.serialize()

    assert data["type"] == "inline"
    assert len(data["vertices"]) == 9  # 3 vertices * 3 coords
    assert len(data["triangles"]) == 3  # 1 triangle * 3 indices


def test_mesh_drawable_serialize_file_reference():
    """MeshDrawable с source_id сериализуется как ссылка."""
    from termin.visualization.core.mesh import MeshDrawable
    from termin.mesh.mesh import Mesh3

    mesh = Mesh3(vertices=np.array([[0, 0, 0]], dtype=np.float32), triangles=np.array([], dtype=np.int32).reshape(0, 3))
    drawable = MeshDrawable(mesh, source_id="/path/to/mesh.obj", name="file_mesh")

    data = drawable.serialize()

    assert data["type"] == "file"
    assert data["source_id"] == "/path/to/mesh.obj"


def test_mesh_drawable_deserialize_inline():
    """MeshDrawable десериализуется из inline данных."""
    from termin.visualization.core.mesh import MeshDrawable
    from termin.mesh.mesh import Mesh3

    vertices = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32)
    triangles = np.array([[0, 1, 2]], dtype=np.int32)
    mesh = Mesh3(vertices=vertices, triangles=triangles)
    drawable = MeshDrawable(mesh, name="original")

    data = drawable.serialize()
    restored = MeshDrawable.deserialize(data)

    assert restored is not None
    assert restored._mesh.vertices.shape == (3, 3)
    assert restored._mesh.triangles.shape == (1, 3)


# ============== Entity ==============

def test_entity_serialize_basic():
    """Entity сериализуется с базовыми полями."""
    from termin.visualization.core.entity import Entity
    from termin.geombase.pose3 import Pose3

    ent = Entity(
        pose=Pose3(lin=np.array([1, 2, 3]), ang=np.array([0, 0, 0, 1])),
        name="test_entity",
        scale=2.0,
        priority=5,
    )

    data = ent.serialize()

    assert data["name"] == "test_entity"
    assert data["priority"] == 5
    assert data["pose"]["position"] == [1, 2, 3]
    assert data["pose"]["rotation"] == [0, 0, 0, 1]


def test_entity_non_serializable():
    """Entity с serializable=False не сериализуется."""
    from termin.visualization.core.entity import Entity
    from termin.geombase.pose3 import Pose3

    ent = Entity(
        pose=Pose3.identity(),
        name="editor_entity",
        serializable=False,
    )

    data = ent.serialize()
    assert data is None


def test_scene_excludes_non_serializable_entities():
    """Scene не включает non-serializable Entity в сериализацию."""
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.entity import Entity
    from termin.geombase.pose3 import Pose3

    scene = Scene()
    normal_ent = Entity(pose=Pose3.identity(), name="normal")
    editor_ent = Entity(pose=Pose3.identity(), name="editor", serializable=False)

    scene.add(normal_ent)
    scene.add(editor_ent)

    data = scene.serialize()

    assert len(data["entities"]) == 1
    assert data["entities"][0]["name"] == "normal"


def test_entity_serialize_with_children():
    """Entity сериализуется с дочерними Entity."""
    from termin.visualization.core.entity import Entity
    from termin.geombase.pose3 import Pose3

    parent = Entity(pose=Pose3.identity(), name="parent")
    child1 = Entity(pose=Pose3.identity(), name="child1")
    child2 = Entity(pose=Pose3.identity(), name="child2")

    parent.transform.add_child(child1.transform)
    parent.transform.add_child(child2.transform)

    data = parent.serialize()

    assert data["name"] == "parent"
    assert len(data["children"]) == 2
    assert data["children"][0]["name"] == "child1"
    assert data["children"][1]["name"] == "child2"


def test_entity_deserialize_with_children():
    """Entity десериализуется с дочерними Entity."""
    from termin.visualization.core.entity import Entity
    from termin.geombase.pose3 import Pose3

    parent = Entity(pose=Pose3.identity(), name="parent")
    child = Entity(pose=Pose3.identity(), name="child")
    parent.transform.add_child(child.transform)

    data = parent.serialize()
    restored = Entity.deserialize(data)

    assert restored.name == "parent"
    assert len(restored.transform.children) == 1
    assert restored.transform.children[0].entity.name == "child"


# ============== Scene ==============

def test_scene_serialize():
    """Scene сериализуется с entities."""
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.entity import Entity
    from termin.geombase.pose3 import Pose3

    scene = Scene(background_color=(0.1, 0.2, 0.3, 1.0))
    ent1 = Entity(pose=Pose3.identity(), name="entity1")
    ent2 = Entity(pose=Pose3.identity(), name="entity2")
    scene.add(ent1)
    scene.add(ent2)

    data = scene.serialize()

    assert data["background_color"] == [0.1, 0.2, 0.3, 1.0]
    assert len(data["entities"]) == 2


def test_scene_serialize_only_root_entities():
    """Scene сериализует только корневые Entity."""
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.entity import Entity
    from termin.geombase.pose3 import Pose3

    scene = Scene()
    parent = Entity(pose=Pose3.identity(), name="parent")
    child = Entity(pose=Pose3.identity(), name="child")
    parent.transform.add_child(child.transform)

    scene.add(parent)
    scene.add(child)  # Добавляем и ребёнка в список

    data = scene.serialize()

    # Должен быть только parent, child сериализуется внутри parent
    assert len(data["entities"]) == 1
    assert data["entities"][0]["name"] == "parent"


# ============== ResourceManager ==============

def test_resource_manager_serialize():
    """ResourceManager сериализует все ресурсы."""
    from termin.visualization.core.resources import ResourceManager
    from termin.visualization.core.material import Material
    from termin.visualization.core.mesh import MeshDrawable
    from termin.mesh.mesh import Mesh3

    rm = ResourceManager()

    mat = Material(color=np.array([1, 0, 0, 1], dtype=np.float32))
    rm.register_material("red", mat)

    mesh = Mesh3(
        vertices=np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32),
        triangles=np.array([[0, 1, 2]], dtype=np.int32)
    )
    drawable = MeshDrawable(mesh)
    rm.register_mesh("triangle", drawable)

    data = rm.serialize()

    assert "materials" in data
    assert "meshes" in data
    assert "red" in data["materials"]
    assert "triangle" in data["meshes"]


def test_resource_manager_deserialize():
    """ResourceManager десериализуется."""
    from termin.visualization.core.resources import ResourceManager
    from termin.visualization.core.material import Material
    from termin.visualization.core.mesh import MeshDrawable
    from termin.mesh.mesh import Mesh3

    rm = ResourceManager()

    mat = Material(color=np.array([1, 0, 0, 1], dtype=np.float32))
    mat.name = "red"
    rm.register_material("red", mat)

    mesh = Mesh3(
        vertices=np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32),
        triangles=np.array([[0, 1, 2]], dtype=np.int32)
    )
    drawable = MeshDrawable(mesh)
    rm.register_mesh("triangle", drawable)

    data = rm.serialize()
    restored = ResourceManager.deserialize(data)

    assert "red" in restored.materials
    assert "triangle" in restored.meshes


# ============== Full round-trip with JSON ==============

def test_full_world_json_roundtrip():
    """Полный цикл: создание -> сериализация -> JSON -> десериализация."""
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.entity import Entity
    from termin.visualization.core.material import Material
    from termin.visualization.core.mesh import MeshDrawable
    from termin.visualization.core.resources import ResourceManager
    from termin.mesh.mesh import Mesh3
    from termin.geombase.pose3 import Pose3

    # Конвертер numpy типов
    def numpy_encoder(obj):
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.integer):
            return int(obj)
        raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")

    # Создаём ресурсы
    rm = ResourceManager()

    mat = Material(color=np.array([0.8, 0.2, 0.1, 1.0], dtype=np.float32))
    mat.name = "test_mat"
    rm.register_material("test_mat", mat)

    mesh = Mesh3(
        vertices=np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], dtype=np.float32),
        triangles=np.array([[0, 1, 2]], dtype=np.int32)
    )
    drawable = MeshDrawable(mesh)
    rm.register_mesh("test_mesh", drawable)

    # Создаём сцену
    scene = Scene(background_color=(0.1, 0.1, 0.1, 1.0))
    parent = Entity(pose=Pose3.identity(), name="parent")
    child = Entity(
        pose=Pose3(lin=np.array([1, 2, 3]), ang=np.array([0, 0, 0, 1])),
        name="child"
    )
    parent.transform.add_child(child.transform)
    scene.add(parent)

    # Сериализуем
    data = {
        "version": "1.0",
        "resources": rm.serialize(),
        "scenes": [scene.serialize()],
    }

    # В JSON и обратно
    json_str = json.dumps(data, indent=2, default=numpy_encoder)
    loaded_data = json.loads(json_str)

    # Десериализуем
    restored_rm = ResourceManager.deserialize(loaded_data["resources"])
    assert "test_mat" in restored_rm.materials
    assert "test_mesh" in restored_rm.meshes

    scene_data = loaded_data["scenes"][0]
    assert np.allclose(scene_data["background_color"], [0.1, 0.1, 0.1, 1.0])
    assert len(scene_data["entities"]) == 1
    assert scene_data["entities"][0]["name"] == "parent"
    assert len(scene_data["entities"][0]["children"]) == 1
    assert scene_data["entities"][0]["children"][0]["name"] == "child"
