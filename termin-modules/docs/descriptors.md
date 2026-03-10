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
