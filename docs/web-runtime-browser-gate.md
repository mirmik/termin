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

## Автономный HTML со сценой

Для уже экспортированного пакета Termin со сценой выполните из корня репозитория

```bash
task build:web
task package:web:scene -- path/to/package.trpkg Scene.html
```

Откройте `Scene.html` с диска. Файл включает viewer, Wasm и переданный пакет
с геометрией, материалами и шейдерами. Упаковщик сжимает Wasm, пакет сцены и
JavaScript-модули gzip перед встраиванием в HTML. При открытии страницы
браузер распаковывает их в памяти через `DecompressionStream("gzip")`.
Загрузчик использует локальные blob URL и при повторном запуске сцены.
Камера и источники света берутся из сцены.
Для прямого освещения добавьте `LightComponent` и материал, шейдер которого
читает источники сцены. Для работы на обоих бэкендах экспортируйте шейдеры
пакета для WebGPU и WebGL2. Упаковка в HTML сохраняет возможности web-профиля
runtime, включая `ShadowPass` для направленного света.

### Батискаф «Чёрный ящик»

После `task build:web` откройте `build/web-core/bin/Termin-Salvage.html`.
За минуту нужно достать оранжевый самописец из обломков судна. Стрелки или
WASD управляют тягой, пробел цепляет и отпускает груз. На телефоне доступны
экранные органы управления. Подведите трос к ящику, поднимите его, пройдите
через пролом и отцепите над приёмной площадкой справа.

Аппарат и ящик — динамические тела Termin. Контакты с палубой, переборкой и
приёмной площадкой рассчитывает `PhysicsWorldComponent`. Игровой C++-компонент
прикладывает тягу, сопротивление воды и силы натяжения троса на фиксированном
шаге сцены, отсчитывает время и определяет доставку. Он слинкован с веб-движком
в отдельный модуль `termin_web_salvage.wasm`. Страница передаёт ввод и читает
состояние для приборов. [Код игровой механики](../platform/termin-web-core/examples/salvage/web_salvage.cpp).

Проверка `task test:web:salvage` открывает отдельную копию HTML без сети и
проходит миссию в Chromium на WebGPU и WebGL2.

### Игра на память «Батискаф»

После `task build:web` откройте `build/web-core/bin/Termin-Bathyscaphe.html` с диска.
Запомните порядок вспышек на пульте и повторите сигнал щелчками по лампам,
касаниями или клавишами `1`–`4`. Для победы пройдите пять раундов.

Сцену отрисовывает Termin Web. Страница переключает источники света
через `host.setLightEnabled`, а при нажатии определяет лампу в 3D-сцене
через `host.pickEntity`. Правила игры и управление находятся
в [bathyscaphe-scene.html](../platform/termin-web-core/web/bathyscaphe-scene.html).

### Покадровая анимация спрайтов

Из исходного проекта с установленным SDK и собранным веб-плеером можно
сразу получить один HTML. Например, для [сцены со слизнем](../test-projects/sprite-flipbook/README.md)
выполните из корня репозитория

```bash
task package:web:project -- --project test-projects/sprite-flipbook --entry-scene Scenes/Main.scene build/web-core/bin/Termin-SpriteFlipbook.html
```

Откройте полученный файл с диска. Встроенный пакет содержит клип, его
спрайты и текстуру атласа. В сцене работает тот же `SpriteAnimator2D`,
что и в настольном плеере. В стандартном фреймграфе `World2DPass`
рисует текущую позу поверх непрозрачной геометрии до тональной коррекции.

### Экранный UI из пакета сцены

После `task build:web` откройте `build/web-core/bin/Termin-UiScene.html` с диска.
Щёлкните по флажку «Отметить сцену» или коснитесь его, чтобы поставить или снять галочку.
Флажок и подпись рисует движок внутри canvas. Их описание лежит в
[`hud.ui-document.json`](../platform/termin-web-core/examples/ui-scene/hud.ui-document.json).

Для своей панели укажите UI-документ в поле `ui_layout` компонента `UIComponent`.
Экспортёр помещает скомпилированный ресурс `ui_document` в пакет. В стандартном
фреймграфе `UIWidgetPass` рисует документ после `TonemapPass`, до преобразования
цвета для вывода в canvas. Для подписей веб-сборка содержит шрифт Droid Sans.
Размеры и отступы виджетов задаются в логических пикселях, а позиция мыши
или касания пересчитывается с учётом плотности canvas.

### Сцена с физикой

После `task build:web` откройте `build/web-core/bin/Termin-PhysicsScene.html`.
Нажмите «Отпустить шар» внутри canvas. Это кнопка из UI-документа сцены.
Её сигнал запускает падение и включает HTML-кнопку «Вернуть шар» рядом
с заголовком страницы. Нажмите её, чтобы снова подвесить шар над платформой.
Обе кнопки работают в автономном файле через `file://`.

Рядом со сценой находится `RetainedChart2D`. Он показывает мировую координату Z
центра массы шара в метрах и время симуляции в секундах. Замер содержит
начальную точку и первые 300 шагов физики (5 секунд при 60 Гц). После
«Вернуть шар» график возвращается к исходному масштабу и новой точке при t = 0.
На узком экране график располагается под сценой.

Чтобы снять такой ряд на странице, после инициализации тела вызовите
`host.recordRigidBodyHeight(uuid, maxSamples)`. На каждом фиксированном шаге
движок записывает координату после решения контактов.
`host.readRigidBodyHeightTrace()` возвращает снимок ряда с массивами
`times` и `heights`, которые можно передать в `chart.setData(times, heights)`.

Страница подписывается на нажатие после загрузки пакета через
`host.onUiButtonClick("physics-hud", "release", callback)`. Первый аргумент —
UUID сущности с `UIComponent`, второй — имя кнопки в документе. Метод
возвращает функцию отписки. Во время падения страница отключает кнопку
внутри сцены вызовом `host.setUiWidgetEnabled("physics-hud", "release", false)`.
«Вернуть шар» останавливает симуляцию, восстанавливает начальное состояние
твёрдого тела и снова включает кнопку в том же UI-документе. Сцена, положение
камеры и графический контекст сохраняются.

Симуляцию выполняет нативный `PhysicsWorldComponent` в WebAssembly
на фиксированном шаге сцены (по умолчанию 1/60 секунды). Шар и платформа
имеют `RigidBodyComponent` и `ColliderComponent`. У шара сферический
коллайдер, у статической платформы — коробчатый. После шага физики
движок переносит положение тела в трансформ сущности, который использует
рендерер.

Направленный свет отбрасывает тень от шара на платформу. Каждый кадр
`ShadowPass` рисует шар с точки зрения источника в карту глубины 512×512.
`ColorPass` читает эту карту при расчёте прямого света на платформе.
При падении и отскоке пятно смещается вместе с шаром. Материал демо
использует одну карту и один каскад через модуль `termin_single_shadow`.

### Сглаживание 3D-сцены

В веб-конвейере `Default` фон и непрозрачная геометрия рисуются с 4× MSAA:
четыре сэмпла на пиксель определяют, какую его часть занимает объект.
`ResolvePass` объединяет сэмплы HDR-буфера перед `TonemapPass`. Размер canvas
и координаты выбора объектов при этом сохраняются.

WebGPU поддерживает нужные форматы с четырьмя сэмплами. На WebGL2 движок
проверяет поддержку 4× для буферов цвета и глубины. Если устройство её
не предоставляет, сцена использует один сэмпл.

### Цвет сцены в canvas

`TonemapPass` переводит HDR-цвета в линейный диапазон дисплея. В демо
промежуточная текстура `rgba16f` сохраняет точность тёмных полутонов
до перевода в sRGB. Перед выводом в canvas общий для WebGPU и WebGL2
`OutputTransformRenderer` кодирует RGB
в sRGB и добавляет пространственный дизеринг для 8-битного вывода. WebGPU
пишет результат в UNorm-представление текстуры canvas. WebGL2 записывает
те же коды в промежуточную UNorm-текстуру и копирует их в canvas.

### Нажатия на объекты сцены

`task build:web` также создаёт `build/web-core/bin/Termin-InteractiveScene.html`.
Откройте файл в браузере и нажмите на одну из двух цветных ламп. Каждая
переключает собственный точечный источник света. Проведите по сцене, чтобы
повернуть камеру и нажать на лампу с нового ракурса.

Чтобы обработать нажатие в своей странице, передайте `onTap` адаптеру ввода.
Он различает щелчок, одиночное касание и жест камеры и передаёт координаты
в пикселях буфера canvas. `host.pickEntity` возвращает UUID ближайшего
доступного для выбора меша в этой точке либо `null` при промахе. Выбор
учитывает текущую камеру, флаг `pickable` и треугольники статического меша.

```js
let amberEnabled = true;
const input = createTerminWebInputAdapter(core, {
    canvas,
    onTap({x, y}) {
        if (host.pickEntity(x, y) === "lamp-amber") {
            const next = !amberEnabled;
            host.setLightEnabled("lamp-amber", next);
            amberEnabled = next;
        }
    },
}).attach();
await host.load(packageUrl);
input.setEnabled(true);
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
- Нажатия на объекты в автономном `Termin-InteractiveScene.html` мышью и
  касанием. Проверяется изменение цвета сферы при выключении каждого источника,
  промах, вращение камеры и попадание по лампе в новом положении.
- Экранный UI в автономном `Termin-UiScene.html` на WebGPU и WebGL2.
  Gate проверяет пиксели подписи и галочки, переключение мышью и касанием,
  сохранение положения камеры при жесте на виджете и попадание при DPR 2.
- Падение шара в автономном `Termin-PhysicsScene.html` на WebGPU и WebGL2
  с отключённой сетью. Проверяются запуск кнопкой движка, отскок, остановка
  на платформе, возврат HTML-кнопкой и повторный запуск касанием. В двух точках платформы
  измеряется вклад направленного света до и после падения. Цвет неподвижного
  шара сравнивается с ожидаемым sRGB. Gate также сопоставляет цвет шара,
  платформы и тени между бэкендами и проверяет однородность тёмного фона.
  Для графика высоты проверяются интервал между отсчётами, совпадение
  с положением шара, появление кривой и её очистка при возврате шара.

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
- размеры автономных HTML-файлов в байтах в `artifacts.standalone_html_bytes`;
- число файлов, raw/gzip-размер directory fixture и отдельный размер
  deterministic `package.trpkg`;
- package fetch, graphics init, native load, startup, first-frame и frame-time
  metrics;
- input/resize counters и характеристики кадров до/после orbit;
- диапазоны и результаты пиксельных проверок графика по каждому бэкенду
  в поле `retained_chart2d`;
- результаты проверки 3D-поверхности, осей и движения камеры для каждого
  бэкенда в поле `retained_chart3d`, а для автономного файла — в `standalone_chart3d`;
- высоту шара, вклад направленного света в двух точках платформы и
  значения `initial_srgb` для сравнения бэкендов в поле `physics_scene`;
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
