# tgfx / termin-graphics review (2026-04-20)

## Что посмотрел

- `tgfx2` core: `render_context`, `device_factory`, `vulkan_render_device`, `vulkan_shader_compiler`.
- Python слой (`nanobind`): `tgfx2_bindings.cpp`.
- Тестовый контур: `tests/test_tgfx2_*`, `tests/python/*` (по структуре и покрытию).

## Основные наблюдения

### 1) UX API: много методов раньше падали неочевидно при неправильном lifecycle

До правки часть методов `RenderContext2` напрямую дергала `cmd_` без явной проверки открытого кадра. Для пользователя библиотеки это обычно выглядит как «краш/segfault где-то глубоко», вместо понятной причины (`begin_frame` забыли, вызвали `end_frame` второй раз и т.п.).

Сделано: добавлены явные `std::runtime_error` с человекочитаемыми сообщениями для ключевых lifecycle-sensitive путей (`begin_frame`, `end_frame`, `begin_pass`, `draw*`, `set_viewport`, `set_scissor`, `blit`, `flush_*`).

### 2) Python API: недостаточная валидация входа

- `create_shader(stage, source)` принимал произвольный `int` и молча кастовал к enum.
- `create_texture_r8` / `create_texture_rgba8` не проверяли согласованность размеров `data` и `(w, h)`.

Сделано: добавлена ранняя валидация с `nb::value_error`; это значительно упрощает дебаг для Python-пользователей.

## Что ещё рекомендую (без внесения в этот коммит)

1. **Сделать «strict env parsing» для backend выбора.**
   Сейчас `default_backend_from_env()` молча откатывается на OpenGL при неизвестном значении `TERMIN_BACKEND`. Это удобно для старта, но плохо для дебага CI/прод-конфигов. Рекомендую режим:
   - default: fallback + warning;
   - strict (через env/flag): throw на неизвестное значение.

2. **Управление Vulkan validation слоями через явный конфиг.**
   В `create_device(BackendType::Vulkan)` вшито `enable_validation = true`. Для релиза/benchmark обычно нужен явный контроль, а не hardcoded поведение.

3. **Единый публичный «error model» для C++/Python.**
   Сейчас часть мест кидает `runtime_error`, часть молчит (legacy GL uniform helpers на Vulkan), часть просто возвращает 0/empty. Хорошо бы выровнять контракт (например, policy: throw в debug, мягкий no-op только там, где это точно безопасно).

4. **Добавить тесты именно на диагностический UX.**
   Нужны тесты формата «неправильный lifecycle -> понятная ошибка», «битый размер texture data -> ValueError». Это защитит API-дружелюбность от регрессий.

## Быстрый итог

Слой стал заметно дружелюбнее именно для интеграторов: ошибки теперь более ранние, точные и читаемые, особенно при миграции на Vulkan/backend-neutral path.
