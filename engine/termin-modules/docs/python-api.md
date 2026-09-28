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

## Вызовы функций проектного C++-модуля

Python-зависимость должна пользоваться уже загруженной runtime-копией
библиотеки, а не открывать build artifact через `ctypes.CDLL`/`PyDLL`.
Повторный `dlopen` обходит lifecycle и может удерживать старую библиотеку
после reload (уничтожение Python `CDLL` не закрывает её OS handle).

```python
import ctypes
from termin.project_modules.runtime import get_project_modules_runtime

# В .pymodule: dependencies: [gameplay]
api = get_project_modules_runtime().bind_native_library("gameplay")
api.gameplay_count.argtypes = [ctypes.c_uint32, ctypes.c_uint32]
api.gameplay_count.restype = ctypes.c_int
count = api.gameplay_count(scene_index, scene_generation)
```

Низкоуровневый эквивалент для собственного `ModuleRuntime`:
`NativeLibrary(runtime.native_symbols("gameplay"))`, где `NativeLibrary`
импортируется из `termin_modules.native_library`.

Биндинг принадлежит одной загрузке модуля и не удерживает native handle.
Cascade reload сначала выгружает Python-зависимости, затем C++-модуль;
после загрузки новой версии Python-пакет импортируется заново и создаёт новый
биндинг. Сохранённая внешним кодом старая обёртка получает `RuntimeError` при
вызове. Автоматической перепривязки старых обёрток нет. `api.valid` позволяет
проверить актуальность; каждый вызов всё равно проверяется отдельно.

Аргументы и результат описываются ctypes-типами; сигнатуру `argtypes` надо
задать явно. Контракт предназначен для синхронных C ABI функций. Возвращаемые
указатели и callback-и с жизнью дольше вызова требуют отдельного управления
ресурсами и не защищены этим контрактом.

На время native-вызова берётся guard. При активных вызовах backend отказывает
в выгрузке с диагностикой, в том числе при free-threaded Python; после их
завершения cleanup можно повторить. Guard освобождается и при ошибке конвертации
аргументов. Native-функция не должна сама инициировать reload своего модуля.
