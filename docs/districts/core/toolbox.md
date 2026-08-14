# Инженерные службы

Core лучше понимать не как одну библиотеку, а как семь маленьких
договорённостей. Они живут в одном районе не потому, что кому-то понравилось
слово `common`, а потому, что должны одинаково работать для всех верхних
доменов и не знать ни одного из них по имени.

## termin-base: пол, стены и рулетка

`termin-base` содержит вещи, которым нельзя знать, что такое сцена или
редактор:

- C/C++ logging и bounded capture queue;
- UUID, строки, handles, pools и resource map;
- `tc_value` и Trent для value trees, JSON и YAML;
- ABI-friendly `tc_tensor` для typed strided memory;
- настройки;
- векторы, матрицы, poses, quaternions, AABB и spatial algebra;
- чистую математику orbit camera;
- низкоуровневый profiler vocabulary.

Здесь C ABI держит границу, C++ API убирает шум, а Python binding даёт тем же
значениям выйти в инструменты и тесты без второго самодельного мира.

[Паспорт termin-base](https://github.com/mirmik/termin/blob/master/core/termin-base/docs/index.md)

## termin-dispatch: очередь без скрытого правительства

Dispatcher принимает работу из разных потоков, но не создаёт собственный
поток и не назначает себя главным. Callback исполняется только при явном
`drain()` или `run_pending()`.

Producer говорит «сделай потом». Владелец приложения решает, где находится
это «потом»: начало кадра, конец транзакции, idle phase или тестовый метод.
Generation tickets не дают вчерашней отмене попасть в сегодняшнюю задачу,
занявшую тот же slot.

[Контракт termin-dispatch](https://github.com/mirmik/termin/blob/master/core/termin-dispatch/docs/index.md)

## termin-inspect: таможня типов

Inspect связывает три мира:

- C dispatcher задаёт language-neutral операции;
- C++ registries знают поля, наследование и kind handlers;
- Python bridge регистрирует Python-классы и преобразования.

Задача не в том, чтобы сделать C++ динамическим языком. Задача — дать
редактору, сериализатору и инструментам один явный способ спросить объект о
полях и значениях, не выдумывая lifetime по выражению его лица.

[Документация termin-inspect](https://github.com/mirmik/termin/blob/master/core/termin-inspect/docs/index.md)

## Python host: один интерпретатор, одна история

`termin-python-host` и `termin_python` отвечают за изолированный запуск
канонического CPython:

- конфигурацию через современный `PyConfig`;
- Python home и `sys.argv` до инициализации;
- проверку runtime ABI против headers и SOABI сборки;
- явный lifecycle для тестов и embedding processes.

Host не владеет editor state, scene state или callbacks конкретного продукта.
Приложение обязано отпустить свои Python-объекты до финализации
интерпретатора. Core предоставляет границу, но не изображает хозяина процесса.

[README Python host](https://github.com/mirmik/termin/blob/master/core/termin-python-host/README.md)

## nanobind SDK: прекращение ABI-анархии

Каждый extension мог бы собрать свою копию nanobind runtime и надеяться, что
вечером все версии совпадут. Core выбирает менее азартный путь: один
`nanobind-ft`, один CPython 3.14t ABI и CMake contract, который отвергает
несовместимого consumer-а до превращения ошибки в загадочный crash.

[Паспорт termin-nanobind-sdk](https://github.com/mirmik/termin/blob/master/core/termin-nanobind-sdk/docs/index.md)

## termin-mcp: связь без знания о мире

Core-owned MCP слой содержит транспорт, execution primitives и
SDK-scoped discovery. Он не знает, что такое сцена, asset manager, editor
selection или GPU texture. Graphics добавляет screenshot/readback adapter,
Editor — власть над своим процессом; транспорт остаётся нейтральным.

[Исходники termin-mcp](https://github.com/mirmik/termin/tree/master/core/termin-mcp)

## termin-build-tools: машина под половицами

Этим пакетом редко пользуется runtime. Он готовит pinned Python, строит wheels,
пишет manifests, проверяет hashes и ABI, собирает SDK profiles и испытывает
получившийся артефакт.

Если остальные модули — инструменты в чемодане, `termin-build-tools` — человек,
который сверяет опись, запирает чемодан и бросает его с лестницы, чтобы
убедиться, что замки настоящие.

[Паспорт termin-build-tools](https://github.com/mirmik/termin/blob/master/core/termin-build-tools/docs/index.md)
