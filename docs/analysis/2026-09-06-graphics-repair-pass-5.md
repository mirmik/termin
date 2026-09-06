# Пятый пакет исправлений графического стека — 2026-09-06

Продолжение [четвёртого пакета](2026-09-06-graphics-repair-pass-4.md), umbrella #2230.
Исправлен Vulkan WSI lifecycle (#2205), present semaphore reuse (#2206) и
sharing для разных graphics/present queue families (#2207).

## Lifecycle и ошибки

`compose_and_present` проверяет source до acquire: действующий image, CopySrc,
single sample, color format и определённый layout. Неверный source логируется,
кадр не приобретается, fence/semaphore state не меняется.

Submit fence сбрасывается только непосредственно перед `vkQueueSubmit`.
Ожидание submit fence разрешено только для успешно submitted slot. OUT_OF_DATE
при acquire возвращает запрос recreate без пустого submit; TIMEOUT/NOT_READY
пропускают кадр. SUBOPTIMAL остаётся usable, согласно существующему Android
identity-transform contract.

Wait/reset/acquire/record/submit/present errors логируются. Fatal error
останавливает эту swapchain generation: последующие compose/clear отвергаются
до native work. Явный recreate после успешного retirement создаёт свежие sync
objects и разрешает работу. Неудачный submit не вызывает present и не публикует
несостоявшийся source layout transition. Это локальное состояние swapchain,
не реализация device-wide recovery из #2213.

Acquire также получает отдельный fence. Он нужен для ошибки между acquire и
submit: завершение WSI signal должно быть доказано перед уничтожением acquire
semaphore. Acquire fence ожидается перед reuse/retirement независимо от submit
fence: одно лишь завершение graphics semaphore wait не подтверждает завершение
сигнала acquire fence. Несданный submit fence не ожидается даже при shutdown.

Общий `submit_frame` используется compose и clear. Низкоуровневые acquire,
present и frame-slot методы стали private; публичная публикация проходит через
проверяемый lifecycle. В репозитории внешних вызовов этих методов не было.

## Presentation synchronization

- Render-finished semaphores принадлежат swapchain images, acquire semaphores,
  command buffers и submit fences — frame slots. При recreate размер per-image
  массива пересоздаётся по действительному числу images.
- Acquire wait на TRANSFER соединён с layout transition через TRANSFER source
  stage barrier. Прежний TOP_OF_PIPE не входил в эту цепочку: window validation
  воспроизводила WRITE_AFTER_READ относительно presentation acquire.
- Все compose/clear image barriers задают `VK_QUEUE_FAMILY_IGNORED` явно.
  Разные graphics/present families используют CONCURRENT sharing с обоими
  индексами; одинаковые — простой EXCLUSIVE path без transfers.
- Source transition учитывает предыдущие memory writes, включая uploads;
  engine layout обновляется после успешного submit.

Per-image reuse следует
[рекомендации Khronos](https://docs.vulkan.org/guide/latest/swapchain_semaphore_reuse.html).
Отдельное ограничение unextended Vulkan сохраняется: device/queue idle не
является формальным доказательством presentation completion при окончательном
retirement. Native validation допускает этот распространённый baseline; строгий
retirement с present fences/maintenance1 выделен в #2254. Этот пакет не выдаёт
graphics fence за гарантию presentation completion.

## Проверки

Новый `tgfx2_vulkan_swapchain_test` работает с реальным SDL/Vulkan surface и
подменяет выбранные вызовы через небольшой `SwapchainOps` table. Проверяются:

- invalid source до acquire; OUT_OF_DATE, TIMEOUT, NOT_READY;
- ошибки acquire, reset acquire fence, reset submit fence, wait, submit, present;
- отсутствие native work после fatal, восстановление через recreate;
- отсутствие ожидания fence неудачного submit при retry/recreate/destructor;
- image → signal semaphore mapping, 120 кадров compose/clear с resize;
- FIFO и доступный Immediate mode. Mailbox публичным `PresentationMode` не
  выражается, поэтому его прогон не заявляется;
- create-info для искусственно различных family indices 3/7 и совпадающих 3/3.

Штатный оконный прогон на NVIDIA RTX 5090:

```bash
TERMIN_UI_FONT="$PWD/termin-thirdparty/recastnavigation/RecastDemo/Bin/DroidSans.ttf" \
BUILD_JOBS=8 task test:cpp -- --window-tests
```

Результат: **253 passed, 1 failed из 254**, 2 inventory entries вне профиля.
Vulkan validation errors отсутствуют. Остался OpenGL3.3 shader interface test
на NVIDIA (#2253). Обычный offscreen профиль — подмножество этого прогона.
После исправления CMake backend guards обычный `task test:cpp` также выполнен
отдельно: **241 passed, 0 failed**, 4 inventory entries вне профиля.

В трёх старых window smoke исправлены color-only fixtures: pipeline depth format
теперь Undefined, как в фактическом render pass. Это устранило отдельные
`renderPass-02684`. Profiler window smoke требует доступный font; указанный выше
явный font path позволяет проверить его без зависимости от ambient SDK поиска.

Новый WSI fault/stress test и обе backend triangle Vulkan registrations прошли
также под ASan/UBSan на llvmpipe/X11 с Khronos/sync validation и LeakSanitizer,
без suppressions. Старый `tgfx2_vulkan_window` обнаруживает 29-byte leak внутри
SDL/X11 title conversion (#2255), при нулевом числе Vulkan validation errors.
Регистрации OpenGL window tests теперь учитывают выключенный OpenGL backend;
общий triangle executable остаётся доступен Vulkan registrations.
Финальный sanitizer window profile после исправления registration:
**240 passed, 5 failed из 245**, без skips. Остались прежние #2238 (два Widget
leaks), #2240 (Release assert policy), #2241 (FEM UAF) и новый #2255 (SDL/X11).
Vulkan core/sync validation errors отсутствуют. Параметры: X11,
`VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/lvp_icd.json`,
`VK_LOADER_LAYERS_DISABLE=~implicit~`, `--no-opengl --window-tests`; остальные
sanitizer/build flags соответствуют четвёртому пакету.

`task build` собрал полный SDK и проверил native Python import graph.
Focused `task lint:cpp -- --python-bindings --jobs 4` для `vulkan_swapchain.cpp`
прошёл без project warnings.

Логи: `/tmp/termin-graphics-pass5-window-final.log`,
`/tmp/termin-graphics-pass5-asan-final.log`, `/tmp/termin-graphics-pass5-cpp-default.log`,
`/tmp/termin-graphics-pass5-sdk.log`,
`/tmp/termin-graphics-pass5-lint.log`.

## Остаток и platform gates

#2207 остаётся On Test: нужен реальный адаптер/surface, где graphics и present
families различны. Named gate — запустить новый WSI test и backend triangle
Vulkan FIFO/Immediate через `task test:cpp -- --window-tests`, проверить
compose/clear, resize, repeated recreate и отсутствие core/sync errors.
Проверка create-info с разными индексами не подменяет эту платформу.

Windows и Android/Quest в этом проходе не запускались. Device-wide terminal
error/cleanup contract остаётся в #2213; строгий presentation retirement — #2254.
