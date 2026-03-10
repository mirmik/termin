# Plan: вынесение render/input-протоколов из `termin-scene`

## Цель

Убрать из core-слоя сцены специальные знания о `drawable` и `input`, заменив их на обобщённый механизм component capabilities с быстрым доступом и scene-local индексами, без деградации производительности hot path.

## Принципы

- `termin-scene` знает только про generic component capabilities.
- Конкретные capability-протоколы (`drawable`, `input`) живут вне core.
- Lookup в hot path не должен использовать строки, hash map или динамический поиск по типам.
- Итерация по capability должна оставаться O(n) по уже отфильтрованному списку.
- Добавление новых протоколов не должно требовать изменений в базовой структуре `tc_component`.

## Этап 1. Зафиксировать целевую границу модулей

- Оставить в `termin-scene`:
  - `tc_scene`, `tc_entity_pool`, `tc_component`, lifecycle,
  - generic `tc_scene_extension`,
  - generic capability registry + scene-local capability indices.
- Вынести в render-библиотеку:
  - `Drawable` и всё, что связано с draw dispatch,
  - render passes / pipelines / viewport / display,
  - render-specific scene extensions.
- Вынести в input-слой:
  - input capability protocol,
  - event routing / dispatch к input-capable компонентам.

## Этап 2. Спроектировать generic capability API

Добавить в `termin-scene` новый слой, например:

- `tc_component_capability.h`
- `tc_scene_capability_index.h`

Предусмотреть в нём:

- глобальную регистрацию capability type;
- стабильный маленький slot/id для каждой capability;
- inline-friendly API:
  - `tc_component_has_capability(...)`
  - `tc_component_get_capability(...)`
  - `tc_component_attach_capability(...)`
  - `tc_component_detach_capability(...)`
- generic scene iteration:
  - `tc_scene_foreach_with_capability(...)`

## Этап 3. Выбрать представление данных без дорогих lookup

Базовый вариант:

- в `tc_component` хранить:
  - `uint64_t capability_mask`
  - массив указателей `capability_ptrs[N]`
- capability lookup делать по slot, а не по имени.

Требования:

- проверка наличия capability — через bitmask;
- получение capability data — индексом в массиве;
- без heap-lookup на каждый draw/input dispatch.

Решение по лимитам:

- на первом этапе заложить фиксированное число inline-capabilities;
- если позже понадобится больше, добавить slow-path overflow, не ломая fast path для типовых случаев.

## Этап 4. Добавить scene-local быстрые индексы

Сцена должна хранить membership по capability slot, чтобы не фильтровать все компоненты на каждом кадре.

Варианты реализации:

- intrusive lists по capability;
- dense arrays со swap-remove;
- hybrid-модель.

Рекомендуемый стартовый вариант:

- для простоты мутаций — intrusive membership в core;
- если profiling покажет узкое место, перейти для hot capabilities на dense arrays.

Нужно обеспечить:

- O(1) add/remove при attach/detach capability;
- O(n) iteration только по релевантным компонентам;
- отсутствие повторной фильтрации по строковому типу.

## Этап 5. Обобщить type registry

Заменить специальные registry-флаги:

- `set_drawable(...)`
- `set_input_handler(...)`

на generic API вида:

- `tc_component_registry_set_capability(type_name, cap_id, enabled)`
- `tc_component_registry_has_capability(type_name, cap_id)`

Идея:

- тип компонента декларирует набор capabilities;
- экземпляр при создании или attach к entity автоматически получает соответствующие capability bindings.

## Этап 6. Вынести `drawable` в отдельный capability-модуль

Создать render-side capability, например:

- `tc_drawable_capability.h`
- `drawable_capability.cpp`

Туда перенести:

- `has_phase`
- `draw_geometry`
- `get_geometry_draws`
- `override_shader`

Новый render hot path должен работать так:

- scene получает список компонентов с capability `drawable`;
- render-pass читает их typed capability data;
- core `tc_component` больше не знает, что такое drawable.

## Этап 7. Вынести `input` в отдельный capability-модуль

Создать input-side capability, например:

- `tc_input_capability.h`
- `input_capability.cpp`

Туда перенести:

- `on_mouse_button`
- `on_mouse_move`
- `on_scroll`
- `on_key`

Event routing должен зависеть только от generic capability iteration, а не от специальных полей в `tc_component`.

## Этап 8. Сохранить совместимость через переходный слой

На время миграции добавить thin adapters:

- старые `tc_component_is_drawable` / `tc_component_is_input_handler`
- старые scene helpers `tc_scene_foreach_drawable` / `tc_scene_foreach_input_handler`

Но реализовать их уже поверх generic capabilities.

Это позволит:

- мигрировать render/input код по частям;
- не ломать Python/C++ bindings одномоментно;
- упростить поэтапное тестирование.

## Этап 9. Обновить C++/Python binding layer

Нужно мигрировать:

- `Drawable` C++ wrapper;
- `InputHandler` C++ wrapper;
- Python component registration (`is_drawable`, `is_input_handler`);
- binding helpers, которые сейчас напрямую ставят special vtable fields.

Цель:

- bindings продолжают выглядеть почти так же снаружи;
- внутри используют новый capability attachment API.

## Этап 10. Профилирование и проверка инвариантов

После миграции проверить:

- стоимость draw-call collection;
- стоимость input dispatch;
- стоимость add/remove component;
- отсутствие лишних allocations в кадре.

Минимальный набор инвариантов:

- attach/detach capability корректно обновляет scene indices;
- destroyed component удаляется из всех capability memberships;
- scene migration entity не оставляет висячих membership links;
- hot iteration не использует строки и hash lookup.

## Порядок внедрения

1. Ввести generic capability registry и slot model.
2. Добавить scene-local capability indices.
3. Перевести registry type flags на generic capabilities.
4. Перенести `input` на capabilities.
5. Перенести `drawable` на capabilities.
6. Оставить compatibility wrappers.
7. Выпилить специальные поля из `tc_component` после полной миграции.

## Риски

- Раздувание `tc_component`, если сделать слишком общий storage.
- Сложность корректного remove/move lifecycle для membership links.
- Скрытая зависимость Python/C++ bindings от старых специальных полей.
- Риск двойной поддержки во время переходного периода.

## Критерий успеха

Система считается успешно переработанной, если:

- `termin-scene` больше не знает о `drawable` и `input` как о специальных протоколах;
- новые capability-протоколы можно добавлять без изменения `tc_component` API;
- render/input hot path работает через slot-based dispatch;
- производительность draw/input iteration не хуже текущей архитектуры на типовом кадре.
