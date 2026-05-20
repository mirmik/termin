# Установка и начало работы

## Требования

- Python/CMake/C++ toolchain, совместимый с корневым SDK build.
- Для разработки Python-кода используйте venv, создаваемый `setup-test-venv.sh`.

## Установка

### Первичная сборка SDK

```bash
./build-sdk.sh
./setup-test-venv.sh
```

`setup-test-venv.sh` ставит Python-пакеты в editable-режиме, поэтому изменения
в Python-исходниках видны без переустановки.

### Ежедневная проверка Python

```bash
bash run-tests-python.sh
```

Скрипт сам активирует `.venv/` и выставляет `TERMIN_SDK`.

## Редактор

Основная версия редактора — tcgui. Архитектура слоев и правила добавления
операций описаны в [editor-architecture](editor-architecture.md).

## Следующие шаги

- [Build System](../../docs/build-system.md) — текущий SDK workflow.
- [Documentation System](../../docs/documentation-system.md) — где держать разные типы документов.
- [Editor Architecture](editor-architecture.md) — структура editor-core, Qt/tcgui views и controllers.
