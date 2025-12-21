import numpy as np
from termin.visualization.core.material import Material
from termin.visualization.render.shader import ShaderProgram


import numpy as np
from termin.visualization.core.serialization import serializable
from termin.visualization.core.entity import Component

import numpy as np
from termin.visualization.core.entity import Entity, Component
from termin.geombase import Pose3, Vec3
from termin.geombase import GeneralPose3
from termin.visualization.core.scene import Scene


@serializable(fields=["x"])
class C(Component):
    def __init__(self, x=0):
        super().__init__()
        self.x = x


@serializable(fields=["value", "flag"])
class DummyComponent(Component):
    def __init__(self, value=0, flag=False):
        super().__init__()
        self.value = value
        self.flag = flag


class DummyContext:
    def load_shader(self, path):
        return ShaderProgram("vs", "fs")

    def load_texture(self, path):
        return f"texture:{path}"

    def create_material(self, shader, color):
        return Material(shader, color=color)


def test_material_serialize_deserialize():
    shader = ShaderProgram("vs", "fs")
    shader.source_path = "shaders/basic.glsl"

    m = Material(
        shader=shader,
        color=np.array([1.0, 0.5, 0.2, 1.0], np.float32),
        textures={},
        uniforms={"roughness": 0.5},
    )

    data = Material.serialize(m)
    ctx = DummyContext()
    m2 = Material.deserialize(data, ctx)

    assert (m2.color == m.color).all()
    assert m2.uniforms["roughness"] == 0.5




def test_component_roundtrip():
    c = DummyComponent(value=42, flag=True)
    data = c.serialize()
    print(data)

    c2 = DummyComponent.deserialize(data["data"], DummyContext())

    assert c2.value == 42
    assert c2.flag is True




def test_entity_serialize_deserialize():
    e = Entity(pose=GeneralPose3(scale=np.array([2.0, 2.0, 2.0])), name="test", priority=3)
    e.add_component(C(x=123))

    data = e.serialize()

    print(data)

    e2 = Entity.deserialize(data, DummyContext())

    assert e2.name == "test"
    scale = e2.transform.local_pose().scale
    assert isinstance(scale, Vec3)
    np.testing.assert_array_almost_equal(scale.tolist(), [2.0, 2.0, 2.0])
    assert e2.priority == 3
    assert len(e2.components) == 1
    assert e2.components[0].x == 123




# def test_scene_roundtrip():
#     s = Scene()
#     e = Entity(pose=Pose3.identity(), name="obj")
#     e.add_component(C(x=99))
#     s.add(e)

#     data = s.serialize()

#     s2 = Scene.deserialize(data, DummyContext(), Entity)

#     assert len(s2.entities) == 1
#     ent = s2.entities[0]
#     assert ent.name == "obj"
#     assert ent.components[0].x == 99
