# Нулевой этаж

<div class="termin-kicker">District guide / Core</div>

<div class="termin-lead" markdown>
Core — инженерный коллектор под городом Termin: геометрия, значения,
отложенные вызовы, рефлексия, Python ABI и несколько служб, о которых верхние
этажи вспоминают обычно в пятницу вечером, когда оттуда уже идёт дым.
</div>

Наверху камеры летят сквозь сцены, редактор обещает порядок, GPU раскаляется,
а пользователь нажимает кнопку и ожидает результата. Core живёт ниже. Здесь
нет ни сцены, ни мешей, ни рендера, ни физики — только договорённости, которые
должны оставаться правдой, когда все эти вещи появятся.

Core — не «движок в миниатюре» и не склад полезных мелочей. Это семь
Core-owned пакетов и закрытый SDK-профиль:

- простые C/C++ типы, математика, значения, логи и настройки;
- очередь отложенной работы без тайного event loop;
- runtime inspection и сериализация между C, C++ и Python;
- один канонический free-threaded CPython 3.14t и один nanobind ABI;
- нейтральный Python host и нейтральные MCP-примитивы;
- инструменты, которые строят установленный SDK и проверяют его идентичность.

```console
task build:core
```

Результат появляется в `sdk-core/`. Это самостоятельный установленный продукт:
его CMake packages и Python runtime можно употреблять без Graphics, Engine и
Editor. Сам district при этом остаётся частью монорепозитория и собирается
только корневым `Taskfile.yml`.

<div class="termin-contract" markdown>
**Короткий контракт:** Core ничего не знает о графике, assets, сценах,
физике, редакторе, player или platform host. Если нижнему типу понадобился
`active_scene`, он уже не нижний — он просто заблудился в канализации.
</div>

## Маршрут чтения

<div class="termin-card-grid" markdown>

<div class="termin-card termin-card--core" markdown>

### [Первый спуск](getting-started.md)

Собрать `sdk-core`, запустить его Python и подключить два CMake package из
внешнего consumer-а.

</div>

<div class="termin-card termin-card--core" markdown>

### [Инженерные службы](toolbox.md)

Карта семи пакетов: кто хранит значения, кто проводит callbacks через границу,
а кто бросает собранный SDK с лестницы.

</div>

<div class="termin-card termin-card--core" markdown>

### [Контракт SDK](sdk.md)

CMake, bundled Python, manifests, ABI identity и доказательство того, что
установленный продукт не питается тайным проводом из checkout.

</div>

<div class="termin-card termin-card--core" markdown>

### [Пограничная служба](boundaries.md)

Тест на гражданство для нового кода и перечень вещей, которые Core не примет,
даже если они пришли в красивом namespace.

</div>

</div>

Сборочные команды и разница между district и профилем собраны отдельно в
[«Сборке и проверке»](build-and-test.md). Общая карта города находится в
[районах Termin](../index.md).
