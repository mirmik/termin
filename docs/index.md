# Termin

Библиотека для 3D-симуляции, физики и визуализации.

## Возможности

- **Entity-Component System** — управление объектами сцены
- **Физика** — симуляция твёрдых тел, коллизии
- **Рендеринг** — OpenGL, освещение, viewport
- **Скелетная анимация** — загрузка и воспроизведение анимаций
- **NavMesh** — навигация и pathfinding
- **FEM** — метод конечных элементов для мультифизики

## Быстрый старт

```python
from termin import Scene, Entity

# Создаём сцену
scene = Scene()

# Добавляем сущность
entity = scene.create_entity("player")
entity.position = (0, 0, 0)

# Основной цикл
while scene.running:
    scene.update(dt=0.016)
    scene.render()
```

## Содержание

```{toctree}
:maxdepth: 2

getting-started
concepts
api/index
```
