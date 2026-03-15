# Legacy Import Cleanup

## Overview

Очистка import-структуры termin-env: перевод всех внутренних и
внешних потребителей на канонические пути, удаление legacy facade
modules, фиксация финального API.

## Context

- Files involved:
  - Facade modules: `termin/termin/visualization/animation/*.py`, `termin/termin/visualization/render/components/*.py`, `termin/termin/physics/rigid_body_component.py`, `termin/termin/physics/physics_world_component.py`
  - Canonical modules importing from legacy native paths: `termin/termin/animation/clip.py`, `termin/termin/animation/clip_io.py`, `termin/termin/animation_components/__init__.py`, `termin/termin/assets/animation_clip_handle.py`, `termin/termin/assets/glb_asset.py`
  - Examples: `termin/examples/loader/load_fbx.py`, `termin/examples/visual/broken/keyframe_animation.py`
  - External project: `/home/mirmik/project/chronosquad-termin` (2 файла с legacy imports)
  - Documentation: `CANONICAL_NAMING.md`
- Related patterns: все facade modules - чистые re-export обёртки
- Dependencies: native модули `_animation_native` и `_components_animation_native` живут под `termin.visualization.animation.*` и импортируются каноническими модулями

## Development Approach

- **Testing approach**: Regular (код, затем проверка)
- Каждая задача завершается полным прогоном тестов
- Внешний проект chronosquad-termin модифицируется отдельно, вне termin-env
- **CRITICAL: every task MUST include new/updated tests**
- **CRITICAL: all tests must pass before starting next task**

## Implementation Steps

### Task 1: Миграция внешнего проекта chronosquad-termin

**Files:**
- Modify: `/home/mirmik/project/chronosquad-termin/Core/controllers/animation_controller.py`
- Modify: `/home/mirmik/project/chronosquad-termin/Core/controllers/effects/blind_effect.py`

- [x] Заменить `termin.visualization.animation.player` на `termin.animation_components`
- [x] Заменить `termin.visualization.render.components.mesh_renderer` на `termin.render_components`
- [x] Просканировать весь chronosquad-termin на оставшиеся legacy imports
- [x] Просканировать `/home/mirmik/projects` на legacy imports
- [x] Запустить chronosquad-termin и убедиться что импорты работают

### Task 2: Перенаправить внутренние импорты из native-модулей

Канонические модули сейчас импортируют из
`termin.visualization.animation._animation_native` и `_components_animation_native`. Нужно понять
как эти native-модули попадают в namespace и перенаправить импорты
на путь без legacy prefix.

**Files:**
- Modify: `termin/termin/animation/clip.py`
- Modify: `termin/termin/animation/clip_io.py`
- Modify: `termin/termin/animation_components/__init__.py`
- Modify: `termin/termin/assets/animation_clip_handle.py`
- Modify: `termin/termin/assets/glb_asset.py`

- [x] Исследовать как `_animation_native` и `_components_animation_native` регистрируются в namespace (через `_dll_setup.extend_package_path` или иначе)
- [x] Определить канонический путь доступа к native-модулям (возможно через `termin.animation._animation_native`)
- [x] Обновить все внутренние импорты на канонический путь
- [x] Запустить тесты проекта

### Task 3: Перевести examples на канонические пути

**Files:**
- Modify: `termin/examples/loader/load_fbx.py`
- Modify: `termin/examples/visual/broken/keyframe_animation.py`

- [x] Заменить legacy imports в load_fbx.py
- [x] Заменить legacy imports в keyframe_animation.py
- [x] Просканировать все examples на оставшиеся legacy imports и исправить
- [x] Запустить тесты проекта

### Task 4: Удалить physics legacy facade modules

**Files:**
- Delete: `termin/termin/physics/rigid_body_component.py`
- Delete: `termin/termin/physics/physics_world_component.py`

- [x] Финально убедиться что ни один файл не импортирует эти модули (grep по всем проектам)
- [x] Удалить `rigid_body_component.py`
- [x] Удалить `physics_world_component.py`
- [x] Запустить тесты проекта

### Task 5: Удалить animation legacy facade modules

**Files:**
- Delete: `termin/termin/visualization/animation/channel.py`
- Delete: `termin/termin/visualization/animation/clip.py`
- Delete: `termin/termin/visualization/animation/clip_io.py`
- Delete: `termin/termin/visualization/animation/player.py`
- Delete: `termin/termin/visualization/animation/animation_clip_asset.py`
- Modify: `termin/termin/visualization/animation/__init__.py` (оставить минимальный compatibility entry point или удалить)

- [x] Финально просканировать все проекты на импорты из `termin.visualization.animation.*`
- [x] Удалить facade-файлы
- [x] Обновить или удалить `__init__.py` пакета
- [x] Запустить тесты проекта

### Task 6: Удалить render components legacy facade modules

**Files:**
- Delete: `termin/termin/visualization/render/components/light_component.py`
- Delete: `termin/termin/visualization/render/components/mesh_renderer.py`
- Delete: `termin/termin/visualization/render/components/line_renderer.py`
- Delete: `termin/termin/visualization/render/components/skinned_mesh_renderer.py`
- Delete: `termin/termin/visualization/render/components/skybox_renderer.py`
- Delete: `termin/termin/visualization/render/components/skeleton_controller.py`
- Modify: `termin/termin/visualization/render/components/__init__.py` (оставить минимальный entry point или удалить)

- [x] Финально просканировать все проекты на импорты из `termin.visualization.render.components.*`
- [x] Удалить facade-файлы
- [x] Обновить или удалить `__init__.py` пакета
- [x] Запустить тесты проекта

### Task 7: Обновить документацию и финальная верификация

**Files:**
- Modify: `CANONICAL_NAMING.md`

- [ ] Обновить CANONICAL_NAMING.md: убрать раздел legacy facades, зафиксировать финальную import-модель
- [ ] Финальное сканирование всех проектов на любые оставшиеся legacy import paths
- [ ] Запустить полный набор тестов
- [ ] Удалить `LEGACY_IMPORT_CLEANUP_PLAN.md` из корня репозитория
