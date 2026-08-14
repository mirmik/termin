# termin-modules

Minimal C++ runtime for project module loading.

Current state:
- `ModuleRuntime` with discovery, dependency ordering, load/unload/reload
- descriptor parsing via `nos::trent` from `termin-base`
- working `CppModuleBackend`
- working `PythonModuleBackend` via Python C API
- runnable example in `examples/basic`

Build and run:

```bash
cmake -S . -B build -DCMAKE_PREFIX_PATH=/opt/termin
cmake --build build -j4
./build/termin_modules_example
```

Install as part of the monorepo:

```bash
./build-and-install.sh
```

Python package build:

```bash
CMAKE_PREFIX_PATH=/opt/termin pip install --no-build-isolation ./termin-modules
```

Notes:
- `termin-modules` depends on installed `termin-base`
- Python bindings require `nanobind` from `termin-nanobind-sdk`
- C++-only configure is supported via `-DTERMIN_MODULES_BUILD_PYTHON=OFF`
