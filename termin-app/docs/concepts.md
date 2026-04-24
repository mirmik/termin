# Основные концепции

## Entity-Component System

Termin использует ECS для организации объектов сцены.

### Entity (Сущность)

Сущность — это просто идентификатор. Сама по себе она ничего не делает, но к ней можно прикреплять компоненты.

```python
entity = scene.create_entity("player")
entity_id = entity.id  # Уникальный идентификатор
```

### Component (Компонент)

Компоненты хранят данные. Примеры:

| Компонент | Описание |
|-----------|----------|
| `Transform` | Позиция, вращение, масштаб |
| `Mesh` | 3D-геометрия |
| `RigidBody` | Физическое тело |
| `Collider` | Форма для коллизий |

```python
# Добавление компонентов
entity.add_component(Transform(position=(0, 1, 0)))
entity.add_component(RigidBody(mass=1.0))
```

## Pose3 и Screw

Для представления положения и движения в 3D используются специальные классы.

### Pose3

Положение + ориентация в пространстве:

```python
from termin.geombase import Pose3

pose = Pose3(
    position=(1, 2, 3),
    rotation=(0, 0, 0, 1)  # Кватернион (x, y, z, w)
)

# Композиция трансформаций
result = pose1 * pose2
```

### Screw (Винт)

Представление скорости или силы как винта (линейная + угловая часть):

```python
from termin.geombase import Screw3

velocity = Screw3(
    linear=(1, 0, 0),   # Линейная скорость
    angular=(0, 0, 1)   # Угловая скорость
)
```

## Сцена и обновление

```python
scene = Scene()

# Добавляем системы
scene.add_system(PhysicsSystem(gravity=(0, -9.8, 0)))
scene.add_system(RenderSystem())

# Игровой цикл
dt = 1 / 60
while running:
    scene.update(dt)  # Обновляет все системы
```
