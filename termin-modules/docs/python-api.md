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
env.sync_live_scenes = True

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

`ModuleEnvironment.sync_live_scenes` управляет интеграцией module runtime с
живыми сценами. По умолчанию значение `True`: editor/player callbacks
деградируют module-owned компоненты в `UnknownComponent` перед unload и
восстанавливают их после load/reload. Для консольных сценариев подготовки
модулей без открытых сцен, например `termin modules warmup`, это поле следует
выключать.
