# Установка и начало работы

## Требования

- Python/CMake/C++ toolchain, совместимый с корневым SDK build.
- Для разработки Python-кода используйте bundled Python из собранного SDK и
  checkout-local test environment, создаваемый `setup-sdk-python-env.sh`.

## Установка

### Первичная сборка SDK

```bash
./build-sdk.sh
./setup-sdk-python-env.sh
```

`setup-sdk-python-env.sh` ставит только test/lint-зависимости в
`build/python-envs/test` и генерирует явный source overlay. Python-исходники
берутся из checkout, а native-модули и runtime-зависимости — из SDK. После
пересборки SDK достаточно повторно запустить setup, чтобы обновить fingerprint;
переустановка Termin-пакетов не нужна.

### Ежедневная проверка Python

```bash
bash run-tests-python.sh
```

Скрипт запускает `sdk/bin/termin_python` с generated overlay и не зависит от
активного venv, `PYTHONPATH` или user site-packages.

## Редактор

Основная версия редактора — tcgui. Архитектура слоев и правила добавления
операций описаны в [editor-architecture](editor-architecture.md).

## Следующие шаги

- [Build System](https://github.com/mirmik/termin-monorepo/blob/master/docs/build-system.md) — текущий SDK workflow.
- [Documentation System](https://github.com/mirmik/termin-monorepo/blob/master/docs/documentation-system.md) — где держать разные типы документов.
- [Editor Architecture](editor-architecture.md) — структура editor-core, tcgui views и controllers.
