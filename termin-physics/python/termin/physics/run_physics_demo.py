"""Physics scene builder used by editor/runtime demos."""

import numpy as np

from termin.geombase import Pose3
from termin.geombase import GeneralPose3
from termin.mesh.mesh import CubeMesh
from termin.scene import Entity
from termin.materials import TcMaterial as Material
from termin.voxels.voxel_mesh import create_voxel_mesh
from termin.visualization.core.scene import create_scene
from termin.render_components import LightComponent, MeshRenderer
from termin.lighting import LightType, LightShadowParams

from termin.physics_components import RigidBodyComponent, PhysicsWorldComponent


def build_physics_scene(world):
    """Build a scene with physics objects."""
    scene = create_scene(name="physics_demo")

    # Materials
    red_material = Material(color=np.array([0.8, 0.3, 0.3, 1.0], dtype=np.float32))
    blue_material = Material(color=np.array([0.3, 0.3, 0.8, 1.0], dtype=np.float32))
    green_material = Material(color=np.array([0.3, 0.8, 0.3, 1.0], dtype=np.float32))
    yellow_material = Material(color=np.array([0.8, 0.8, 0.3, 1.0], dtype=np.float32))
    gray_material = Material(color=np.array([0.5, 0.5, 0.5, 1.0], dtype=np.float32))

    # Meshes
    cube_mesh = CubeMesh()
    cube_tc = create_voxel_mesh(
        vertices=cube_mesh.vertices,
        triangles=cube_mesh.triangles,
        vertex_normals=cube_mesh.vertex_normals,
        name="cube",
    )

    # Ground plane (visual only - physics uses world.ground_height)
    ground = Entity(pose=Pose3.identity(), name="ground")
    ground.add_component(MeshRenderer(cube_tc, gray_material))
    ground.transform.relocate(GeneralPose3(
        lin=np.array([0, 0, -0.05]),
        scale=np.array([10.0, 10.0, 0.1])
    ))
    scene.add(ground)

    # Falling cube 1
    cube1 = Entity(pose=Pose3.identity(), name="cube1")
    cube1.add_component(MeshRenderer(cube_tc, red_material))
    cube1.transform.relocate(Pose3.identity().with_translation(np.array([0.0, 0.0, 3.0])))
    cube1.add_component(RigidBodyComponent(mass=1.0, is_static=False))
    scene.add(cube1)

    # Falling cube 2 (offset and tilted)
    import math
    angle = math.radians(30)
    quat = np.array([math.sin(angle/2), 0, 0, math.cos(angle/2)])
    cube2 = Entity(pose=Pose3.identity(), name="cube2")
    cube2.add_component(MeshRenderer(cube_tc, blue_material))
    cube2.transform.relocate(Pose3(ang=quat, lin=np.array([2.0, 0.0, 4.0])))
    cube2.add_component(RigidBodyComponent(mass=1.0, is_static=False))
    scene.add(cube2)

    # Falling cube 3 (higher)
    cube3 = Entity(pose=Pose3.identity(), name="cube3")
    cube3.add_component(MeshRenderer(cube_tc, green_material))
    cube3.transform.relocate(Pose3.identity().with_translation(np.array([-2.0, 0.0, 5.0])))
    cube3.add_component(RigidBodyComponent(mass=1.0, is_static=False))
    scene.add(cube3)

    # Falling cube 4 (will land on cube1)
    cube4 = Entity(pose=Pose3.identity(), name="cube4")
    cube4.add_component(MeshRenderer(cube_tc, yellow_material))
    cube4.transform.relocate(Pose3.identity().with_translation(np.array([0.0, 0.0, 6.0])))
    cube4.add_component(RigidBodyComponent(mass=1.0, is_static=False))
    scene.add(cube4)

    # Physics world manager
    physics_entity = Entity(pose=Pose3.identity(), name="physics_world")
    physics_entity.add_component(PhysicsWorldComponent(
        gravity=np.array([0, 0, -9.81]),
        iterations=10,
        restitution=0.3,
        friction=0.5,
        ground_height=0.0,
        ground_enabled=True,
    ))
    scene.add(physics_entity)

    # Light
    light_entity = Entity(pose=Pose3.identity(), name="directional_light")
    light_component = LightComponent(
        light_type=LightType.DIRECTIONAL,
        color=(1.0, 1.0, 1.0),
        intensity=1.0,
        shadows=LightShadowParams(enabled=True, map_resolution=2048),
    )
    light_entity.add_component(light_component)
    scene.add(light_entity)

    world.add_scene(scene)
    return scene


def run_physics_demo():
    from tcbase import log

    message = (
        "run_physics_demo() used the removed Qt editor. "
        "Open the tcgui editor and load a physics scene through the project workflow instead."
    )
    log.error(message)
    raise RuntimeError(message)


if __name__ == "__main__":
    run_physics_demo()
