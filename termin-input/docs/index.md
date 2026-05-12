# termin-input

`termin-input` содержит input abstractions и bindings для событий/состояний ввода, используемых engine/editor/display слоями.

Связанные документы:

- [Module Map](../../docs/modules.md#termin-input)
- [termin-base input enums](../../termin-base/docs/index.md)

## Основные области

- Public headers в `include/`.
- C++ implementation в `src/` и `cpp/`.
- Python bindings в `cpp/bindings/`.
- Python package в `python/termin/input`.

## Публичный API

Python package: `termin.input` через пакет `termin-input`.

Базовые enum-значения ввода (`Action`, `MouseButton`, `Mods`, `Key`) экспортируются из `tcbase`.

