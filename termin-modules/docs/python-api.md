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
# Optional host-controlled root for native shadow-load sessions. By default
# termin-modules uses the system temporary directory.
env.native_shadow_root = "/path/to/runtime-cache/native-modules"

runtime.set_environment(env)
runtime.register_cpp_backend(termin_modules.CppModuleBackend())
runtime.register_python_backend(termin_modules.PythonModuleBackend())

if not runtime.discover("/path/to/project"):
    raise RuntimeError(runtime.last_error)
runtime.load_all()

# Explicitly release C++ libraries, Python imports and their search paths.
# A failed shutdown retains the records/handles and can be retried.
if not runtime.shutdown():
    raise RuntimeError(runtime.last_error)
```

Доступные типы:

- `ModuleRuntime`
- `ModuleEnvironment`
- `CppModuleBackend`
- `PythonModuleBackend`
- `ModuleKind`
- `ModuleState`
- `ModuleCleanupPhase`
- `ModuleEvent`
- `ModuleEventKind`
- `ModuleRecord`

`ModuleEnvironment.sync_live_scenes` управляет интеграцией module runtime с
живыми сценами. По умолчанию значение `True`: editor/player callbacks
деградируют module-owned компоненты в `UnknownComponent` перед unload и
восстанавливают их после load/reload. Для консольных сценариев подготовки
модулей без открытых сцен, например `termin modules warmup`, это поле следует
выключать.

Editor не выполняет build в live runtime worker thread. Для isolated artifact
phase используется CLI:

```bash
termin_python -m termin.project_modules.warmup warmup --project /path/to/project --quiet
termin_python -m termin.project_modules.warmup warmup --project /path/to/project --build-module gameplay
termin_python -m termin.project_modules.warmup warmup --project /path/to/project --clean-module gameplay
termin_python -m termin.project_modules.warmup warmup --project /path/to/project --rebuild-module gameplay
```

После успешного subprocess build editor выполняет load/reload commit через
thread-neutral runtime API. CLI process не разделяет с editor CWD, interpreter
или registries.
