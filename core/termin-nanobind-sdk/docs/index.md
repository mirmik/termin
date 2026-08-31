# termin-nanobind-sdk / termin-nanobind

`termin-nanobind-sdk` ships nanobind runtime helpers used by Termin Python packages.

Связанные документы:

- [README](../README.md)
- [Build system](../../../docs/build-system.md)

## Основные области

- Python package `termin_nanobind`.
- Runtime SDK discovery and shared-library preload helpers in `python/termin_nanobind/`.
- CMake package files for the selected CPython 3.14 (`cp314`) or 3.14t
  (`cp314t`) nanobind ABI.

## Публичный API

Python package:

```python
from termin_nanobind.runtime import preload_sdk_libs
```

Most Termin packages call `preload_sdk_libs(...)` from their `__init__.py` to load SDK shared libraries before importing nanobind extensions.
The logical library name `nanobind` resolves to `nanobind-ft` in a
free-threaded interpreter and to `nanobind` in a GIL-enabled interpreter.
