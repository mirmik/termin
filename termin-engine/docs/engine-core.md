# EngineCore

`EngineCore` - владелец runtime loop. Он связывает обновление сцен, рендеринг и callbacks host-приложения в один цикл кадра.

Исходники:

- `include/termin/engine/engine_core.hpp`
- `src/engine_core.cpp`
- `bindings/engine_core_bindings.cpp`

## Роль

`EngineCore` владеет одним [SceneManager](scene-manager.md) и одним [RenderingManager](rendering-manager.md). Редактор и player обычно должны работать с менеджерами через engine runtime, а не создавать независимые экземпляры менеджеров.

Здесь же выполняется engine-wide runtime initialization:

- init/shutdown scene runtime;
- init/shutdown collision runtime;
- регистрация builtin scene extensions;
- публикация singleton через C API для cross-DLL доступа.

## Цикл кадра

`EngineCore` задает порядок одного кадра:

```text
обработать host events
обновить сцены
подготовить сцены к рендеру
отрендерить и презентовать
вызвать after-render callbacks
```

Важный контракт здесь - порядок:

1. сначала обрабатываются host/UI events;
2. обновление сцен происходит до рендера;
3. `before_render` дает scene components последний шанс опубликовать состояние, нужное рендеру;
4. rendering видит стабильное состояние сцены на текущий кадр;
5. after-render callbacks вызываются после presentation.

## Интеграция с host

`EngineCore` не привязан к конкретному host. Host предоставляет callbacks:

- обработка events;
- проверка, надо ли продолжать цикл;
- shutdown.

Это позволяет SDL, tcgui, Qt-like hosts, tests и external embedding использовать одну и ту же форму runtime loop.

## Профилирование

Когда profiling включен, loop владеет границами profiler frame. UI-work можно включить или приглушить как единую секцию `UI`; это сохраняет сравнимость scene/render profiling между разными host-ами.

Cadence измеряется по `steady_clock` отдельно от времени размеченных секций.
Перед scheduler resync фиксируются фактический start-to-start interval и
опоздание относительно ожидаемого старта. Поэтому кадр, который не уложился в
deadline, остается видимым в истории даже когда loop пропускает попытку
«догнать» старое расписание.
