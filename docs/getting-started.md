# Установка и начало работы

## Требования

- Python 3.10+
- CMake 3.20+
- Компилятор C++17 (GCC, Clang, MSVC)

## Установка

### Из исходников (разработка)

```bash
git clone https://github.com/mirmik/termin.git
cd termin
pip install -e .
```

### Проверка установки

```python
import termin
print(termin.__version__)
```

## Первый пример

Создадим простую сцену с кубом:

```python
from termin import Scene
from termin.graphics import Viewport
from termin.mesh import cube

# Инициализация
scene = Scene()
viewport = Viewport(width=800, height=600)

# Создаём куб
entity = scene.create_entity("cube")
entity.mesh = cube(size=1.0)
entity.position = (0, 0, -5)

# Рендер-луп
while not viewport.should_close():
    viewport.poll_events()

    entity.rotation.y += 0.01  # Вращение

    scene.update(dt=0.016)
    viewport.render(scene)
```

## Структура проекта

```
termin/
├── termin/          # Python пакет
│   ├── __init__.py
│   ├── graphics/    # Рендеринг
│   ├── physics/     # Физика
│   └── _native/     # C++ биндинги
├── cpp/             # C++ исходники
├── core_c/          # C ядро
└── examples/        # Примеры
```

## Следующие шаги

- {doc}`concepts` — основные концепции библиотеки
- {doc}`api/index` — справочник API
