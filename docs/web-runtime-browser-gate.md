# Web Runtime browser gate

## Поддерживаемая матрица

Обязательный gate первого Termin Web Runtime ориентирован на Chromium с
WebGPU. Автоматический CI использует headless Chromium и SwiftShader, поэтому
не зависит от наличия физического GPU на runner-е. Аппаратный Chromium остаётся
полезной ручной проверкой, но не заменяет детерминированный CI gate.

Firefox проверяется вручную там, где сборка браузера и платформа предоставляют
WebGPU. Отсутствие WebGPU в конкретной конфигурации Firefox не является
регрессией Termin. Safari в текущую compatibility matrix не входит.

## Запуск

Первый запуск устанавливает закреплённый Emscripten toolchain и собирает Wasm.
Node lifecycle smoke и полный Chromium gate запускаются отдельными задачами.
Native host tools и wasm32 Core при этом собираются непосредственно из текущего
checkout:

```bash
task build:web -- --setup
task test:web
task test:web:browser
```

Сборка публикует единый проверяемый каталог built-in WebGPU/WebGL2 shaders в
`build/web-core-host-tools/share/termin`. Render fixture не компилирует этот
набор повторно: она копирует артефакты из каталога и отдельно собирает только
свой package-specific shader.

При уже собранном Web Runtime полный browser gate запускается отдельной
командой:

```bash
task test:web:browser
```

Если браузер не находится в `PATH`, executable задаётся явно:

```bash
TERMIN_WEB_BROWSER=/path/to/chrome task test:web:browser
```

## Интерактивный график данных

`chart2d.html` строит линейный график через C API `tc_retained_chart2d`
библиотеки `tcplot`. JavaScript передаёт координаты, а оси, подписи,
деления и сам ряд рисует Termin. Для запуска из корня репозитория выполните

```bash
task build:web
python3 -m http.server 8000 --bind 127.0.0.1 --directory build/web-core/bin
```

Откройте `http://127.0.0.1:8000/chart2d.html`. Кнопка меняет набор точек
на том же графике. Перетаскивание сдвигает видимую область, колесо меняет
масштаб вокруг курсора. Для проверки конкретного бэкенда добавьте
`?backend=webgpu` или `?backend=webgl2`.

В своей странице задайте canvas размер через CSS, затем подключите модуль:

```html
<canvas id="signal" style="display:block;width:100%;height:360px;touch-action:none"></canvas>
<script type="module">
    import {createTerminChart2D} from "./termin-web-chart2d.mjs";

    const chart = await createTerminChart2D(document.querySelector("#signal"), {
        xLabel: "Time (s)", yLabel: "Voltage (V)", seriesName: "V(t)",
    });
    chart.setData([0, 1, 2, 3], [0, 0.5, 0.2, 1]);
</script>
```

`setData(x, y)` принимает обычные и типизированные числовые массивы
одинаковой длины. Первый непустой ряд задаёт диапазон автоматически.
Следующие вызовы заменяют точки и сохраняют текущий вид. Для повторной
подгонки передайте третий аргумент `{fit: true}`. Явный диапазон задаётся
через `chart.setRange({xMin, xMax, yMin, yMax})` или параметр `range`
при создании. При удалении графика вызовите `await chart.dispose()` для
освобождения GPU-ресурсов и обработчиков ввода.

Для публикации разместите рядом `termin-web-chart2d.mjs`, `termin-web-chart.mjs`,
`termin-web-core.mjs`, `termin-web-host.mjs`, `termin-web-input.mjs`,
сгенерированные `termin_web_core.mjs`, `termin_web_core.wasm` и
`graphics.trpkg` из одной сборки. Шрифт встроен в Wasm.
`graphics.trpkg` содержит каталог и готовые шейдеры обоих бэкендов.
График работает с собственным canvas без загрузки сцены и обновляет кадр
при изменении данных, области просмотра или размера.

## Интерактивная 3D-поверхность

После `task build:web` откройте `build/web-core/bin/Termin-Chart3D.html`
прямо в браузере. В файле собраны демо, Wasm со шрифтом и шейдеры.
Для встраивания в приложение та же сборка содержит ES-модуль и страницу
`chart3d.html`, доступную через описанный выше локальный HTTP-сервер.

```html
<canvas id="surface" style="display:block;width:100%;height:400px;touch-action:none"></canvas>
<script type="module">
    import {createTerminChart3D} from "./termin-web-chart3d.mjs";

    const chart = await createTerminChart3D(document.querySelector("#surface"), {
        xLabel: "X (m)", yLabel: "Y (m)", zLabel: "Height (m)",
    });
    const x = [-1, 0, 1], y = [-1, 0, 1];
    chart.setSurface(x, y, [0, 1, 0, 1, 2, 1, 0, 1, 0]);
</script>
```

`setSurface(x, y, z)` принимает координаты прямоугольной сетки и высоты
по строкам. Высота точки `(x[i], y[j])` лежит в `z[j * x.length + i]`.
Каждая ось содержит хотя бы две точки. Первая поверхность помещается в кадр
автоматически. Повторный вызов заменяет данные и сохраняет положение камеры.
Чтобы подобрать вид при обновлении, передайте четвёртым аргументом `{fit: true}`.

Левая кнопка мыши или движение одним пальцем вращает поверхность.
Shift с левой кнопкой или движение двумя пальцами сдвигает камеру.
Колесо мыши и щипок меняют масштаб. Вызов `await chart.dispose()`
освобождает ресурсы графика. На HTTP-странице можно задать бэкенд через
`?backend=webgpu` или `?backend=webgl2`.

## Проверки Chromium

Gate поднимает временный HTTP server только на loopback, запускает отдельный
временный browser profile и проверяет:

- secure context и наличие WebGPU;
- создание adapter/device и canvas surface;
- single-fetch indexed `package.trpkg` load, SHA-256/path validation и первый
  текстурированный кадр без package tree в MEMFS;
- reload, teardown и ожидаемые package errors;
- финальный shutdown Render bootstrap и повторную инициализацию без дубликатов;
- orbit, wheel, keyboard, focus и canvas resize/DPR;
- изменение пикселей сцены после input, а не только рост event counter;
- тот же orbit path непосредственно в полноэкранном `viewer.html`.
- retained `TcVisualScene` → `DrawList2D` → `Canvas2DRenderer` путь на отдельной
  странице `visual-scene.html`, включая устойчивые pixel probes.
- `RetainedChart2D` на WebGPU и WebGL2: пиксели подписей и линии при замене
  ряда, изменение диапазона после ввода, resize и повторное создание.
- `RetainedChart3D` на обоих бэкендах. Gate проверяет изображение поверхности
  и осей, обновление сетки, вращение, масштабирование, resize и повторное создание.
- Открытие автономного `Termin-Chart3D.html` в отдельном каталоге через
  `file://` с отключённой сетью и смену поверхности кнопкой.

Успех обозначается маркером `TERMIN_WEB_CORE_SMOKE_PASSED`. При любой ошибке
команда возвращает ненулевой exit code и сохраняет diagnostics.

## Machine-readable report

По умолчанию отчёт записывается в
`build/web-core/bin/browser-gate-report.json`. Другой путь можно задать через
`TERMIN_WEB_GATE_REPORT` либо аргумент `--report` самого
`termin-web-core/tests/browser_smoke.py`.

Report schema v1 содержит:

- версию Chromium, user agent и признаки secure context/WebGPU;
- raw и gzip-размеры Wasm/ESM/host/input/viewer artifacts;
- число файлов, raw/gzip-размер directory fixture и отдельный размер
  deterministic `package.trpkg`;
- package fetch, graphics init, native load, startup, first-frame и frame-time
  metrics;
- input/resize counters и характеристики кадров до/после orbit;
- диапазоны и результаты пиксельных проверок графика по каждому бэкенду
  в поле `retained_chart2d`;
- результаты проверки 3D-поверхности, осей и движения камеры для каждого
  бэкенда в поле `retained_chart3d`, а для автономного файла — в `standalone_chart3d`;
- статус, длительность gate и ошибку/Chrome stderr при падении.

GitHub Actions job `web-runtime-chromium` запускает те же публичные build и
test-задачи и публикует JSON как artifact `web-runtime-chromium-gate`.

## Retained VisualScene2D example

После сборки страница `build/web-core/bin/visual-scene.html` показывает
самостоятельный retained 2D пример. Она создаёт дерево `TcVisualScene` в Wasm,
понижает его в канонический `DrawList2D` и исполняет список через
`Canvas2DRenderer` на WebGPU.

Страница загружает fixture runtime package без запуска scene frame loop:
package предоставляет закреплённые WGSL-артефакты общих canvas2d-шейдеров.
Пример автоматически проверяется общим `termin_web_core_browser_smoke`. Для
быстрого изолированного прогона только этого пути доступна цель:

```bash
cmake --build build/web-core --target termin_web_visual_scene_browser_smoke
```

## Firefox manual scenario

1. Разместить `build/web-core/bin` на HTTPS origin либо открыть через loopback
   `http://127.0.0.1`.
2. Открыть `viewer.html` и убедиться, что состояние стало `running`.
3. Проверить orbit левой кнопкой, pan правой кнопкой, zoom колесом и resize
   окна.
4. Проверить отсутствие WebGPU validation errors в console.
5. Если `navigator.gpu` отсутствует или `requestAdapter()` возвращает `null`,
   записать конфигурацию браузера/ОС как unsupported, а не считать сцену
   сломанной.

## Deployment contract

- Production origin обязан использовать HTTPS. Loopback HTTP допустим только
  для разработки и тестов.
- Сервер должен отдавать `.wasm` как `application/wasm`, `.mjs` как JavaScript,
  JSON как `application/json`, а texture formats с корректным MIME type.
- HTML и mutable manifest следует отдавать с revalidation (`no-cache`).
  Versioned Wasm/ESM/package artifacts можно отдавать с длительным
  `max-age` и `immutable`; URL обязан меняться вместе с содержимым.
- Текущий runtime однопоточный и не требует `SharedArrayBuffer`, поэтому
  COOP/COEP не являются частью deployment contract. Их следует добавлять
  только вместе с отдельным threaded-Wasm этапом.
- WebGPU uncaptured errors и device loss логируются native backend-ом и
  переводят host в явное error state на следующем frame tick.
