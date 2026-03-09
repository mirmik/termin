# termin-modules

`termin-modules` это runtime-слой для загрузки проектных модулей в `termin`.

Текущий объём:

- поиск дескрипторов `.module` и `.pymodule`
- сборка и загрузка C++ модулей
- импорт и выгрузка Python модулей
- единый `ModuleRuntime` API для C++ и Python

Основные части:

- `ModuleRuntime`: orchestration, порядок зависимостей и состояние модулей
- `CppModuleBackend`: build command, загрузка shared library и вызов `module_init`
- `PythonModuleBackend`: управление `sys.path` и импорт Python-пакетов
- `ModuleDescriptorParser`: разбор дескрипторов через `nos::trent`

Типовой сценарий:

1. Создать `ModuleRuntime`
2. Настроить `ModuleEnvironment`
3. Зарегистрировать `CppModuleBackend` и `PythonModuleBackend`
4. Вызвать `discover(project_root)`
5. Вызвать `load_all()` или `load_module(name)`
