# Language-Neutral Deferred Dispatcher

## Status

Accepted and implemented by `termin-dispatch`.

## Context

Встраиваемому приложению нередко нужно принять completion или изменение из
worker-потока, а применить его в выбранной фазе собственного цикла. Это
нормальная application-level задача и не означает, что движок должен объявить
один поток привилегированным или встроить глобальный UI executor.

Связывать такую очередь с `termin-gui-native`, `termin-window`, graphics host,
редактором или Python нельзя:

- UI-модуль должен оставаться библиотекой виджетов;
- не каждое окно использует Termin UI;
- headless и embedded hosts имеют собственные циклы;
- C++, Python и будущие языки должны видеть одну семантику;
- Termin пока не должен неявно возвращать многопоточность в свои приложения.

## Decision

В SDK существует самостоятельный leaf-модуль `termin-dispatch`.

Его source of truth — узкий C ABI. C++ и Python являются проекциями того же
native dispatcher, а не независимыми реализациями очереди. Модуль зависит
только от `termin-base` для логирования и не знает о scene, engine, render,
graphics, windows, UI или editor.

Dispatcher:

- не создаёт потоков;
- не содержит thread ID и не назначает owner thread;
- не запускает event loop;
- принимает работу через thread-safe `post`;
- исполняет её только при явном `drain`, на потоке вызвавшем `drain`;
- позволяет приложению выбрать фазу цикла, budget и shutdown policy.

Таким образом, Diffusion Editor может публиковать completion из своих
worker-потоков и вызывать `run_pending` в собственном цикле. Сам Termin от этого
не становится многопоточным и не получает автоматической integration point.

## Ordering and reentrancy

Очередь FIFO для принятой работы. Каждый drain формирует конечный batch из
работы, видимой в начале вызова. Публикация из callback переносится в следующий
batch. Это защищает application loop от бесконечной цепочки self-posting и
делает одну фазу обслуживания ограничиваемой.

Одновременно исполняется не более одного drain. Конкурентные внешние вызовы
сериализуются; рекурсивный drain из callback не блокируется на самом себе, а
возвращает `busy`.

Callback errors не разрушают очередь: они логируются, отражаются в статистике,
после чего batch продолжается.

## Ownership and cancellation

Успешный C `post` передаёт dispatcher-у payload и optional disposer.
Освобождение происходит ровно один раз после исполнения, успешной отмены,
discard или destroy. Неуспешный `post` оставляет payload вызывающей стороне.

Отмена адресует работу generational ticket-ом. Она успешна только пока работа
стоит в очереди. Уже захваченный текущим batch callback считается executing и
не отменяется. Stale ticket безопасно отклоняется.

`close` только запрещает новые posts. Приложение явно выбирает, исполнить ли
остаток или вызвать `discard_pending`. `destroy` закрывает dispatcher, ждёт
активный drain и освобождает очередь; внешний lifetime handle при этом обязан
быть согласован вызывающей программой.

## Language projections

### C

Opaque handle, function pointers, `void*` payload, disposer, generational
ticket и plain statistics struct. Это стабильная граница для Rust, C#, Lua и
других будущих FFI.

### C++

Move-only RAII owner, `std::function<void()>` convenience overload и
non-owning cancellation token. Исключения переводятся в logged failed result и
не проходят через C boundary.

### Python

`Dispatcher.defer`, `DeferredCall.cancel` и `Dispatcher.run_pending`.
Публикация и отмена разрешены из worker-потоков. Binding обеспечивает GIL
вокруг Python callback/lifetime, а native drain не удерживает GIL между
callbacks.

## Explicit non-goals

- автоматическая интеграция в `EngineCore`, редактор или window manager;
- UI-specific `defer`;
- выделенный background thread или thread pool;
- task dependencies, priorities, futures или work stealing;
- wakeup конкретного event loop;
- сокрытие ограничений внешнего platform API.

Если приложению нужен wakeup спящего event loop, оно добавляет адаптер своего
loop поверх успешного `post`. Универсальный dispatcher не должен выбирать
SDL/Win32/Qt/asyncio механизм и тем самым приобретать зависимость от host-а.
