# termin-modules

`termin-modules` это runtime-слой для загрузки проектных модулей в `termin`.

Текущий объём:

- поиск дескрипторов `.module` и `.pymodule`
- сборка и загрузка C++ модулей
- импорт и выгрузка Python модулей
- единый `ModuleRuntime` API для C++ и Python

Основные части:

- `ModuleRuntime`: orchestration, порядок зависимостей и состояние модулей
- `CppModuleBackend`: build command, проверка versioned native ABI и lifecycle shared library
- `PythonModuleBackend`: управление `sys.path` и импорт Python-пакетов
- `ModuleDescriptorParser`: разбор дескрипторов через `nos::trent`

Типовой сценарий:

1. Создать `ModuleRuntime`
2. Настроить `ModuleEnvironment`
3. Зарегистрировать `CppModuleBackend` и `PythonModuleBackend`
4. Вызвать `discover(project_root)`
5. Вызвать `load_all()` или `load_module(name)`

Проектный C++ модуль обязан экспортировать descriptor ABI v1 через
`TERMIN_NATIVE_MODULE_DESCRIPTOR_V1` из
`<termin_modules/native_module_abi.h>`. Descriptor содержит identity/version,
совместимость SDK/compiler/runtime, capabilities и обязательные fallible
`init`/`shutdown`. Helper `termin_module_native_validator --inspect` позволяет
проверить artifact и получить эти метаданные в JSON, не запуская lifecycle
модуля.

Консольный прогрев проектных модулей:

```bash
termin modules --project /path/to/project
termin modules warmup --project /path/to/project --module gameplay
```

Команда использует `termin.project_modules.ProjectModulesRuntime` из верхнего
пакета `termin-project-modules`, то есть тот же project-facing runtime policy
layer, что и редактор при открытии проекта. Для Python-модулей она создаёт/дополняет проектный `.venv`, ставит
requirements из `.pymodule` и импортирует указанные пакеты. Для C++-модулей
проходит обычный runtime load path, включая сборку stale-модулей перед
загрузкой. Live scene synchronization при этом отключена: команда не пытается
деградировать или восстанавливать компоненты в сценах через `UnknownComponent`,
потому что в консольном warmup-сценарии открытых сцен нет. Это позволяет
подготовить проект из CI или консоли без запуска редактора.

Сборка в монорепозитории:

- `./build-and-install.sh` собирает и устанавливает `termin-modules` вместе с остальными пакетами
- `./build-and-install-cpp.sh` собирает C++-only вариант с `TERMIN_MODULES_BUILD_PYTHON=OFF`
- `./build-and-install-bindings.sh` ставит Python package `termin-modules`
