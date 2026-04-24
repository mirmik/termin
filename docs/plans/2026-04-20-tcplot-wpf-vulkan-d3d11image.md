# tcplot в WPF через Vulkan + D3D11Image

**Дата:** 2026-04-20
**Область:** tcplot (`PlotView2DMulti`) ↔ WPF-хост (PlotDemoApp, потом Alliance)
**Статус:** Фаза 0 выполнена. Фазы 1–5 отложены (vulkan-направление паузится).
**Смежный план:** [2026-04-19-wpf-termin-vulkan-path.md](2026-04-19-wpf-termin-vulkan-path.md) — про 3D-сцену termin-engine в WPF. Этот план касается отдельного пути для `tcplot`.

---

## Мотивация

Цель — получить `PlotView2DMulti` (сейчас используется в `PlotDemoApp` и планируется в `Alliance/SimLaunchView`) на Vulkan-backend, без потери привычной WPF-композиции (кнопки/попапы должны рисоваться поверх графика штатно).

## Выбор архитектуры (обсуждено 2026-04-20)

Рассмотрены три варианта встраивания Vulkan-кадра в WPF:

| Вариант | Airspace (WPF сверху) | Перф | Сложность кода | Вердикт |
|---|---|---|---|---|
| HwndHost + Win32 Vulkan swapchain | **ломается** (Win32 child-window не подчиняется композиции) | нативный | низкая | отклонён — UI-автор Alliance рисует кнопки/попапы поверх графика |
| Offscreen → WriteableBitmap | работает | **−5–10 мс/кадр** на GPU→CPU копию | низкая | отклонён — перф всё-таки важен |
| **Vulkan → shared D3D11 texture → D3D11Image** | работает | нативный (GPU-GPU) | высокая | **выбран** |

Аналог уже существует в OpenGL-пути: `OpenTK.GLWpfControl` под капотом делает ровно такой же interop — shared D3D9Ex surface + `WGL_NV_DX_interop2` + `D3DImage`. Мы повторяем тот же паттерн, но с Vulkan-стороны: `VK_KHR_external_memory_win32` + `D3D11Texture2D` + `D3D11Image`. Разница только в том, что для OpenGL путь упакован в готовую NuGet-библиотеку, а для Vulkan в .NET-мире такой обёртки нет — пишем сами.

## Альтернатива на долгий срок: D3D11-backend в tgfx2

Обсуждали возможность реализации полноценного D3D11-backend'а в tgfx2 (чтобы совсем избавиться от interop). Оценка: ~3000–4000 строк C++ + ~400 строк C# + тулчейн шейдеров (HLSL + DXC для кросс-компиляции в SPIR-V/DXBC). Итого 6–8 недель focus-work. Отложено — сначала пройдём interop-путь, если прод-нагрузка покажет, что interop неудобен — вернёмся.

Для шейдеров рекомендованный на будущее источник — **HLSL + DXC**: DXC умеет SPIR-V-target нативно, SPIR-V → GLSL через SPIRV-Cross проходит чище, чем GLSL → HLSL. Slang — кандидат через 1–2 года, сейчас mainstream ещё не достиг.

---

## Фазы

### Фаза 0 — параметризация tcplot backend'а ✅ **ВЫПОЛНЕНО (2026-04-20)**

- `tcplot/include/tcplot/plot_view2d_multi.hpp`: поле `device_` теперь `tgfx::IRenderDevice` (было `OpenGLRenderDevice`). Добавлен второй конструктор с явным `tgfx::BackendType`.
- `tcplot/src/plot_view2d_multi.cpp`: `tgfx::create_device(backend)` через фабрику. Конструктор без backend-аргумента читает env `TERMIN_BACKEND` через `default_backend_from_env()`.
- SWIG-обёртка не меняется: для активации Vulkan достаточно выставить `TERMIN_BACKEND=vulkan` до создания `PlotView2DMulti`. Отдельный конструктор с `BackendType`-аргументом — на Фазу 5, когда C#-контрол должен выбирать backend явно.
- **Не тронуто:** `plot_view2d.cpp` и `plot_view3d.cpp`. 3D-path через `draw_tc_mesh` делает `dynamic_cast<OpenGLRenderDevice>` (`engine3d.cpp:115`) для интеграции с legacy `tc_mesh`/`tc_gpu_share_group`. Для 2D WPF-интеграции не нужно, разбираться отдельно.
- GL-путь PlotDemoApp проверен — регрессий нет.

### Фаза 1 — Vulkan smoke test с tcplot (standalone, без WPF)

**Зачем:** подтвердить, что `PlotView2DMulti` через Vulkan-backend не разваливается до того, как инвестировать в WPF-interop. На текущий момент tcplot 2D-путь (без 3D через `draw_tc_mesh`) не имеет явных GL-специфичных мест, но единственный реальный тест — запустить.

**Что сделать:**
- Модифицировать `termin-graphics/tests/test_tgfx2_vulkan_window.cpp` (или создать `tcplot/tests/test_plot_view2d_multi_vulkan.cpp`): создать `PlotView2DMulti(ttf, 3, BackendType::Vulkan)`, залить тестовыми данными, рендерить в SDL2-окно через Vulkan swapchain.
- **Подводный камень:** метод `render(w, h, dst_gl_fbo)` в Vulkan-режиме не имеет смысла — аргумент `dst_gl_fbo` GL-специфичен. Решение: либо добавить `render_to_texture(TextureHandle)` в `PlotView2DMulti` (backend-neutral), либо в Vulkan-режиме использовать `blit_to_external_target`-эквивалент в `VulkanRenderDevice` (см. `vulkan_render_device.hpp:147` — "backend-neutral replacements").
- **Ожидаемые проблемы:**
  - `blit_to_external_target` на Vulkan throws — надо заменить путь рендера на нейтральный.
  - Возможны shader-compile issues (GLSL встроен в `.cpp` через `R"()"` — `engine2d.cpp`, `text2d_renderer.cpp` и др. — компилируется через shaderc, но могут вылезти `#version`-совместимость или extension-использование).
  - MSAA resolve на Vulkan идёт через renderpass-resolve, не через `glBlitFramebuffer` — должно работать, но проверять.

**Оценка:** 2–4 дня focus-work. Основное время — отладка shader-компилер и offscreen-рендеринг.

### Фаза 2 — Vulkan external-memory exports (Win32)

**Что добавить в `VulkanRenderDevice`:**
- Включение extensions: `VK_KHR_external_memory_win32` + `VK_KHR_external_semaphore_win32` + `VK_KHR_timeline_semaphore`.
- Метод создания экспортируемого `VkImage` (`VkExternalMemoryImageCreateInfo{handleTypes = OPAQUE_WIN32}`, `VkExportMemoryAllocateInfo`).
- Метод создания экспортируемого `VkSemaphore` (`VkExportSemaphoreCreateInfo`) — для sync с D3D11.
- Экспорт NT-handle через `vkGetMemoryWin32HandleKHR` / `vkGetSemaphoreWin32HandleKHR`.
- Публичный API (на `VulkanRenderDevice`, не `IRenderDevice` — это Vulkan-specific):
  ```cpp
  TextureHandle create_shared_image(uint32_t w, uint32_t h, PixelFormat fmt);
  HANDLE         get_shared_nt_handle(TextureHandle tex);
  VkSemaphore    create_shared_timeline_semaphore();
  HANDLE         get_semaphore_win32_handle(VkSemaphore sem);
  ```

**Standalone-тест (C++):** создать shared image, проверить, что handle валидный (`DuplicateHandle` не падает).

**Оценка:** 3–5 дней. Vulkan external-memory API не самый сложный, но validation layer иногда выдаёт нетривиальные warnings.

### Фаза 3 — C# D3D11Image обёртка (простой flat-colour тест)

**Что сделать:**
- Новый C#-класс `VulkanD3D11Bridge` (в `termin-csharp`): создаёт `ID3D11Device`, принимает NT-handle от Vulkan, открывает через `ID3D11Device1::OpenSharedResource1` как `ID3D11Texture2D`.
- WPF-обёртка `VulkanImage : Image`: держит `D3D11Image` как Source, `SetBackBuffer(D3DResourceType.IDirect3DSurface9, sharedSurface)`.
- Минимальный WPF-тест: Vulkan заливает shared image одним цветом, WPF показывает.
- Пакет `Microsoft.Wpf.Interop.DirectX` (если не хочется писать `D3D11Image` с нуля — это ~200 строк).

**Оценка:** 3–4 дня.

### Фаза 4 — Синхронизация `ID3D11Fence` ↔ Vulkan timeline semaphore

**Зачем:** без sync — tearing и use-after-write GPU races.

**Что сделать:**
- Vulkan сигналит экспортируемый timeline semaphore после каждого кадра.
- C#-сторона открывает тот же handle через `ID3D11Device5::OpenSharedFence`, получает `ID3D11Fence`.
- Перед каждым WPF-кадром (`CompositionTarget.Rendering`) `ID3D11DeviceContext4::Wait` на нужном monotonic-value.
- Verify: отсутствие tearing'а при быстром resize-е / обновлении данных.

**Подводный камень:** `ID3D11Fence` требует Win10 1809+. Если нужна совместимость с 1803 и раньше — придётся через keyed mutex (хуже эргономика), но сейчас Win10 1809 уже overdue — считаем, что не наш случай.

**Оценка:** 2–3 дня.

### Фаза 5 — Порт `MultiPlot2DControl` в PlotDemoApp

**Что сделать:**
- Новый `VulkanMultiPlot2DControl` (или переделка существующего `MultiPlot2DControl`): вместо `GLWpfControl` — `Image` с `D3D11Image`-источником.
- Сохранить весь текущий API: `Plot`, `AppendToLine`, `PanelHeight`, `ScrollOffset`, `MsaaSamples`, mouse-forwarding, pan coalescing (см. комментарии в текущем файле).
- Добавить SWIG-экспорт конструктора `PlotView2DMulti(ttf, count, BackendType)` — чтобы C#-контрол мог явно запросить Vulkan.
- Проверить: тот же demo-набор окон (`MainWindow`, `Plot2DWindow`, `MultiPlot2DWindow`, `ScrollableMultiPlot2DWindow`) работает, пан/зум отзывчивы, MSAA виден.

**Оценка:** 3–5 дней.

---

## Суммарная оценка

**Фазы 1–5 вместе:** ~2–3 недели focus-work одного человека. Календарно с прерываниями — 4–6 недель.

## Риски и подводные камни

1. **Intel iGPU и Vulkan external memory** — исторически глючили, может потребоваться fallback на `WriteableBitmap` для машин с Intel-only GPU. Проверять заранее (есть ли такие целевые машины у Alliance?).
2. **Shader-совместимость** — `text3d_renderer.cpp` использует `#version 330 core` (GL-style), для Vulkan нужна шапка `#version 450 core` + explicit layout. Часть сделано (`text2d_renderer.cpp:54` уже `#version 450 core` + `layout(push_constant)`), часть — нет.
3. **Device-sharing между Vulkan и D3D11** — рекомендуется создавать оба device'а на одном и том же физическом GPU через `DXGI_ADAPTER_DESC::AdapterLuid` ↔ `VkPhysicalDeviceIDProperties::deviceLUID`. Иначе shared handle может не открыться.
4. **Resize-storm** — при быстром ресайзе окна пересоздание shared image каждого размера приведёт к flicker'у и утечкам. Нужен handle-lifecycle-мененджер с deferred-destruction (как уже сделано для Vulkan-ресурсов через fence-based sync — см. коммит `52caa53`).
5. **3D на Vulkan в tcplot** — `plot_view3d.cpp` + `engine3d.cpp::draw_tc_mesh` используют legacy GL path (`tc_mesh_upload_gpu` + `tc_gpu_share_group`). Для Vulkan 3D tcplot нужно либо переписать путь загрузки mesh'а на tgfx2-native, либо не поддерживать 3D на Vulkan пока. Для Alliance (только 2D) это не блокер.

## Точка выхода из плана

Когда Alliance переходит на Vulkan-путь целиком и PlotDemoApp демонстрирует все сценарии на Vulkan без регрессий — план закрывается. До этого момента оба backend'а (GL + Vulkan) сосуществуют, выбор через env или конструктор.
