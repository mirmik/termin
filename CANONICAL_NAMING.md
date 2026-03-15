# Canonical Naming

Этот документ фиксирует канонические Python namespace'ы и правила именования после выноса библиотек из `termin`.

## Цели

- У каждого логического модуля должен быть один канонический import path.
- Внутренний код репозитория должен использовать только канонические пути.
- Legacy пути допустимы только как временные фасады для совместимости.
- Новый код не должен добавлять новые re-export цепочки.

## Общие правила

1. Канонический путь должен отражать логический модуль, а не историческое место файла.
2. Если модуль вынесен в отдельную библиотеку, Python API этой библиотеки становится source of truth.
3. `termin` может содержать фасады совместимости, но они не считаются каноническими.
4. Код внутри `termin-env` должен импортировать канонический модуль напрямую, а не через фасад.
5. Если старый путь нужен для совместимости, он должен быть тонким re-export без дополнительной логики.
6. Временные хаки с ручным `__path__.append(...)` и подмешиванием repo path не считаются нормальной архитектурой и подлежат удалению.

## Канонические Python namespace'ы

### Core libraries

- `termin.geombase`
- `termin.entity`
- `termin.mesh`
- `termin.collision`
- `termin.colliders`
- `termin.lighting`
- `termin.physics`
- `termin.skeleton`
- `termin.animation`

### Component libraries

- `termin.render_components`
- `termin.kinematic`
- `termin.physics_components`
- `termin.skeleton_components`
- `termin.animation_components`

## Legacy paths

Следующие пути считаются legacy facade paths. Они допустимы временно, но не должны использоваться новым кодом:

- `termin.visualization.render.components`
- `termin.visualization.animation`
- `termin.visualization.animation.player`
- `termin.visualization.render.components.skeleton_controller`
- `termin.physics.rigid_body_component`
- `termin.physics.physics_world_component`

## Правила по подсистемам

### Skeleton

- Канонический core API: `termin.skeleton`
- Канонический component API: `termin.skeleton_components`
- `SkeletonController` не должен жить в `termin.visualization.render.components`

### Animation

- Канонический core API: `termin.animation`
- Канонический component API: `termin.animation_components`
- `AnimationPlayer` не должен быть частью core namespace
- `termin.visualization.animation` считается legacy facade

### Physics

- Канонический core API: `termin.physics`
- Канонический component API: `termin.physics_components`
- FEM остается в `termin.physics` как отдельная ветка API
- `RigidBodyComponent` и `PhysicsWorldComponent` не должны быть частью канонического `termin.physics` component API

### Render components

- Канонический component API: `termin.render_components`
- `termin.visualization.render.components` считается legacy facade

## Требования к внутренним импортам

Внутренний код репозитория обязан:

- импортировать `AnimationPlayer` из `termin.animation_components`
- импортировать `SkeletonController` из `termin.skeleton_components`
- импортировать render-компоненты из `termin.render_components`
- импортировать physics-компоненты из `termin.physics_components`

Внутренний код репозитория не должен:

- импортировать component classes из `termin.visualization.*`
- импортировать component classes через старые пути внутри `termin.physics`
- использовать legacy фасады как промежуточный слой между библиотеками

## Политика совместимости

Legacy path можно удалить, когда выполнены все условия:

1. Внутри `termin-env` больше нет импортов этого пути.
2. Все тесты и editor/runtime сценарии проходят без него.
3. Для внешних проектов либо завершена миграция, либо принято явное решение сломать совместимость.

До этого момента legacy path должен оставаться:

- тонким
- без fallback логики
- без дополнительного поведения
- с явной пометкой, что это compatibility facade

## Текущее направление чистки

Приоритет cleanup такой:

1. Убрать ручные `__path__.append(...)` из package `__init__.py` и оставить единый механизм namespace discovery.
2. Ввести канонические пакеты `termin.animation`, `termin.animation_components`, `termin.skeleton_components`, `termin.physics_components`.
3. Перевести внутренние импорты репозитория на канонические пути.
4. Сжать legacy фасады до простых re-export модулей.
5. Удалять legacy пути только после полной внутренней миграции.
