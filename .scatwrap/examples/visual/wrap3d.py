<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>examples/visual/wrap3d.py</title>
</head>
<body>
<pre><code>
&quot;&quot;&quot;Minimal demo that renders a cube and allows orbiting camera controls.&quot;&quot;&quot;

from __future__ import annotations

import numpy as np

from termin.geombase.pose3 import Pose3
from termin.mesh.mesh import UVSphereMesh, Mesh, Mesh3
from termin.visualization import (
    Entity,
    MeshDrawable,
    Scene,
    Material,
    VisualizationWorld,
    PerspectiveCameraComponent,
    OrbitCameraController,
)
from termin.visualization.components import MeshRenderer
from termin.visualization.shader import ShaderProgram
from termin.visualization.skybox import SkyBoxEntity
from termin.visualization.materials.simple import ColorMaterial

# import convex hull
from scipy.spatial import ConvexHull

def build_scene(world: VisualizationWorld) -&gt; tuple[Scene, PerspectiveCameraComponent]:
    
    mesh = ConvexHull([
        [1, 1, 1],
        [1, 1, -1],
        [1, -1, 1],
        [1, -1, -1],
        [-1, 1, 1],
        [-1, 1, -1],
        [-1, -1, 1],
        [-1, -1, -1],


        [-2, -2, -1],
        [2, -2, -1],
        [2, 2, -1],
        [-2, 2, -1],
    ])
    mesh = Mesh3.from_convex_hull(mesh)

    drawable = MeshDrawable(mesh)

    material = ColorMaterial((0.8, 0.3, 0.3, 1.0))
    entity = Entity(pose=Pose3.identity(), name=&quot;cube&quot;)
    entity.add_component(MeshRenderer(drawable, material))
    scene = Scene()
    scene.add(entity)

    skybox = SkyBoxEntity()
    scene.add(skybox)
    world.add_scene(scene)

    camera_entity = Entity(name=&quot;camera&quot;)
    camera = PerspectiveCameraComponent()
    camera_entity.add_component(camera)
    camera_entity.add_component(OrbitCameraController())
    scene.add(camera_entity)

    return scene, camera


def main():
    world = VisualizationWorld()
    scene, camera = build_scene(world)
    window = world.create_window(title=&quot;termin cube demo&quot;)
    window.add_viewport(scene, camera)
    world.run()


if __name__ == &quot;__main__&quot;:
    main()

</code></pre>
</body>
</html>
