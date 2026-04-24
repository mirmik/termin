# WPF ↔ Termin — путь к Vulkan: план по C#-стороне

**Дата:** 2026-04-19  
**Область:** WPF-хост (C#) ↔ termin engine (C++/Python)  
**Статус Phase 1 со стороны termin:** готово (в termin-env, ветка `feature/termin-app-engine-vulkan`).  
**Что надо сделать на C#-стороне:** описано ниже.

---

## Контекст

Сейчас WPF-приложения (TerminSceneApp, VdegNexus/Alliance) выводят 3D через
`GLWpfControl` (OpenTK.Wpf) → GL FBO, передаваемый в termin через
`tc_render_surface` vtable (`get_framebuffer` = FBO id). Termin пишет прямо
в этот FBO через `blit_to_external_target` — **путь GL-only**, на Vulkan
throws.

Фаза 1 унифицирует API так, чтобы surface отдавала движку **tgfx2
TextureHandle** вместо raw FBO id. На OpenGL это чистый рефактор —
внутри termin сразу активируется ветка `blit_to_texture`, которая
backend-neutral. На Vulkan это обязательное предусловие для будущей
интеграции D3D11/DXGI interop.

---

## Что уже сделано на termin-стороне

Добавлены два новых экспорта в `libtermin_graphics2.so` / `Termin.Native.dll`
(заголовок `tgfx/tgfx2_interop.h`, реализация `tgfx2_gpu_ops.cpp`):

```c
// Обернуть уже существующую GL-текстуру как tgfx2 TextureHandle.
// Не копирует — handle держит GLuint и возвращает в том же виде
// в командах blit/bind. Handle id = 0 если device не OpenGL.
uint32_t tgfx2_interop_register_external_gl_texture(
    uint32_t gl_tex_id,
    uint32_t width, uint32_t height,
    int format,                 // tgfx::PixelFormat как int, см. enums.hpp
    uint32_t usage);            // tgfx::TextureUsage bitmask

// Освободить handle (GL-текстуру НЕ удаляет — хост остаётся её владельцем).
void tgfx2_interop_destroy_texture_handle(uint32_t handle_id);
```

Также уже есть поле `get_tgfx_color_tex_id` в C-структуре
`tc_render_surface_vtable` (заголовок `tc_render_surface.h:84`), но
**отсутствует в C#-копии** `RenderSurfaceVTable` (`TerminCore.cs:674-690`).
Из-за этого layout на C#-стороне на один указатель короче. Сейчас
работает только потому, что поле опциональное и termin fallback'ит на
legacy путь — но любой сдвиг в структуре приведёт к катастрофе.

---

## Что нужно поменять в `termin-csharp` (SDK-библиотека)

### 1. Добавить delegate и поле в VTable

**Файл:** `termin-csharp/Termin.Native/TerminCore.cs`

Добавить рядом с остальными делегатами (~строка 672):

```csharp
[UnmanagedFunctionPointer(CallingConvention.Cdecl)]
public delegate uint RenderSurfaceGetTgfxColorTexIdDelegate(IntPtr surface);
```

В `RenderSurfaceVTable` (~строка 674) добавить поле **в конец**, чтобы
совпасть с порядком в C:

```csharp
[StructLayout(LayoutKind.Sequential)]
public struct RenderSurfaceVTable
{
    public IntPtr get_framebuffer;
    public IntPtr get_size;
    public IntPtr make_current;
    public IntPtr swap_buffers;
    public IntPtr context_key;
    public IntPtr poll_events;
    public IntPtr get_window_size;
    public IntPtr should_close;
    public IntPtr set_should_close;
    public IntPtr get_cursor_pos;
    public IntPtr destroy;
    public IntPtr share_group_key;
    public IntPtr get_tgfx_color_tex_id;  // ← добавить
}
```

### 2. Добавить P/Invoke для interop функций

В `TerminCore.cs` рядом с блоком Render Surface:

```csharp
// ========================================================================
// tgfx2 interop — external GL texture ↔ tgfx2 TextureHandle
// ========================================================================

[DllImport(DLL, EntryPoint = "tgfx2_interop_register_external_gl_texture")]
public static extern uint Tgfx2RegisterExternalGlTexture(
    uint glTexId, uint width, uint height, int format, uint usage);

[DllImport(DLL, EntryPoint = "tgfx2_interop_destroy_texture_handle")]
public static extern void Tgfx2DestroyTextureHandle(uint handleId);
```

Плюс enum-ы, соответствующие `tgfx::PixelFormat` и `tgfx::TextureUsage`
из `termin-graphics/include/tgfx2/enums.hpp`. Минимальный набор для
текущей задачи:

```csharp
public enum Tgfx2PixelFormat : int
{
    RGBA8_UNorm = /* см. enums.hpp, обычно 1 */,
    // … остальные по надобности
}

[Flags]
public enum Tgfx2TextureUsage : uint
{
    None               = 0,
    Sampled            = 1 << 0,
    Storage            = 1 << 1,
    ColorAttachment    = 1 << 2,
    DepthStencilAttachment = 1 << 3,
    CopySrc            = 1 << 4,
    CopyDst            = 1 << 5,
}
```

**Важно:** посмотри актуальные значения в `tgfx2/enums.hpp` на момент
сборки SDK — если они поменяются, enum'ы надо будет подправить в тандеме.

---

## Что нужно поменять в `WpfRenderSurface.cs`

**Файл:** `AppsUIMonorepo/TerminSceneApp/Infrastructure/WpfRenderSurface.cs`
(аналогично в Alliance — `VdegNexus/Alliance/Alliance/Infrastructure/` если
есть свой клон; если обёртка шарится через TerminSdk — править один раз).

### 1. Добавить поля для handle-кеша

```csharp
private uint _cachedFboId;
private uint _cachedColorTexId;          // ← GL color attachment id
private int  _cachedWidth;
private int  _cachedHeight;
private uint _cachedTgfxHandle;          // ← tgfx2 TextureHandle id
private TerminCore.RenderSurfaceGetTgfxColorTexIdDelegate? _getTgfxColorTexId;
```

### 2. Обновить `UpdateFramebuffer` чтобы он ещё и вытаскивал
color attachment и (пере)регистрировал tgfx2 handle

```csharp
public void UpdateFramebuffer()
{
    GL.GetInteger(GetPName.FramebufferBinding, out int fboId);
    _cachedFboId = (uint)fboId;

    // Color attachment 0 — это цветовая текстура FBO, которую движок
    // должен получить как tgfx2 TextureHandle.
    GL.GetFramebufferAttachmentParameter(
        FramebufferTarget.Framebuffer,
        FramebufferAttachment.ColorAttachment0,
        FramebufferParameterName.FramebufferAttachmentObjectName,
        out int colorTexId);

    int w = (int)_control.ActualWidth;
    int h = (int)_control.ActualHeight;

    // Пересоздаём handle только когда идентичность изменилась —
    // чтобы не плодить записи в tgfx2 handle pool.
    bool changed = colorTexId != _cachedColorTexId
                || w != _cachedWidth || h != _cachedHeight;
    if (changed)
    {
        if (_cachedTgfxHandle != 0)
        {
            TerminCore.Tgfx2DestroyTextureHandle(_cachedTgfxHandle);
            _cachedTgfxHandle = 0;
        }
        if (colorTexId != 0 && w > 0 && h > 0)
        {
            _cachedTgfxHandle = TerminCore.Tgfx2RegisterExternalGlTexture(
                (uint)colorTexId,
                (uint)w, (uint)h,
                (int)TerminCore.Tgfx2PixelFormat.RGBA8_UNorm,
                (uint)(TerminCore.Tgfx2TextureUsage.Sampled
                     | TerminCore.Tgfx2TextureUsage.ColorAttachment
                     | TerminCore.Tgfx2TextureUsage.CopyDst));
        }
        _cachedColorTexId = (uint)colorTexId;
        _cachedWidth = w;
        _cachedHeight = h;
    }
}
```

### 3. Добавить callback и зарегистрировать в vtable

```csharp
// В конструктор рядом с остальными делегатами:
_getTgfxColorTexId = GetTgfxColorTexIdCallback;

// В инициализацию _vtable:
_vtable = new TerminCore.RenderSurfaceVTable
{
    // … всё как раньше …
    share_group_key = Marshal.GetFunctionPointerForDelegate(_shareGroupKey),
    get_tgfx_color_tex_id = Marshal.GetFunctionPointerForDelegate(_getTgfxColorTexId),
};

// Callback:
private static uint GetTgfxColorTexIdCallback(IntPtr surface)
    => GetSelf(surface)?._cachedTgfxHandle ?? 0;
```

### 4. Освободить handle в `Dispose`

```csharp
public void Dispose()
{
    if (_disposed) return;
    _disposed = true;
    _control.MouseMove -= OnMouseMove;
    if (_cachedTgfxHandle != 0)
    {
        TerminCore.Tgfx2DestroyTextureHandle(_cachedTgfxHandle);
        _cachedTgfxHandle = 0;
    }
    if (_surfacePtr != IntPtr.Zero) { TerminCore.RenderSurfaceFreeExternal(_surfacePtr); _surfacePtr = IntPtr.Zero; }
    if (_selfHandle.IsAllocated) _selfHandle.Free();
    GC.SuppressFinalize(this);
}
```

---

## Проверка

1. **Собрать и запустить на OpenGL как сейчас.** Картинка должна работать
   точно так же как до изменений — функциональной разницы не видно, потому
   что оба пути (через `display_color_tex` и через `blit_to_external_target`)
   дают идентичный результат на GL.
2. **Убедиться что активна новая ветка.** Самый простой способ: временно
   добавить `tc_log` в `RenderingManager::present_display` внутри ветки
   `if (display_color_tex)` / `else` и посмотреть какая сработала. Должна
   срабатывать первая.
3. **Проверить отсутствие утечек handle'ов.** После серии resize'ов и
   reload'ов окна в логе не должно расти число `textures_.add` (если
   добавить debug-counter в `OpenGLRenderDevice::register_external_texture`).

---

## Что это разблокирует

- `blit_to_external_target` становится **мёртвым кодом** для всех мигрированных
  surface'ов. Можно будет (осторожно) выпиливать целиком после того как и Qt
  editor, и Python SDL surface'ы тоже пройдут аналогичную миграцию.
- `present_display` в `rendering_manager.cpp` и `pull_rendering_manager.cpp`
  работает единым backend-neutral путём — нет специального case'а для GL.
- Vulkan-интеграция (Phase 2, ниже) получает одну точку состыковки —
  `get_tgfx_color_tex_id` просто возвращает другой handle (обёрнутый
  VkImage вместо GL texture). Весь остальной engine-код не меняется.

---

## Phase 2 — WPF + Vulkan через D3D11 shared handle (следующая итерация)

**Не делается в этой итерации.** Набросок архитектуры для планирования:

1. WPF-сторона переходит с `GLWpfControl` на **D3D11Image** (через
   `SharpDX.WPF` / `Microsoft.Wpf.Interop.DirectX` / кастомный контрол).
   Это единственный встроенный в WPF способ показать аппаратно-ускоренный
   кадр от Vulkan.
2. Termin Vulkan-бэкенд получает новый метод на `IRenderDevice`:

   ```cpp
   // Экспортировать VkImage как Windows DXGI-совместимый shared handle.
   // Работает только на Vulkan backend и только с текстурами, созданными
   // с `VkExternalMemoryImageCreateInfo{handleTypes = OPAQUE_WIN32}`.
   uintptr_t export_texture_win32_handle(TextureHandle tex);
   ```

   Реализация: `VK_KHR_external_memory_win32` + `vkGetMemoryWin32HandleKHR`.
3. C# импортит handle как `ID3D11Texture2D` через
   `ID3D11Device1::OpenSharedResource1`, кормит в `D3D11Image`.
4. `WpfRenderSurface.get_tgfx_color_tex_id` возвращает **уже созданный
   в termin** tgfx2 TextureHandle (шаг 2 даёт только handle, саму текстуру
   термин создал сам через `create_texture(usage=Sampled|ColorAttachment|CopyDst)`).

Итого на Phase 2 изменения локализованы в:
- `WpfRenderSurface` — меняется внутренняя реализация, публичный API
  `UpdateFramebuffer` / `SurfacePtr` остаётся прежним.
- Termin: добавляется `export_texture_win32_handle` на Vulkan device.
- Engine-passes (color, depth, shadow, id, bloom, tonemap, …) **не
  трогаем** — они уже backend-neutral.

---

## Порядок применения на Windows-машине

1. Собрать свежий SDK termin'а (tgfx2 с новыми interop-экспортами).
2. Обновить `termin-csharp/Termin.Native/TerminCore.cs` (пункт 1-2 выше).
3. Пересобрать `Termin.Native.dll`, положить в `VdegNexus/TerminSdk/lib/`.
4. Обновить `WpfRenderSurface.cs` (пункт 3 выше) — в TerminSceneApp и
   везде, где используется копия.
5. Перебилдить приложения, прогнать визуальный smoke-test.
6. (Опционально) временный debug-лог чтобы убедиться что `display_color_tex`
   ветка сработала.

Если smoke-test проходит — Phase 1 завершена.
