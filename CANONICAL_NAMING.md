# Canonical Naming

Этот документ фиксирует канонические Python namespace'ы и правила именования после выноса библиотек из `termin`.

## Цели

- У каждого логического модуля должен быть один канонический import path.
- Внутренний код репозитория должен использовать только канонические пути.
- Новый код не должен добавлять новые re-export цепочки.

## Общие правила

1. Канонический путь должен отражать логический модуль, а не историческое место файла.
2. Если модуль вынесен в отдельную библиотеку, Python API этой библиотеки становится source of truth.
3. Код внутри `termin-env` должен импортировать канонический модуль напрямую.
4. Временные хаки с ручным `__path__.append(...)` и подмешиванием repo path не считаются нормальной архитектурой и подлежат удалению.

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

## Правила по подсистемам

### Skeleton

- Канонический core API: `termin.skeleton`
- Канонический component API: `termin.skeleton_components`

### Animation

- Канонический core API: `termin.animation`
- Канонический component API: `termin.animation_components`
- `AnimationPlayer` не должен быть частью core namespace

### Physics

- Канонический core API: `termin.physics`
- Канонический component API: `termin.physics_components`
- FEM остается в `termin.physics` как отдельная ветка API

### Render components

- Канонический component API: `termin.render_components`

## Требования к внутренним импортам

Внутренний код репозитория обязан:

- импортировать `AnimationPlayer` из `termin.animation_components`
- импортировать `SkeletonController` из `termin.skeleton_components`
- импортировать render-компоненты из `termin.render_components`
- импортировать physics-компоненты из `termin.physics_components`

Внутренний код репозитория не должен:

- импортировать component classes из `termin.visualization.*`
- импортировать component classes через старые пути внутри `termin.physics`
