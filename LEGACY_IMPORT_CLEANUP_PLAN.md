# Legacy Import Cleanup Plan

Этот документ фиксирует, что именно мы чистим в import-структуре `termin-env`, зачем это нужно и в каком порядке это безопасно делать.

## Зачем это делаем

После выноса библиотек из `termin` в отдельные пакеты у нас остался слой compatibility facade modules:

- старые import paths все еще существуют
- часть из них уже не нужна внутреннему коду
- часть все еще нужна внешним проектам
- местами старые и новые namespace'ы смешиваются, что усложняет bootstrap, граф зависимостей и дальнейший рефакторинг

Цель cleanup:

1. Свести внутренние импорты к каноническим путям.
2. Оставить legacy paths только как тонкий слой совместимости.
3. Удалять legacy фасады только после миграции внешних потребителей.

## Что уже сделано

- Внутренний код `termin-env` в основном переведен на:
  - `termin.animation`
  - `termin.animation_components`
  - `termin.skeleton_components`
  - `termin.physics_components`
  - `termin.render_components`
- `termin.visualization.animation.*` уже сведен к compatibility facade modules.
- Значительная часть `termin.visualization.render.components.*` уже сводится к facade modules.
- Импортный bootstrap через `__path__.append(...)` централизован в `termin._dll_setup`.

## Текущее состояние внешних потребителей

### `/home/mirmik/project/chronosquad-termin`

Найдены живые legacy imports:

- `termin.visualization.animation.player`
- `termin.visualization.render.components.mesh_renderer`

Конкретные файлы:

- [`animation_controller.py`](/home/mirmik/project/chronosquad-termin/Core/controllers/animation_controller.py)
- [`blind_effect.py`](/home/mirmik/project/chronosquad-termin/Core/controllers/effects/blind_effect.py)

### `/home/mirmik/projects`

На момент составления этого плана legacy imports из проблемных зон не найдены.

Из реально использующих `termin` проектов заметен [`Chess`](/home/mirmik/projects/Chess), но он сидит на:

- `termin.visualization.core.*`
- `termin.visualization.ui.*`
- `termin.geombase.*`

а не на старых `animation/render components` facade paths.

## Фаза 1: Внешняя миграция

### Цель

Убрать внешних потребителей, которые блокируют удаление facade modules.

### Что делать

В `chronosquad-termin` заменить:

- `termin.visualization.animation.player` -> `termin.animation_components`
- `termin.visualization.render.components.mesh_renderer` -> `termin.render_components`

После этого заново просканировать:

- `/home/mirmik/project/chronosquad-termin`
- `/home/mirmik/projects`

### Критерий завершения

Вне `termin-env` больше нет импортов:

- `termin.visualization.animation.*`
- `termin.visualization.render.components.*`
- `termin.physics.rigid_body_component`
- `termin.physics.physics_world_component`

## Фаза 2: Зафиксировать compatibility surface

### Цель

Оставить только те legacy packages, которые реально нужны как переходный слой.

### Что делать

Проверить и сохранить как compatibility packages:

- [`termin/termin/visualization/animation/__init__.py`](/home/mirmik/project/termin-env/termin/termin/visualization/animation/__init__.py)
- [`termin/termin/visualization/render/components/__init__.py`](/home/mirmik/project/termin-env/termin/termin/visualization/render/components/__init__.py)

Убедиться, что внутри `termin-env` на них больше не висит логика, кроме re-export/facade behavior.

Обновить документацию:

- [`CANONICAL_NAMING.md`](/home/mirmik/project/termin-env/CANONICAL_NAMING.md)

### Критерий завершения

Legacy packages больше не являются source of truth ни для одной подсистемы.

## Фаза 3: Удалить одиночные legacy modules

### Цель

Убрать отдельные facade files, которые уже не нужны ни внутреннему коду, ни внешним проектам.

### Кандидаты на удаление после Фазы 1

- [`termin/termin/physics/rigid_body_component.py`](/home/mirmik/project/termin-env/termin/termin/physics/rigid_body_component.py)
- [`termin/termin/physics/physics_world_component.py`](/home/mirmik/project/termin-env/termin/termin/physics/physics_world_component.py)

### Следующие кандидаты

- [`termin/termin/visualization/animation/channel.py`](/home/mirmik/project/termin-env/termin/termin/visualization/animation/channel.py)
- [`termin/termin/visualization/animation/clip.py`](/home/mirmik/project/termin-env/termin/termin/visualization/animation/clip.py)
- [`termin/termin/visualization/animation/clip_io.py`](/home/mirmik/project/termin-env/termin/termin/visualization/animation/clip_io.py)
- [`termin/termin/visualization/animation/player.py`](/home/mirmik/project/termin-env/termin/termin/visualization/animation/player.py)
- [`termin/termin/visualization/render/components/light_component.py`](/home/mirmik/project/termin-env/termin/termin/visualization/render/components/light_component.py)
- [`termin/termin/visualization/render/components/mesh_renderer.py`](/home/mirmik/project/termin-env/termin/termin/visualization/render/components/mesh_renderer.py)
- [`termin/termin/visualization/render/components/line_renderer.py`](/home/mirmik/project/termin-env/termin/termin/visualization/render/components/line_renderer.py)
- [`termin/termin/visualization/render/components/skinned_mesh_renderer.py`](/home/mirmik/project/termin-env/termin/termin/visualization/render/components/skinned_mesh_renderer.py)
- [`termin/termin/visualization/render/components/skybox_renderer.py`](/home/mirmik/project/termin-env/termin/termin/visualization/render/components/skybox_renderer.py)
- [`termin/termin/visualization/render/components/skeleton_controller.py`](/home/mirmik/project/termin-env/termin/termin/visualization/render/components/skeleton_controller.py)

### Критерий завершения

Остались только те legacy files, которые действительно нужны как package-level compatibility entry points.

## Фаза 4: Cleanup examples и репозиторного шума

### Цель

Убрать архивный и демонстрационный шум, чтобы он не маскировал реальные зависимости.

### Что делать

- пройти `termin/examples`
- перевести примеры на канонические пути там, где это безопасно
- старые сломанные/исторические демо либо чинить отдельно, либо явно помечать как legacy

### Особое замечание

Примеры не должны быть источником архитектурных решений. Если пример держится на старом facade path, это не аргумент сохранять facade бесконечно.

## Фаза 5: Финальная консолидация API

### Цель

Зафиксировать окончательную import-модель без исторических слоев.

### Канонические поверхности

- `termin.animation`
- `termin.animation_components`
- `termin.skeleton`
- `termin.skeleton_components`
- `termin.physics`
- `termin.physics_components`
- `termin.render_components`

### Ожидаемый результат

- `termin.visualization.animation` удален или объявлен deprecated с коротким переходным окном
- `termin.visualization.render.components` удален или сведён к минимальному временному мосту
- старые physics component paths удалены

## Практический следующий шаг

Следующее действие по этому плану:

1. Исправить legacy imports в `/home/mirmik/project/chronosquad-termin`.
2. Повторно просканировать `/home/mirmik/project/chronosquad-termin` и `/home/mirmik/projects`.
3. Если внешних потребителей больше нет — переходить к удалению одиночных facade modules.
