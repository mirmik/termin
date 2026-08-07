# Разработка termin-app

Эта страница описывает окружение разработчика редактора. Пользовательский
маршрут — от сборки SDK до первой собственной сцены — находится в
[корневых «Первых шагах»](https://github.com/mirmik/termin/blob/master/docs/getting-started.md).

## Соберите SDK

Редактор и его bundled Python-библиотеки входят в общий SDK. Из корня
репозитория выполните:

```bash
./build-sdk.sh
```

После сборки запускайте редактор напрямую с явным проектом:

```bash
./sdk/bin/termin_editor /path/to/Project.terminproj
```

Путь к директории проекта также допустим, если в ней находится ровно один
`.terminproj`. Launcher удобен для ручного выбора и создания проектов:

```bash
./run-termin.sh
```

## Подготовьте Python-тесты

Тестовые и lint-зависимости не входят в runtime SDK. Checkout-local окружение
и source overlay создаются отдельной командой:

```bash
./setup-sdk-python-env.sh
```

Python-исходники тестируются из checkout, а native-модули и runtime-зависимости
берутся непосредственно из SDK. После пересборки bindings копировать `.so` или
`.pyd` в исходники не нужно. Повторный setup требуется только для обновления
fingerprint overlay после изменения SDK.

Запуск Python-тестов:

```bash
./run-tests-python.sh
```

Полный тестовый контур проекта запускается через:

```bash
./run-tests.sh
```

## Связанные документы

- [Архитектура редактора](editor-architecture.md)
- [Termin CLI](termin-cli.md)
- [Project build manifest](project-build-manifest.md)
- [Editor MCP diagnostics](editor-mcp.md)
- [Корневая система сборки](https://github.com/mirmik/termin/blob/master/docs/build-system.md)
