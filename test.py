from termin.visualization.core.scene import Scene
from termin.entity import Entity

scene = Scene()
entity = Entity('TestEntity')
scene.add(entity)
print('Python entities:', len(scene.entities))
print('TcScene entity_count:', scene._tc_scene.entity_count())