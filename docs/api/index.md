# API Reference

```{toctree}
:maxdepth: 2

c-api
```

## Python API

### Core

```{eval-rst}
.. py:module:: termin

.. py:class:: Scene

   Контейнер для сущностей и систем.

   .. py:method:: create_entity(name: str = "") -> Entity

      Создаёт новую сущность.

      :param name: Имя сущности (опционально)
      :return: Созданная сущность

   .. py:method:: update(dt: float) -> None

      Обновляет все системы сцены.

      :param dt: Время с прошлого кадра в секундах

.. py:class:: Entity

   Сущность в сцене.

   .. py:attribute:: id
      :type: int

      Уникальный идентификатор сущности.

   .. py:attribute:: position
      :type: tuple[float, float, float]

      Позиция в мировых координатах.

   .. py:method:: add_component(component) -> None

      Добавляет компонент к сущности.
```

### Geometry

```{eval-rst}
.. py:module:: termin.geombase

.. py:class:: Pose3

   Положение и ориентация в 3D пространстве.

   .. py:method:: __init__(position=(0,0,0), rotation=(0,0,0,1))

      :param position: Позиция (x, y, z)
      :param rotation: Кватернион (x, y, z, w)

   .. py:method:: __mul__(other: Pose3) -> Pose3

      Композиция трансформаций.
```

## C++ API

:::{note}
C++ API документация будет добавлена после настройки Doxygen + Breathe.
:::

Пока см. заголовочные файлы в `cpp/`:

- `cpp/entity/tc_entity.hpp` — Entity system
- `cpp/geombase/pose3.hpp` — Pose3
- `cpp/physics/rigid_body.hpp` — Physics
