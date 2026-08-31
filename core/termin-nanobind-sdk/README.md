# termin-nanobind-sdk

Отдельный SDK-артефакт для `nanobind`, который устанавливает:

- ABI-specific shared runtime: `libnanobind.so` for CPython 3.14 or
  `libnanobind-ft.so` for CPython 3.14t
- CMake package `nanobind`
- headers и исходники `nanobind`, которые нужны `nanobind_add_module(NB_SHARED)`

Идея простая: `nanobind` собирается один раз как общий SDK-компонент, а остальные пакеты `termin-*` больше не вызывают `nanobind_build_library(...)` локально.
Установленный CMake package поддерживает только канонические `NB_SHARED`-модули
на том CPython ABI, для которого собран артефакт. ABI централизованно
применяется ко всем `nanobind_add_module(...)`. Локальные
`NB_STATIC`, `STABLE_ABI`, domain-specific runtimes и runtime другого Python
ABI отвергаются.

## Локальная сборка

Нужны CPython 3.14 нужного ABI и установленный в нём package `nanobind`.
По умолчанию выбирается `cp314t`; обычный ABI включается через
`-DTERMIN_PYTHON_ABI=cp314`.

```bash
pip install nanobind
cmake -S . -B build \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX=/opt/termin \
  -DPython_EXECUTABLE=$(which python3)
cmake --build build --parallel
sudo cmake --install build
```

После установки потребители могут использовать:

```cmake
find_package(Python 3.14 COMPONENTS Interpreter Development REQUIRED)
find_package(nanobind CONFIG REQUIRED)
nanobind_add_module(my_module NB_SHARED ...)
```

Передавать `FREE_THREADED` каждому модулю не требуется: wrapper выводит ABI из
SDK runtime target, при необходимости добавляет `NB_FREE_THREADED` и связывает
модуль с `nanobind` либо `nanobind-ft`. Обычные
C++-библиотеки, использующие nanobind API вне `NB_MODULE`, подключают тот же
профиль через:

```cmake
termin_nanobind_link_runtime(my_bridge PUBLIC)
```

Установленный CMake package сверяет выбранный потребителем Python
`major.minor`, полный SOABI и free-threaded marker с ABI SDK до создания
модуля.

## Артефакт SDK

CI публикует `sdk-nanobind.tar.gz` с layout под `/opt/termin`.
