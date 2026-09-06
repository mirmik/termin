# Первый пакет исправлений графического стека — 2026-09-06

Продолжение [production audit](2026-09-06-termin-graphics-production-audit.md)
и umbrella #2230. Закрыты #2197, #2198, #2199, #2203.

## Изменения

- **#2199, validation gate:** root CTest требует Vulkan validation layer и
  включает synchronization validation. ERROR diagnostics проваливают тест даже
  при успешном exit code; callback работает на initialization и teardown,
  счётчик ошибок живёт до уничтожения instance. Native negative fixtures
  доказывают отказ на ошибке buffer creation, shutdown, instance creation и
  отсутствии layer. Полный вывод сохранён во вложенных CTest logs.
- **#2197, texture payload:** один C-дескриптор
  `{data, size_bytes, width, height, channels}` используется C/C++ и Python.
  Проверка фактического размера выполняется до hashing/copy; формат соответствует
  каналам, RGB остаётся трёхбайтным до GPU normalization. Invalid updates
  сохраняют прежнее содержимое, resize/format change удаляет старый CPU payload.
  Арифметика размеров проверяется на переполнение. Native consumers мигрированы;
  Python сообщает `ValueError` для неправильного ndarray.
- **#2203, SPIR-V:** проверяются alignment, header и границы instruction stream
  до копирования в words/reflection; ошибка содержит происхождение shader.
  Это проверка binary envelope, а не полный semantic validator. Согласование
  compiler/device target остаётся в #2204.
- **#2198, pools:** явные move constructor/assignment освобождают вытесненные
  owned resources через общий release path. Self move безопасен, moved-from
  pool пуст, borrowed color сохраняется.

Контракт texture API описан в
[документации модуля](../../graphics/termin-graphics/docs/index.md#texture-cpu-sync).
Изменение C/C++ сигнатуры требует пересборки consumers; SDK пересобран целиком.

## Проверки

- `task build` — полный SDK собран, SDK verification и native Python imports
  прошли.
- `task test:python:setup`, затем selected `task test:python` — **57 passed**:
  texture payload/API, default texture assets, runtime texture export и CTest
  metadata.
- `task lint:cpp` с Python bindings и каноническим Python 3.14 — изменённые
  production C/C++ файлы прошли clang-tidy.
- Обычный `task test:cpp` — **235 registrations, 22 failures, 4 skips**.
  Failures соответствуют существующим Vulkan defects; gate теперь показывает
  их честно. `tgfx_tests`, `tgfx2_device_factory_test`, новые
  `tgfx2_vulkan_shader_input_test` и `tgfx2_vulkan_validation_test` проходят.
  Vulkan smoke отдельно подтверждает RGB8 upload/readback `(17, 99, 231, 255)`.
- Эти же четыре целевых executable/регистрации проходят в отдельной
  **ASan/UBSan** сборке; RGB native roundtrip сохраняется. Полный sanitizer
  набор завершился с **24 failures из 233 tests** и остаётся красным из-за
  известных Vulkan ошибок и отдельных находок ниже.

Команда воспроизведения sanitizer-профиля:

```bash
VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json \
VK_LOADER_LAYERS_DISABLE='~implicit~' \
TERMIN_SHADER_ARTIFACT_ROOT="$PWD/sdk/share/termin" \
CTEST_PARALLEL_LEVEL=4 BUILD_JOBS=8 BUILD_DIR="$PWD/build/graphics-asan" \
CFLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' \
CXXFLAGS='-fsanitize=address,undefined -fno-omit-frame-pointer' \
LDFLAGS='-fsanitize=address,undefined' \
task test:cpp -- --no-opengl --no-sdl
```

Явный llvmpipe и отключение сторонних implicit layers убирают наблюдавшиеся даже
на пустом устройстве утечки loader/ICD/D-Bus. Khronos validation и synchronization
validation остаются включены, LeakSanitizer не отключается и suppressions не
добавлены. Вывод обычных тестов доступен в `Testing/Temporary/LastTest.log`
соответствующего build-каталога, результаты — в `ctest-results.xml` и
`ctest-execution-manifest.json`. Логи этого прохода также сохранены в
`/tmp/termin-graphics-first-pass.log`, `/tmp/termin-graphics-asan-final.log`,
`/tmp/termin-graphics-python-tests.log`, `/tmp/termin-graphics-lint.log`.

## Дополнительные находки

По месту исправлены два UAF в тестовых fixtures: command list уничтожался после
Vulkan device, UI-тест запрашивал handles уже удалённых widgets. Assertions
двух dispatch tests включены и в Release. Исправлена отсутствовавшая
`python-bindings` classification у world-controller test, мешавшая чистому
native build-каталогу.

Отдельные незавершённые работы зафиксированы на доске:

- **#2238:** metadata standalone/unowned widgets не освобождается; LSan
  воспроизводит утечки в FrameTimelineWidget и GUI renderer smoke.
- **#2240:** часть CTest targets теряет проверки и операции внутри `assert`
  из-за Release `NDEBUG`; нужен общий root contract. Воспроизведено также в
  `display_input_router_test`.
- **#2241:** удалённый FEM joint остаётся в runtime links мира; ASan фиксирует
  UAF в `FEMPhysicsWorldComponent::clear_runtime_links()` при teardown сцены.

Следующий graphics пакет — #2200/#2201/#2202: buffer/image/host synchronization,
с предварительной проверкой порядка отложенных Vulkan команд. Платформенные
D3D11/browser/Quest проверки в этом проходе не выполнялись.
