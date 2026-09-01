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

При уже собранном Web Runtime полный browser gate запускается отдельной
командой:

```bash
task test:web:browser
```

Если браузер не находится в `PATH`, executable задаётся явно:

```bash
TERMIN_WEB_BROWSER=/path/to/chrome task test:web:browser
```

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
