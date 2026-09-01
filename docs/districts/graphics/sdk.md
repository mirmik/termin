# Контракт Graphics SDK

Graphics SDK — самостоятельный установленный продукт из двух районов: Core +
Graphics. Это полная кумулятивная closure, собранная одним корневым
оркестратором и одним runtime lock, а не тонкий слой поверх случайного
`sdk-core/` на машине разработчика.

```console
task build:graphics
```

По умолчанию продукт устанавливается в `sdk-graphics/`; полный editor SDK в
`sdk/` и Core-only продукт в `sdk-core/` не перезаписываются.

## Native consumer

Передайте installed prefix через `CMAKE_PREFIX_PATH`:

```cmake
cmake_minimum_required(VERSION 3.20)
project(graphics_consumer LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)

find_package(termin_graphics CONFIG REQUIRED)

add_executable(graphics_consumer main.cpp)
target_link_libraries(graphics_consumer PRIVATE
    tgfx::termin_graphics2
)
```

```console
cmake -S . -B build \
  -DCMAKE_PREFIX_PATH=/absolute/path/to/termin/sdk-graphics
cmake --build build
```

Для scene-neutral framegraph execution добавьте:

```cmake
find_package(termin_render_core CONFIG REQUIRED)
target_link_libraries(graphics_consumer PRIVATE
    termin_render_core::termin_render_core
)
```

Выражайте реальную dependency closure отдельными packages. Не линкуйте «весь
Graphics» из страха пропустить библиотеку: страх — плохой package manager.

## Python consumer

Bundled interpreter изолирует native distributions от системного Python:

```console
./sdk-graphics/bin/termin_python -I tool.py
```

Устойчивые точки входа включают:

```python
import termin.graphics
from termin import mesh
import termin.nodegraph
from termin import plot

from termin import animation
from termin import glb
from termin import gui_native
from termin import image
from termin import skeleton
from termin import visual_scene
```

Готовые plot widgets принадлежат отдельному leaf package
`termin.plot.gui_native`. Engine mesh components живут отдельно в
`termin.mesh.components` и не входят в Graphics contract.

## Product identity

`sdk-product.json` фиксирует profile ID `graphics`. Native artifact manifest и
Python runtime manifest должны ссылаться на один `native_build_id`; wheels и
runtime packages принадлежат той же сборке.

Installed-consumer gate:

1. копирует SDK за пределы checkout;
2. очищает `PYTHONPATH`, package registries и source hints;
3. проверяет portable GLB, skeleton, animation, material parser, shader
   compiler и graphics MCP readback;
4. намеренно прячет CMake package и требует отрицательного результата;
5. собирает native consumer против installed configs;
6. запускает headless showcase без Engine и Editor.

Reference fixture находится в
[`tests/installed-graphics-consumers`](https://github.com/mirmik/termin/tree/master/tests/installed-graphics-consumers).
Это доказательство границы, а не публичный script API.

## Чего consumer не должен делать

- добавлять checkout через `PYTHONPATH`;
- искать headers в `graphics/*/include`;
- вызывать `add_subdirectory(graphics)` из внешнего проекта;
- смешивать `sdk-core`, `sdk-graphics` и `sdk` libraries;
- полагаться на system CMake package registry как fallback;
- импортировать Engine или Editor, чтобы получить графическую primitive.

Если installed SDK не содержит нужного package, сборка должна упасть ясно.
Тайный source fallback лишь откладывает падение до машины, на которой нет
вашего домашнего каталога.
