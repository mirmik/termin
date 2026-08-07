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

Первый запуск устанавливает закреплённый Emscripten toolchain, собирает Wasm,
исполняет Node lifecycle smoke и полный Chromium gate:

```bash
./build-web-core.sh --setup --browser-smoke
```

При уже установленном toolchain достаточно:

```bash
./build-web-core.sh --browser-smoke
```

Если браузер не находится в `PATH`, executable задаётся явно:

```bash
TERMIN_WEB_BROWSER=/path/to/chrome ./build-web-core.sh --browser-smoke
```

Gate поднимает временный HTTP server только на loopback, запускает отдельный
временный browser profile и проверяет:

- secure context и наличие WebGPU;
- создание adapter/device и canvas surface;
- strict package load и первый текстурированный кадр;
- reload, teardown и ожидаемые package errors;
- финальный shutdown Render bootstrap и повторную инициализацию без дубликатов;
- orbit, wheel, keyboard, focus и canvas resize/DPR;
- изменение пикселей сцены после input, а не только рост event counter;
- тот же orbit path непосредственно в полноэкранном `viewer.html`.

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
- число файлов, raw и gzip-размер strict runtime package;
- package fetch, graphics init, native load, startup, first-frame и frame-time
  metrics;
- input/resize counters и характеристики кадров до/после orbit;
- статус, длительность gate и ошибку/Chrome stderr при падении.

GitHub Actions job `web-runtime-chromium` запускает этот же публичный build
wrapper и публикует JSON как artifact `web-runtime-chromium-gate`.

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
