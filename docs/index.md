# Termin: город сложных машин

<div class="termin-kicker">Engine / editor / simulation</div>

<div class="termin-lead" markdown>
Termin — 3D-движок и нативный редактор для интерактивных приложений, игр,
робототехники и физического моделирования. Внутри — сцены, рендеринг,
симуляция, Python, C++ и достаточно движущихся частей, чтобы сухая
документация стала ещё одной разновидностью производственной аварии.
</div>

Проект активно развивается и пока ориентирован на сборку из исходников. Если
вы здесь впервые, начните с [первых шагов](getting-started.md): там есть готовая
физическая сцена и маршрут создания собственного проекта. Если вы меняете сам
движок, сначала посмотрите [карту районов](districts/index.md) — она объясняет,
кто чем владеет и почему ближайший каталог не всегда является законным местом
для нового кода.

## Что здесь можно делать

### Создавать сцены

Редактор предоставляет иерархию сущностей, 3D viewport, инспектор свойств,
project browser, undo/redo и Play Mode. Сцена хранит authoring state, а
симуляция запускается отдельно и не переписывает его при остановке.

### Настраивать графику

Меши, материалы, текстуры, PBR-освещение, тени, камеры, render targets и
настраиваемые pipelines соединяются в один runtime. GLB/glTF может принести
геометрию, материалы, skeleton, animation и иерархию — после чего каждый слой
обязан остаться в границах своего владельца.

### Собирать поведение из компонентов

Entities получают данные и поведение через компоненты. В одном проекте могут
сочетаться встроенные C++ components, Python-код и project-local C++ modules.

### Запускать симуляции

Termin включает collision и rigid-body physics, а также кинематику, navmesh,
animation, FEM и QP-модели. Acceptance projects показывают как обычную игровую
физику, так и механические сценарии, после которых слово «кубик» уже звучит
слишком легкомысленно.

### Выпускать приложения

Build profiles описывают entry scene, ресурсы, runtime backend и target.
Pipeline формирует desktop products, Android/Vulkan APK и Quest/OpenXR APK.

## Районы

<div class="termin-card-grid" markdown>

<div class="termin-card termin-card--core" markdown>

### [Core: нулевой этаж](districts/core/index.md)

Значения, dispatch, inspect, Python 3.14t, nanobind и installed SDK contract.
Здесь верхние домены получают фундамент и не получают права протащить вниз
собственную мебель.

</div>

<div class="termin-card termin-card--graphics" markdown>

### [Graphics: машинное отделение](districts/graphics/index.md)

Изображения, меши, GPU, шейдеры, render core, окна, retained UI, visual scene,
nodegraph и plotting — законченная графическая closure без Engine и Editor.

</div>

<div class="termin-card" markdown>

### [Карта всего города](districts/index.md)

Core, Graphics, Physics, Engine, Editor и Platform; направление зависимостей,
SDK profiles и честный статус ещё незамкнутых границ.

</div>

</div>

## Куда идти с конкретной задачей

| Задача | Документ |
|---|---|
| Увидеть Termin в работе | [Первые шаги](getting-started.md) |
| Собрать только нижний SDK | [Core: первый спуск](districts/core/getting-started.md) |
| Запустить графический showcase | [Graphics: первый кадр](districts/graphics/getting-started.md) |
| Понять команды проекта | [Termin CLI](https://github.com/mirmik/termin/blob/master/editor/termin-app/docs/termin-cli.md) |
| Собрать полный SDK | [Система сборки](build-system.md) |
| Найти владельца пакета | [Карта районов](districts/index.md) |
| Изменять код движка | [Карта модулей](modules.md) и [smoke-проверки](smoke-checks.md) |

## Пользовательская документация

- [Первые шаги](getting-started.md) — сборка SDK, showcase, новый проект и
  первый запуск сцены.
- [Termin CLI](https://github.com/mirmik/termin/blob/master/editor/termin-app/docs/termin-cli.md)
  — `init`, `editor`, `play`, build profiles и packaged runtime.
- [Тестовые проекты](https://github.com/mirmik/termin/tree/master/test-projects)
  — editor-openable примеры для desktop, Android, Quest/OpenXR, physics,
  кинематики и FEM.

## Разработка Termin

- [Система документации](documentation-system.md) — где живут district,
  module, user и architecture documents.
- [Система сборки](build-system.md) — SDK stages, profiles и Python runtime.
- [Smoke-проверки](smoke-checks.md) — поддерживаемые проверки editor и runtime.
- [Linting и статический анализ](linting.md), [C++ Style Guide](cpp-style.md) и
  [Python Linting](python-linting.md).
- [Карта модулей](modules.md) и
  [граф зависимостей библиотек](library-dependencies.md).
- [Документация доски](taskboard-tool.md) и
  [правила ведения карточек](taskboard-guidelines.md).

## Архитектура и следы расследований

Эти материалы нужны при изменении самого двигателя. Для первого запуска их
читать не требуется; для архитектурного refactor — требуется раньше, чем
появится третий почти одинаковый manager.

- [Архитектурные заметки](architecture/index.md) — cross-module contracts и
  принятые решения.
- [Планы и миграции](plans/index.md) — текущие и исторические планы.
- [Architecture Council](architecture-council/index.md) — протоколы спорных
  системных границ.
- [Анализы и аудиты](https://github.com/mirmik/termin/tree/master/docs/analysis)
  — техническое состояние отдельных подсистем.
- [Каталог встроенных шейдеров](builtin-shader-catalog.md),
  [render phase semantics](render-phase-semantics.md) и
  [GPU pipeline layout](gpu-pipeline-layout.md).

!!! warning "Активная разработка"

    API, formats и отдельные workflows могут меняться без compatibility
    layer. Документация описывает текущий checkout и обязана падать вместе с
    устаревшим контрактом, а не сопровождать его ещё десять лет из вежливости.
