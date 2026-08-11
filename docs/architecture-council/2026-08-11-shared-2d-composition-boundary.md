# Shared 2D Composition Boundary

Дата: 2026-08-11

Статус: Accepted

## Контекст

`termin-gui-native` и `termin-visual-scene` являются двумя retained object
models с разной семантикой. Widget tree решает constraint layout, focus,
keyboard navigation, style, overlays и accessibility. Graphic-item tree решает
arbitrary affine placement, geometric hit testing, opacity, clipping и
z-order; он также должен оставаться пригодным для tcplot, WPF/C# и других hosts
без native widget toolkit.

При этом обе системы независимо накапливают transforms, переводят points и
bounds между пространствами, наследуют presentation state, обходят дерево для
paint и выполняют inverse mapping для hit testing. Реализованные `SceneView`,
widget portals и widget subtree transforms показали не только похожесть
алгоритмов, но и практическую потребность в композиции двух деревьев.

Нижние слои уже частично общие: `termin-base` предоставляет точные C/C++
affine и geometry values, а `termin-graphics` — paths, paints, canonical
`DrawList2D` и executor. Недостающая граница находится между semantic trees и
render vocabulary.

Исходный вопрос зафиксирован в Kanboard #1519.

## Решение

Считать `termin-gui-native` и `termin-visual-scene` двумя semantic frontends
одной 2D composition ecosystem, сохраняя отдельные object trees, owners,
handles и domain policies.

- `Widget` и `GraphicItem` не получают общий базовый object, общий vtable или
  общий owning tree.
- `termin-base` остаётся владельцем exact `tc_affine2f`/`Affine2f`, points,
  bounds и чистых операций compose, inverse и mapping.
- `termin-graphics` получает небольшой невладеющий 2D composition/evaluation
  слой. Он работает со значениями и scoped state, а не с Widget или
  GraphicItem: accumulated affine, effective visibility/opacity, clip state,
  point/bounds mapping и canonical draw-list transform/clip scopes.
- Каждый semantic owner сам обходит своё дерево и передаёт локальные значения
  общему evaluator. Он же сохраняет собственные ordering, invalidation,
  interaction и lifetime rules.
- Widget constraint layout остаётся в `termin-gui-native`. Layout вычисляет
  logical bounds; общая composition phase размещает уже измеренное subtree в
  presentation space. Ограниченный widget transform может оставаться
  `translation + positive uniform scale`, но на composition boundary
  представляется точным affine value.
- `termin-visual-scene` сохраняет arbitrary affine transforms и geometric
  clips. Общий backend не понижает их до возможностей widgets.
- `tgfx::DrawList2D` остаётся каноническим backend-neutral render value.
  `tc_ui_draw_list` может сохраняться как C ABI и semantic UI frontend, но его
  transform/clip handling должен lowering-иться в общую vocabulary, а не
  образовывать второй независимый executor contract.
- Взаимное встраивание выражается handle-based projections/portals. Bridge
  связывает anchor handle одного owner с root handle другого, рассчитывает
  placement, clipping, ordering и input boundary, но не переносит ownership.
  Текущий `SceneView` и его widget portals являются первым consumer и должны
  быть переведены на reusable bridge без reverse dependency из
  `termin-visual-scene` в GUI.

Целевая зависимость:

```text
tcplot / termin-gui-native / other hosts
                   |
                   v
          termin-visual-scene
                   |
                   v
      termin-graphics composition + DrawList2D
                   |
                   v
       termin-base affine and geometry values
```

`termin-gui-native` может зависеть от `termin-visual-scene`; обратная
зависимость запрещена. Reusable widget/scene bridge принадлежит GUI-facing
adapter/composition слою, а не visual-scene core.

## Обоснование

Общий universal node быстро накопил бы несовместимые обязанности. `measure` и
focus не имеют смысла для большинства geometry items, тогда как arbitrary
shear, negative scale и geometric clip не являются обещанием widget ABI.
Объединение owners также разрушило бы independent WPF/tcplot hosting и
generation-handle lifetime contracts.

Оставить только специальные bridges недостаточно: widget subtree transform
уже повторяет compose, inverse и coordinate mapping, а GUI renderer отдельно
преобразует вложенный `DrawList2D`. Следующие consumers снова размножили бы эту
механику и получили бы несовпадающие paint/input coordinates.

Stateless value-level backend сохраняет простую dependency direction. Он
устраняет дублирование математики и rendering scopes, не навязывая semantic
trees одинаковые storage, event или serialization policies.

## Рассмотренные альтернативы

### Объединить Widget и GraphicItem в одну object system

Отвергнуто. Общий base должен был бы либо содержать несвязанные UI и geometry
обязанности, либо превратиться в пустой marker, не устраняющий реальное
дублирование traversal и coordinate calculations. Он также создал бы неверную
зависимость visual-scene от widget toolkit.

### Сохранить независимые реализации и только специальные adapters

Отвергнуто как конечное состояние. `SceneView` полезен как vertical slice, но
его ручные world-bounds, camera-transform, ordering и input rules не должны
копироваться в каждый будущий host или portal type.

### Создать новый top-level generic scene/compositor module

Отвергнуто на первом этапе. Exact math и render vocabulary уже имеют
канонических владельцев. Новый package оправдан только доказанным API, который
не помещается в `termin-base`/`termin-graphics`; текущая декомпозиция такого
свидетельства не даёт.

### Сделать visual scene владельцем widgets через особый item type

Отвергнуто. Это создаёт второй ownership path, связывает portable scene с GUI
и делает destruction/hot reload/focus зависимыми от порядка teardown двух
owners. Portal хранит handles и никогда не становится owner.

## Последствия и риски

- Миграция должна быть vertical: paint, bounds, hit testing, pointer mapping и
  clipping одного consumer переводятся вместе. Paint-only migration считается
  некорректной.
- Общий evaluator не должен получить callbacks, allocation pools, revisions,
  serialization или generic node storage. Появление этих обязанностей требует
  отдельного решения.
- Widget local-transform restrictions остаются явно проверяемыми. Нельзя молча
  аппроксимировать arbitrary scene affine для portal widget.
- UI text measurement, density и accessibility font scale остаются UI
  semantics. Composition передаёт accumulated geometric scale renderer-у, но
  не выполняет widget reflow.
- Geometric path clips и axis-aligned widget clips должны иметь одну точную
  lowering policy. Упрощение path clip до AABB допустимо только как явно
  названная conservative query, не как hit-test contract.
- Переиспользуемый portal bridge обязан сохранять stale-handle safety и не
  продлевать lifetime ни одного owner.
- Временное сосуществование старого и нового traversal создаёт риск
  расхождения coordinate spaces; compatibility fallback не является целевым
  состоянием и удаляется после миграционных tests.

## Последующая работа

1. #1520 — опубликовать невладеющий composition/evaluation contract в
   `termin-graphics` поверх канонического `tc_affine2f`.
2. #1521 — перевести visual-scene paint/bounds/hit traversal на этот contract
   без изменения public item ownership и arbitrary-affine semantics.
3. #1522 и #1523 — перевести widget placement, draw lowering и pointer mapping
   на тот же contract, сохранив отдельный constraint layout и UI presentation
   metrics.
4. #1524 — выделить reusable handle-based widget/scene projection bridge из
   `SceneView` portal side table.
5. #1525 — удалить дублирующие transform/clip executor paths и пройти
   cross-tree identity, affine, clip, DPI, portal input и stale-lifetime gates.

## Ссылки

- Kanboard: umbrella #1519; implementation #1520–#1525.
- [`../architecture/2026-08-11-shared-2d-composition.md`](../architecture/2026-08-11-shared-2d-composition.md).
- [`../architecture/2026-07-27-retained-visual-scene-2d.md`](../architecture/2026-07-27-retained-visual-scene-2d.md).
- [`../architecture/2026-07-10-native-scene-view-bridge.md`](../architecture/2026-07-10-native-scene-view-bridge.md).
- [`../plans/2026-08-11-native-widget-subtree-transforms.md`](../plans/2026-08-11-native-widget-subtree-transforms.md).
