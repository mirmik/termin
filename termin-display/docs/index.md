# termin-display

`termin-display` содержит platform/display integration: native windows, SDL backend window, viewport/display bindings и glue-код для презентации rendered textures.

Связанные документы:

- [Module Map](../../docs/modules.md#termin-display)
- [termin-graphics](../../termin-graphics/docs/index.md)

## Основные области

- Public headers в `include/`.
- Native/platform implementation в `src/platform/`.
- Python bindings в `bindings/`.
- Python package в `python/termin/display`.
- Examples в `examples/`.
- Tests в `tests/`.

## Публичный API

Основной Python entrypoint:

```python
from termin.display import SDLBackendWindow
```

`BackendWindow` является abstract/native base; прикладной код должен использовать concrete implementation, например `SDLBackendWindow`.

`FBOSurface` is also the typed Python boundary for embedding an offscreen
display in `termin.gui_native.Viewport3D`. Alongside `is_valid()`,
`framebuffer_size()`, `resize()` and `get_tgfx_color_tex_id()`, it exposes
`dispatch_pointer_move()`, `dispatch_pointer_button()`, `dispatch_scroll()`,
`dispatch_key()` and `dispatch_text()`. These methods route through the input
manager already attached to the render surface and return `False` for a stale
surface or missing manager. New UI code must use this contract instead of
transporting `tc_render_surface*` or `tc_input_manager*` as Python integers.
