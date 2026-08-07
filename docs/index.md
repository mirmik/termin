# Termin

Termin — 3D-движок и нативный редактор для интерактивных приложений, игр,
робототехники и физического моделирования. Он объединяет визуальное
редактирование сцен, компонентную модель, рендеринг, симуляцию и сборку
приложений для нескольких платформ.

Termin активно развивается и пока ориентирован на сборку из исходников. Если
вы открыли документацию впервые, начните с [первых шагов](getting-started.md):
там есть готовая физическая сцена и маршрут создания собственного проекта.

## Что можно делать в Termin

### Создавать сцены

Редактор предоставляет иерархию сущностей, 3D viewport, инспектор свойств,
project browser, undo/redo и Play Mode. Сцена хранит авторское состояние, а
симуляция запускается отдельно и не перезаписывает его при остановке.

### Настраивать графику

В проекте доступны меши, материалы, текстуры, PBR-освещение, тени, камеры,
render targets и настраиваемые pipelines. GLB/glTF может приносить сразу
геометрию, материалы, skeleton, анимации и иерархию сцены.

### Собирать поведение из компонентов

Сущности получают данные и поведение через компоненты. В одном проекте могут
сочетаться встроенные C++-компоненты, Python-код и project-local C++-модули.

### Запускать симуляции

Termin включает коллизии и rigid-body physics, а также подсистемы кинематики,
навигации, анимации, FEM и QP-моделей. Готовые acceptance-проекты показывают
как обычную игровую физику, так и специализированные механические сценарии.

### Выпускать приложения

Build profiles описывают entry scene, ресурсы, runtime backend и целевую
платформу. Текущий pipeline умеет формировать desktop bundles, Android/Vulkan
APK и Quest/OpenXR APK.

## Начните отсюда

| Задача | Документ |
|---|---|
| Увидеть Termin в работе | [Первые шаги](getting-started.md) |
| Разобраться с командами проекта | [Termin CLI](https://github.com/mirmik/termin/blob/master/termin-app/docs/termin-cli.md) |
| Собрать SDK | [Система сборки](build-system.md) |
| Посмотреть готовые проекты | [Test projects](https://github.com/mirmik/termin/tree/master/test-projects) |
| Понять устройство репозитория | [Карта модулей](modules.md) |
| Начать разработку движка | [Сборка и smoke-проверки](smoke-checks.md) |

## Пользовательская документация

- [Первые шаги](getting-started.md) — сборка SDK, showcase, новый проект и
  первый запуск сцены.
- [Termin CLI](https://github.com/mirmik/termin/blob/master/termin-app/docs/termin-cli.md) — `init`, `editor`, `play`, build profiles и packaged runtime.
- [Тестовые проекты](https://github.com/mirmik/termin/tree/master/test-projects) —
  editor-openable примеры для desktop, Android, Quest/OpenXR, physics,
  кинематики и FEM.

## Разработка Termin

- [Система документации](documentation-system.md) — где живут пользовательские,
  модульные и архитектурные документы.
- [Система сборки](build-system.md) — SDK stages, build profiles и Python
  runtime.
- [Smoke-проверки](smoke-checks.md) — поддерживаемые проверки редактора и
  runtime.
- [Linting и статический анализ](linting.md) — общий quality workflow.
- [C++ Style Guide](cpp-style.md) и [Python Linting](python-linting.md).
- [Карта модулей](modules.md) и
  [граф зависимостей библиотек](library-dependencies.md).
- [Документация доски](taskboard-tool.md) и
  [правила ведения карточек](taskboard-guidelines.md).

## Архитектура и инженерные материалы

Эти документы нужны при изменении самого движка; для первого знакомства с
Termin читать их не требуется.

- [Архитектурные заметки](architecture/index.md) — текущие cross-module
  контракты и принятые решения.
- [Планы и миграции](plans/index.md) — рабочие и исторические планы изменений.
- [Architecture Council](architecture-council/index.md) — разбор спорных
  системных границ.
- [Анализы и аудиты](https://github.com/mirmik/termin/tree/master/docs/analysis) —
  исследования технического состояния отдельных подсистем.
- [Каталог встроенных шейдеров](builtin-shader-catalog.md),
  [render phase semantics](render-phase-semantics.md) и
  [GPU pipeline layout](gpu-pipeline-layout.md).
