# Карта районов

<div class="termin-kicker">Termin / устройство города</div>

<div class="termin-lead" markdown>
Termin — не куча библиотек, сваленная под одной крышей в надежде, что CMake
к утру разберётся. Это город из шести районов. У каждого есть земля, работа и
граница, после которой удобный include превращается в архитектурное
правонарушение.
</div>

`District` — namespace владения пакетами внутри одного монорепозитория. Это
не отдельный Git-репозиторий, не вложенный проект и не самостоятельная
сборочная система. Город строится одним корневым оркестратором; районы отвечают
за то, кому принадлежит код и в какую сторону ему позволено смотреть.

<div class="termin-card-grid" markdown>

<div class="termin-card termin-card--core" markdown>

### [Core: нулевой этаж](core/index.md)

Значения, геометрия, логирование, dispatch, inspect, Python ABI, MCP-примитивы
и сборочные инструменты. Ничего, чему для объяснения нужна сцена или GPU.

<span class="termin-status">guide ready</span>
<span class="termin-status">sdk-core</span>

</div>

<div class="termin-card termin-card--graphics" markdown>

### [Graphics: машинное отделение](graphics/index.md)

Изображения, меши, GPU backend-ы, шейдеры, scene-neutral render core, окна,
retained UI, visual scene, nodegraph и графики. Здесь пиксель получает приказ.

<span class="termin-status">guide ready</span>
<span class="termin-status">sdk-graphics</span>

</div>

<div class="termin-card" markdown>

### Physics

Коллизии, rigid-body и FEM-модели, QP, robotics, PGA и navmesh. Район уже
имеет физическое владение пакетами, но его dependency closure ещё не замкнут
настолько, чтобы выдавать отдельный SDK-профиль.

<span class="termin-status">ownership active</span>
<span class="termin-status">closure pending</span>

</div>

<div class="termin-card" markdown>

### Engine

Сцены, assets, prefab, компоненты, lighting, input, audio и runtime-композиция.
Engine соединяет нижние домены и платит за это знанием об их контрактах.

<span class="termin-status">full profile</span>

</div>

<div class="termin-card" markdown>

### Editor

Проекты, player, CLI, application bootstrap и сам редактор. Это верхний этаж,
где пользователь нажимает кнопку и все нижние обещания одновременно проходят
проверку на честность.

<span class="termin-status">full profile</span>

</div>

<div class="termin-card" markdown>

### Platform

Android, OpenXR и Web hosts. Platform выбирает конкретную машину и потребляет
нижние продукты; нижние районы не должны затягивать platform policy обратно в
свои подвалы.

<span class="termin-status">target builds</span>

</div>

</div>

## Направление движения

Базовая улица с односторонним движением выглядит так:

```text
Core  <-  Graphics  <-  Engine  <-  Editor
  ^                         ^
  +-------- Physics --------+

Platform hosts consume the required lower product closure.
```

- Core не зависит от других product districts.
- Graphics зависит от Core, но не от Engine, Editor или Physics.
- Physics в целевой модели зависит от Core; существующие cross-domain хвосты
  ещё мигрируют и поэтому не маскируются зелёной краской.
- Engine компонует Core, Graphics и Physics.
- Editor компонует продукт и developer workflow.
- Platform выбирает host и target, оставаясь потребителем нижних слоёв.

Это нормативное направление. Физическое размещение пакетов и профили Core /
Graphics уже проверяются; универсальная автоматическая проверка всех
межрайонных зависимостей ещё не завершена. На этой карте пунктир нарисован
пунктиром, потому что архитектурная документация не должна выдавать желаемое
за уличное освещение.

## Район, профиль и пакет — три разные вещи

| Слово | Что оно означает |
|---|---|
| Core / Graphics district | Область владения пакетами |
| `core/`, `graphics/` | Физический namespace путей в checkout |
| `core`, `graphics`, `full` | Профиль корневой сборки |
| Core SDK / Graphics SDK | Самостоятельный установленный результат профиля |
| `graphics/termin-graphics` | Один конкретный GPU-пакет внутри Graphics |
| `graphics/termin-render-core` | Scene-neutral orchestration в Graphics |
| `engine/termin-render` | Scene и component adapter над render core |

Graphics SDK кумулятивен: это Core + Graphics, собранные из одного checkout и
одним runtime lock. Он не является тонким overlay, а `graphics/` не умеет и не
должен собирать себя отдельно.

## Где лежит истина

- [District manifest](https://github.com/mirmik/termin/blob/master/build-system/districts.json)
  перечисляет владельцев пакетов.
- [District monorepo ADR](../architecture/2026-08-14-district-monorepo.md)
  фиксирует нормативную архитектуру и состояние миграции.
- [Система сборки](../build-system.md) описывает профили и артефакты.
- [Карта модулей](../modules.md) группирует код по возможностям. Это
  семантический путеводитель, а не второй реестр ownership.
- `task ownership` проверяет, что каждый пакет принадлежит ровно одному
  району.

Следующий маршрут вниз — [Core](core/index.md). Следующий маршрут к раскалённой
части машины — [Graphics](graphics/index.md).
