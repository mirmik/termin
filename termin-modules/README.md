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
cmake -S . -B build
cmake --build build -j4
./build/termin_modules_example
```
