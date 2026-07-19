# Дескрипторы

Сейчас `termin-modules` поддерживает два типа дескрипторов.

## C++ модуль

```json
{
  "name": "cpp_demo",
  "type": "cpp",
  "build": {
    "command": "cmake -S . -B build && cmake --build build",
    "output": "build/libcpp_demo.so"
  }
}
```

- `name`: идентификатор модуля в runtime
- `type`: должен быть `cpp`
- `dependencies`: необязательный список зависимостей на другие проектные модули
- `build.command`: необязательная команда сборки, выполняется в директории дескриптора
- `build.command` и `build.output` могут быть либо строкой, либо объектом с ключами `linux` / `windows`
- внутри `build.command` и `build.output` поддерживается подстановка `${name}`
- `build.output`: обязательный путь к артефакту; если путь относительный, он считается от директории дескриптора
- `ignore`: необязательный флаг, позволяющий пропустить модуль

Пример с разными артефактами для Linux и Windows:

```json
{
  "name": "chrono_core",
  "type": "cpp",
  "build": {
    "command": {
      "linux": "cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --config Release",
      "windows": "cmake -B build -DCMAKE_BUILD_TYPE=Release && cmake --build build --config Release"
    },
    "output": {
      "linux": "build/lib${name}.so",
      "windows": "build/Release/${name}.dll"
    }
  }
}
```

## Python модуль

```json
{
  "name": "python_demo",
  "type": "python",
  "dependencies": ["cpp_demo"],
  "root": ".",
  "packages": ["python_demo"]
}
```

- `name`: идентификатор модуля в runtime
- `type`: должен быть `python`
- `dependencies`: необязательный список зависимостей на другие проектные модули
- `root`: import root; если путь относительный, он считается от директории дескриптора
- `packages`: список Python-пакетов для импорта
- `requirements`: необязательный список внешних Python-зависимостей
- `ignore`: необязательный флаг, позволяющий пропустить модуль

Поле `components` в дескрипторах запрещено. Владение component type names
берётся из фактических runtime-type descriptors, опубликованных модулем.

Нативный lifecycle получает единственный канонический owner через host API и
передаёт его каждому builder явно:

```cpp
int32_t module_init(
    const termin_native_module_host_v1* host,
    termin_native_module_error*
) {
    if (!host || !host->module_id || !host->module_id[0]) return -1;
    auto component = termin::ComponentTypeDescriptorBuilder::native<MyComponent>(
        "MyComponent", host->module_id, "CxxComponent");
    return component.commit() ? 0 : -1;
}
```

Для Python backend до импорта регистрирует явные claims
`packages namespace -> module id`. `PythonComponent` и `PythonFramePass`
разрешают owner по `cls.__module__` и передают его в native descriptor API.
Здесь нет mutable current-owner scope: вложенный или упавший import не может
изменить владельца чужой регистрации. Scene migration, hot reload и cleanup
читают owner из опубликованной runtime-type записи, а не из ручного списка в
descriptor.
