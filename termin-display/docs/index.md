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

