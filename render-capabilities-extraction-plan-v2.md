# Technical Plan v2: generic component capabilities для `termin-scene`

## Статус

Этот документ детализирует план миграции от встроенных специальных протоколов `drawable` / `input` к generic capability architecture с быстрым slot-based dispatch и scene-local индексами.

---

## 1. Цель изменений

Нужно уйти от текущей модели, где базовый `tc_component` содержит knowledge о двух конкретных подсистемах:

- `drawable_vtable`
- `drawable_ptr`
- `input_vtable`
- registry flags `is_drawable` / `is_input_handler`
- scene-level специальные проходы `foreach_drawable` / `foreach_input_handler`

и перейти к модели, где:

- core знает только про generic capabilities;
- конкретные протоколы объявляются и подключаются внешними подсистемами;
- в hot path нет строковых lookup и hash map;
- scene iteration идёт по уже готовым спискам нужной capability.

---

## 2. Целевой architectural split

### В `termin-scene` остаётся

- `tc_scene`
- `tc_entity_pool`
- `tc_component`
- lifecycle and scheduler
- `tc_scene_extension`
- generic component capability registry
- generic scene capability indexing

### В render/input слоях живёт

- render-side capability `drawable`
- input-side capability `input`
- typed capability vtables
- helpers / wrappers / adapters
- render/input dispatch code

### Что важно

`termin-scene` не знает доменных имён capability.
Он знает только:

- capability id
- capability slot
- capability storage on component
- capability membership in scene

---

## 3. Ограничения и требования

### Требования по производительности

- Проверка capability у компонента — O(1)
- Получение capability data — O(1)
- Итерация по capability в сцене — O(n) только по релевантным компонентам
- Без строк и hash map в draw/input hot path
- Без полного сканирования всех компонентов сцены для render/input dispatch

### Требования по миграции

- Переход должен быть поэтапным
- Старые API должны временно работать через compatibility layer
- Python/C++ bindings должны пережить миграцию без одновременного переписывания всего стека

### Ограничения по дизайну

- Не превращать `tc_component` в динамический контейнер с heap allocations на каждый access
- Не строить generic extension lookup для каждого dispatch как у scene extensions
- Не ломать текущую модель lifecycle и владения компонентами

---

## 4. Целевая data model

## 4.1 Capability registration

Ввести новый модуль, например:

- `termin-scene/include/core/tc_component_capability.h`
- `termin-scene/src/tc_component_capability.c`

Новые сущности:

- `tc_component_cap_id` — стабильный глобальный id capability type
- `tc_component_cap_slot` — компактный индекс для fast-path storage

Пример концептуального API:

- `tc_component_cap_id tc_component_capability_register(const char* debug_name)`
- `bool tc_component_capability_get_slot(tc_component_cap_id id, uint32_t* out_slot)`
- `const char* tc_component_capability_name(tc_component_cap_id id)`

### Правило

- В runtime capability получает slot один раз
- Slot остаётся стабильным до shutdown
- Fast path работает только по slot

---

## 4.2 Storage в `tc_component`

### Текущая проблема

Сейчас `tc_component` захардкожен под два специальных протокола.

### Предлагаемое поле

В `tc_component` добавить:

- `uint64_t capability_mask`
- `void* capability_ptrs[TC_COMPONENT_INLINE_CAPS]`

Опционально:

- `uint32_t capability_count`
- overflow storage для будущего расширения, но не в первой версии

### Рекомендуемая версия v1

Сделать жёстко inline-only capabilities:

- `#define TC_COMPONENT_INLINE_CAPS 16` или `32`
- capability slot обязан попадать в этот диапазон

Это даёт:

- очень простой hot path
- отсутствие дополнительных heap-lookup
- достаточный запас для ближайших протоколов

### Почему это лучше сейчас

- архитектура станет чище уже на первом этапе
- производительность будет практически как у прямых полей
- код останется простым в сопровождении

---

## 4.3 Capability instance representation

Каждая capability хранит `void*` на свои данные.

Для двух первых протоколов:

- `drawable` capability data = указатель на render-side struct/vtable bundle
- `input` capability data = указатель на input-side struct/vtable bundle

Core не интерпретирует этот pointer.

Core умеет только:

- хранить его
- возвращать его
- поддерживать membership по slot

---

## 5. Scene-local indexing

## 5.1 Зачем нужен отдельный индекс

Если ограничиться только `component->capability_mask`, то render/input будут вынуждены сканировать все компоненты сцены.
Это ломает производительность.

### Значит нужен scene-level membership cache

Сцена должна знать: какие компоненты принадлежат capability slot `S`.

---

## 5.2 Рекомендуемая структура v1

Добавить в `tc_scene` capability memberships.

Рабочий вариант v1:

- массив голов intrusive list по slot
- счётчики по slot

Например концептуально:

- `tc_component* capability_heads[TC_COMPONENT_INLINE_CAPS]`
- `size_t capability_counts[TC_COMPONENT_INLINE_CAPS]`

А в `tc_component` добавить membership-links:

- `tc_component* cap_prev[TC_COMPONENT_INLINE_CAPS]`
- `tc_component* cap_next[TC_COMPONENT_INLINE_CAPS]`

### Плюсы

- O(1) attach/remove
- простой lifecycle
- не нужен realloc
- predictable performance

### Минусы

- раздувает `tc_component`

### Почему всё же норм

Для небольшого fixed capability count это честная плата за очень быстрый hot path.

---

## 5.3 Альтернатива v2

Если позже окажется, что память слишком дорога, можно перейти на:

- dense swap-remove arrays per capability
- или hybrid: hot capabilities dense, остальные intrusive

Но это не нужно тащить в первый этап.

---

## 6. Generic API поверх capability system

Новые функции в core:

### Component-level

- `bool tc_component_has_capability(const tc_component* c, tc_component_cap_id id)`
- `void* tc_component_get_capability(const tc_component* c, tc_component_cap_id id)`
- `bool tc_component_attach_capability(tc_component* c, tc_component_cap_id id, void* cap_ptr)`
- `void tc_component_detach_capability(tc_component* c, tc_component_cap_id id)`

### Scene-level

- `void tc_scene_capability_on_component_added(tc_scene_handle scene, tc_component* c)`
- `void tc_scene_capability_on_component_removed(tc_scene_handle scene, tc_component* c)`
- `void tc_scene_foreach_with_capability(tc_scene_handle scene, tc_component_cap_id id, tc_component_iter_fn callback, void* user_data, int filter_flags)`

### Registry-level

- `void tc_component_registry_set_capability(const char* type_name, tc_component_cap_id id, bool enabled)`
- `bool tc_component_registry_has_capability(const char* type_name, tc_component_cap_id id)`

---

## 7. Lifecycle integration points

## 7.1 Add component to entity/scene

Когда компонент добавляется в entity:

1. type registry уже знает capability set компонента;
2. instance получает соответствующие capability attachments;
3. scene добавляет компонент в capability membership lists.

Нужно встроить это в существующий add/register flow, не ломая lifecycle.

## 7.2 Remove component

При remove:

1. сначала вынуть компонент из всех capability memberships сцены;
2. потом unregister/lifecycle cleanup;
3. затем detach capability data, если ownership этого требует.

## 7.3 Scene migration / entity migration

При переносе entity между сценами:

- компонент должен выйти из capability index старой сцены;
- затем войти в capability index новой сцены.

Это надо явно проверить, потому что это типичный источник висячих ссылок.

---

## 8. Ownership model capability data

Нужно заранее зафиксировать правило владения.

### Рекомендуемое правило v1

Core не владеет `capability_ptr`.
Ownership остаётся у внешней подсистемы / объекта компонента.

То есть:

- core только хранит opaque pointer;
- attach/detach capability не освобождает память автоматически;
- lifecycle capability data контролируется тем слоем, который её создал.

### Почему это хорошо

- проще миграция с текущих C++ wrappers;
- не надо делать ещё один generic destructor protocol в первой версии.

### Если понадобится позже

Можно добавить optional capability-type vtable:

- `on_component_added_to_scene`
- `on_component_removed_from_scene`
- `detach`

Но это лучше не вводить в первой итерации.

---

## 9. Migration strategy по этапам

## Этап A. Ввести generic capability core без использования

### Изменяемые файлы

- новый `termin-scene/include/core/tc_component_capability.h`
- новый `termin-scene/src/tc_component_capability.c`
- `termin-scene/include/core/tc_component.h`
- `termin-scene/include/core/tc_scene.h`
- `termin-scene/src/tc_scene.c`
- `termin-scene/src/tc_component.c` или эквивалентный registry implementation

### Что делаем

- capability registry
- slot model
- component storage
- scene membership lists
- generic scene iteration

### Что не делаем

- не трогаем пока `drawable` / `input`
- не меняем render/input код

### Критерий готовности

- capability system существует
- можно зарегистрировать synthetic capability в тесте
- компонент можно attach/detach без поломки lifecycle

---

## Этап B. Перевести type registry flags на generic model

### Что делаем

- существующие special flags остаются снаружи как compatibility API
- внутри они проксируются в generic capability registry

То есть старый код ещё может вызывать:

- `set_drawable(...)`
- `set_input_handler(...)`

но под капотом это уже `set_capability(type, cap_id, true)`.

### Критерий готовности

- старые tests/bindings продолжают работать
- новые capability ids заведены для drawable и input

---

## Этап C. Мигрировать `input`

### Почему первым `input`

`input` проще, чем `drawable`:

- меньше методов
- нет phase marks
- нет geometry/material/shader pipeline coupling

### Новые файлы

- `termin-scene/include/termin/input_capability.hpp` или вне `termin-scene`, если сразу выносим
- `termin-scene/cpp/.../input_capability.cpp` либо новый input submodule

### Что делаем

- вводим typed `tc_input_capability`
- существующий `InputHandler` начинает attach’ить generic capability
- scene input dispatch идёт через `tc_scene_foreach_with_capability(..., input_cap_id, ...)`
- старые `tc_component_is_input_handler` и `tc_scene_foreach_input_handler` остаются thin wrappers

### Критерий готовности

- все input events проходят новым путём
- специальные поля `input_vtable` больше не нужны для новых вызовов

---

## Этап D. Мигрировать `drawable`

### Это самый сложный этап

Нужно вынести:

- `has_phase`
- `draw_geometry`
- `get_geometry_draws`
- `override_shader`

в render-side capability protocol.

### Что делаем

- вводим typed `tc_drawable_capability`
- `Drawable` wrapper attach’ит capability вместо special field wiring
- render passes используют generic capability iteration
- compatibility wrappers сохраняются

### Особое внимание

- не потерять текущую оптимизацию обхода drawables
- не втащить render-headers обратно в scene core

### Критерий готовности

- `ColorPass`, `ShadowPass` и другие собирают drawables через capability system
- `drawable_vtable` и `drawable_ptr` не нужны hot path

---

## Этап E. Выпилить legacy special fields

Удаляем из `tc_component`:

- `drawable_vtable`
- `drawable_ptr`
- `input_vtable`

Удаляем или переводим в deprecated wrappers:

- `tc_component_is_drawable`
- `tc_component_is_input_handler`
- `tc_component_draw_geometry`
- `tc_component_on_mouse_button` и т.д.

Оставить можно только thin forwarders поверх capability API, если это полезно для ABI.

---

## 10. Compatibility layer design

На переходный период важно сохранить старый surface.

### Wrappers, которые стоит оставить временно

- `tc_component_is_drawable(c)`
- `tc_component_is_input_handler(c)`
- `tc_scene_foreach_drawable(...)`
- `tc_scene_foreach_input_handler(...)`

### Новая внутренняя реализация

- берём capability id нужного протокола;
- вызываем generic capability APIs;
- внешнее поведение не меняется.

### Почему это критично

- Python code не нужно ломать сразу;
- render/input код можно мигрировать частями;
- проще откатывать изменения поэтапно.

---

## 11. Изменения в bindings

## 11.1 C++

Потребуются изменения в:

- `Drawable`
- `InputHandler`
- component registry helpers
- binding helpers для Python/C# bridge

### Задача

Снаружи API может остаться почти прежним:

- `install_drawable_vtable()`
- `is_drawable = True`
- `is_input_handler = True`

Но реализация должна attach’ить capability, а не писать в special field.

## 11.2 Python

В Python base class сейчас есть knowledge о `is_drawable` и `is_input_handler`.
Это допустимо как пользовательский sugar, если core больше не знает этих понятий напрямую.

То есть Python API можно оставить, но его backend должен стать generic.

---

## 12. Testing plan

## 12.1 Unit tests для capability core

Нужны тесты на:

- registration capability type
- attach/detach capability to component
- component has/get capability
- scene membership add/remove
- generic iteration order / completeness
- remove component clears capability membership
- migrate entity between scenes updates membership

## 12.2 Regression tests для input

- событие приходит только input-capable компонентам
- disabled component не получает input
- scene/editor filters работают как раньше

## 12.3 Regression tests для drawable

- drawable collection даёт тот же набор компонентов
- phase filtering работает
- layer mask filtering работает
- override_shader вызывается корректно

## 12.4 Performance checks

Минимально сравнить до/после:

- draw-call collection on medium scene
- input dispatch on scene with many components
- add/remove component cost

---

## 13. Технические решения, которые предлагается зафиксировать сейчас

### Решение 1

Используем **slot-based capability storage**, не map-based extension lookup.

### Решение 2

В первой версии делаем **fixed inline capability count**.

### Решение 3

В первой версии делаем **scene-local intrusive membership**.

### Решение 4

Core **не владеет capability_ptr**, ownership остаётся внешнему слою.

### Решение 5

Миграция идёт через **compatibility wrappers**, а не через big bang rewrite.

---

## 14. Первый безопасный implementation slice

Если начинать код сейчас, лучший первый срез такой:

### Scope

- добавить generic capability registry;
- добавить capability storage в `tc_component`;
- добавить scene membership по capability;
- добавить generic `tc_scene_foreach_with_capability`;
- пока не подключать render/input.

### Почему именно так

- меняется фундамент, но не меняется поведение render/input;
- легко тестировать изолированно;
- после этого можно мигрировать `input`, не трогая рендер.

### Deliverables

- новые core headers/sources;
- unit tests для capability core;
- без регрессий в существующих подсистемах.

---

## 15. Второй implementation slice

### Scope

- завести capability id для `input`;
- перевести `InputHandler` и related dispatch;
- сохранить старые input wrappers.

### Deliverables

- input path уже работает через capability system;
- `input_vtable` больше не нужен как первичный механизм.

---

## 16. Третий implementation slice

### Scope

- завести capability id для `drawable`;
- перевести render collection path;
- сохранить legacy drawable wrappers.

### Deliverables

- render hot path идёт через capability iteration;
- special drawable fields становятся legacy-only либо удаляются.

---

## 17. Признаки, что архитектура удалась

- В `termin-scene` больше нет domain-specific знания о render/input протоколах
- Новую capability можно добавить без изменения базового `tc_component`
- Scene iteration не требует полного сканирования всех компонентов
- Hot path использует только slot/mask/pointer operations
- Миграция прошла без big bang rewrite bindings и passes

---

## 18. Рекомендуемое следующее действие

Следующий практический шаг после этого документа:

**начать implementation slice A** — generic capability core.

Если перед кодом нужна ещё одна прослойка подготовки, то только в формате:

- списка конкретных файлов для этапа A;
- эскиза новых структур в `tc_component` и `tc_scene`;
- перечня тестов, которые надо добавить сразу.
