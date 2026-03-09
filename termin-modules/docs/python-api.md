# Python API

Python-пакет `termin_modules` реэкспортирует native nanobind-модуль:

```python
import termin_modules
```

Минимальный пример:

```python
import termin_modules

runtime = termin_modules.ModuleRuntime()

env = termin_modules.ModuleEnvironment()
env.python_executable = "python3"

runtime.set_environment(env)
runtime.register_cpp_backend(termin_modules.CppModuleBackend())
runtime.register_python_backend(termin_modules.PythonModuleBackend())

runtime.discover("/path/to/project")
runtime.load_all()
```

Доступные типы:

- `ModuleRuntime`
- `ModuleEnvironment`
- `CppModuleBackend`
- `PythonModuleBackend`
- `ModuleKind`
- `ModuleState`
- `ModuleEvent`
- `ModuleEventKind`
- `ModuleRecord`
