# Санитарный кордон

Graphics легко превратить в свалку всего видимого. У сущности есть mesh —
тащим сущность вниз. Редактор показывает texture — тащим editor selection.
График стоит в widget — пусть plot знает GUI. Через месяц район уже владеет
всем, кроме квитанций за электричество.

Граница нужна раньше.

## Что принадлежит Graphics

Хороший кандидат:

- существует без engine scene и editor project;
- описывает visual data, GPU execution, presentation primitive или
  scene-neutral retained composition;
- принимает explicit host/target/capabilities;
- имеет installed CMake или Python contract;
- тестируется headless либо маленьким window host;
- зависит только от Core и других осмысленных Graphics packages.

## Что остаётся выше

Graphics не владеет:

- `termin-assets`, asset databases, reload policy и default asset adapters;
- `tc_scene`, ECS, entities и components;
- physics integration;
- authored engine render pipelines и lighting policy;
- project management, player и editor bootstrap;
- Android/OpenXR/Web application hosts.

## Типовые пограничные дела

### GLB

Portable parsing, encoded images, mesh/skeleton/animation data и transactional
publication принадлежат `termin-glb`. `GLBAsset`, resource plugins, Entity
instantiation и serialized-scene repair принадлежат
`editor/termin-glb-adapters` или другим верхним adapters.

### Mesh, skeleton и animation

Data structures и runtime sampling находятся в Graphics. `MeshComponent`,
`SkeletonComponent` и playback на Entity находятся в Engine component
packages. Низкий тип не должен зависеть от сцены ради удобного метода
`attach_to_entity()`.

### Tween

Easing, tween values и manager core принадлежат `termin-tween`.
`TweenManagerComponent` — Engine adapter. Новый Graphics guide использует
чистые primitives и не рекламирует compatibility re-export как архитектуру.

### Visual Scene и UI

`termin-visual-scene` — маленькое retained дерево визуальных объектов, не ECS.
`termin-gui-native` — widget/document model, не window manager и не application
loop. `termin-window` — events и presentation, не UI policy.

### Plot и nodegraph

`tcplot` остаётся toolkit-neutral; готовые widgets живут в
`tcplot-gui-native`. Nodegraph mutations проходят через `GraphController`, а
Python node/edge objects являются snapshots. UI projection не получает право
обходить native mutation contract.

## Вопросы перед переездом

1. Сможет ли код работать в headless Graphics showcase без Engine?
2. Принимает ли он device/target/context явно, или ищет process-global мир?
3. Это visual/runtime data или adapter к scene/assets/components?
4. Владелец lifetime и shutdown назван в API?
5. Решение опирается на capability или на строку backend-а?
6. Installed consumer способен проверить контракт без исходников?

Если ответы указывают вверх, оставьте код наверху. Близость к пикселю ещё не
делает объект частью Graphics — как близость к электростанции не делает
прохожего турбиной.

Нормативная граница всего города описана в
[District monorepo ADR](../../architecture/2026-08-14-district-monorepo.md).
