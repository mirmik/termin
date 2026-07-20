# termin-display

`termin-display` содержит logical displays, viewport layout, display-level input
routing и backend-neutral offscreen output surfaces. Native windows и
физическая презентация принадлежат соседнему `termin-window`.

Связанные документы:

- [Module Map](../../docs/modules.md#termin-display)
- [termin-graphics](../../termin-graphics/docs/index.md)
- [Display render surface contract](../../docs/architecture/2026-07-19-display-render-surface-contract.md)
- [termin-window](../../termin-window/docs/index.md)

## Основные области

- Public headers в `include/`.
- Native/platform implementation в `src/platform/`.
- Python bindings в `bindings/`.
- Python package в `python/termin/display`.
- Examples в `examples/`.
- Tests в `tests/`.

## Публичный API

Python bindings пока повторно экспортируют window types:

```python
from termin.display import SDLBackendWindow
```

`BackendWindow` является abstract/native base; прикладной код должен использовать concrete implementation, например `SDLBackendWindow`.

Это packaging compatibility, а не ownership: C++ `BackendWindow` и
`SDLBackendWindow` уже реализованы в `termin-window`. Новая display/render
архитектура не должна возвращать их в `termin-display`.

`tc_display` эксклюзивно владеет прикреплённым `tc_render_surface`. Surface
имеет обязательные semantic `destroy` и storage deleter; успешное создание или
замена передаёт владение display, а неуспешная операция оставляет его caller.
Offscreen surface является внутренней backend-реализацией и создаётся через
`Display.offscreen(device, width, height)`. Сам `Display` предоставляет texture,
pixel extent, resize и typed pointer/wheel/key/text dispatch, поэтому отдельной
долгоживущей Python surface identity нет.
