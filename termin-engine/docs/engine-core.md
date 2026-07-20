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

## Завершение runtime

`shutdown()` явно и окончательно освобождает принадлежащие engine сцены и
рендеринг. Вызов идемпотентен, но после него нельзя снова запускать loop,
подключать loop client или выполнять кадры. `shutdown()` нельзя вызывать, пока
`run()` ещё исполняется.

Если `RenderEngine` использует графическое устройство, принадлежащее host,
composition root обязан завершать приложение в таком порядке:

1. `EditorSession.prepare_engine_shutdown()` отключает loop client и снимает
   frontend-интеграции;
2. `EngineCore.shutdown()` разрушает engine-owned потребителей графического
   устройства;
3. `EditorSession.close()` разрушает окна и их per-window presentation
   resources.
4. После того как engine-owned GPU resources и все окна уничтожены,
   `WindowedGraphicsSession.close()` сначала закрывает канонический
   `tgfx::GraphicsHost`, затем platform state оконной системы.

`tgfx::GraphicsHost` является единственным владельцем graphics domain и явно
инжектируется в `RenderEngine`; восстановление второго cache/context из
process-global device запрещено. `BackendWindowSystem` владеет только platform
bootstrap, а `BackendWindow` — только native/presentation state. Session
фиксирует lifetime: окна → GraphicsHost → platform bootstrap.

Деструктор `EngineCore` вызывает `shutdown()` как страховку, но host не должен
полагаться на него при borrowed graphics device: владелец устройства обязан
быть ещё жив во время явного shutdown.

## Профилирование

Когда profiling включен, loop владеет границами profiler frame. UI-work можно
включить или приглушить как единую секцию `UI`; приглушение исключает UI только
из дерева секций, но не из raw `active_ms`. Host может открывать устойчивые
дочерние фазы внутри `UI`. Native editor использует `Events`, `Queued Work`,
`Project Watch`, `Observers & Input`, `Debug Tools`, `UI Schedule` и
`UI Compose`.

Cadence измеряется по `steady_clock` отдельно от времени размеченных секций.
Перед scheduler resync фиксируются фактический start-to-start interval и
опоздание относительно ожидаемого старта. Поэтому кадр, который не уложился в
deadline, остается видимым в истории даже когда loop пропускает попытку
«догнать» старое расписание.

`SceneManager Tick` покрывает полный scene tick, включая служебную работу между
обновлениями отдельных сцен. Внутри `Scene Update` scene scheduler размечает
фазы `Start`, `Fixed Update`, `Update`, `Extensions`, а component-фазы — ещё и
конкретные экземпляры в форме `Type @ Entity [source]`. Устаревших режимов
`profile_components` и `detailed_rendering` нет: детализация задаётся явными
стабильными секциями во владельцах подсистем, чтобы профиль не менял структуру
от скрытого глобального флага.
