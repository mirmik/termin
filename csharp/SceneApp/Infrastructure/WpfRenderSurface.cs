using System.Runtime.InteropServices;
using OpenTK.Graphics.OpenGL4;
using OpenTK.Wpf;
using Termin.Native;

namespace SceneApp.Infrastructure;

public class WpfRenderSurface : IDisposable
{
    private readonly GLWpfControl _control;
    private IntPtr _surfacePtr;
    private GCHandle _selfHandle;
    private bool _disposed;
    private double _cursorX;
    private double _cursorY;
    private bool _shouldClose;
    private uint _cachedFboId;

    private TerminCore.RenderSurfaceGetFramebufferDelegate? _getFramebuffer;
    private TerminCore.RenderSurfaceGetSizeDelegate? _getSize;
    private TerminCore.RenderSurfaceMakeCurrentDelegate? _makeCurrent;
    private TerminCore.RenderSurfaceSwapBuffersDelegate? _swapBuffers;
    private TerminCore.RenderSurfaceContextKeyDelegate? _contextKey;
    private TerminCore.RenderSurfacePollEventsDelegate? _pollEvents;
    private TerminCore.RenderSurfaceGetWindowSizeDelegate? _getWindowSize;
    private TerminCore.RenderSurfaceShouldCloseDelegate? _shouldCloseCallback;
    private TerminCore.RenderSurfaceSetShouldCloseDelegate? _setShouldClose;
    private TerminCore.RenderSurfaceGetCursorPosDelegate? _getCursorPos;
    private TerminCore.RenderSurfaceDestroyDelegate? _destroy;
    private TerminCore.RenderSurfaceVTable _vtable;

    public IntPtr SurfacePtr => _surfacePtr;

    public void UpdateFramebuffer()
    {
        GL.GetInteger(GetPName.FramebufferBinding, out int fboId);
        _cachedFboId = (uint)fboId;
    }

    public WpfRenderSurface(GLWpfControl control)
    {
        _control = control;
        _selfHandle = GCHandle.Alloc(this);

        _getFramebuffer = GetFramebufferCallback;
        _getSize = GetSizeCallback;
        _makeCurrent = MakeCurrentCallback;
        _swapBuffers = SwapBuffersCallback;
        _contextKey = ContextKeyCallback;
        _pollEvents = PollEventsCallback;
        _getWindowSize = GetWindowSizeCallback;
        _shouldCloseCallback = ShouldCloseCallback;
        _setShouldClose = SetShouldCloseCallback;
        _getCursorPos = GetCursorPosCallback;
        _destroy = DestroyCallback;

        _vtable = new TerminCore.RenderSurfaceVTable
        {
            get_framebuffer = Marshal.GetFunctionPointerForDelegate(_getFramebuffer),
            get_size = Marshal.GetFunctionPointerForDelegate(_getSize),
            make_current = Marshal.GetFunctionPointerForDelegate(_makeCurrent),
            swap_buffers = Marshal.GetFunctionPointerForDelegate(_swapBuffers),
            context_key = Marshal.GetFunctionPointerForDelegate(_contextKey),
            poll_events = Marshal.GetFunctionPointerForDelegate(_pollEvents),
            get_window_size = Marshal.GetFunctionPointerForDelegate(_getWindowSize),
            should_close = Marshal.GetFunctionPointerForDelegate(_shouldCloseCallback),
            set_should_close = Marshal.GetFunctionPointerForDelegate(_setShouldClose),
            get_cursor_pos = Marshal.GetFunctionPointerForDelegate(_getCursorPos),
            destroy = Marshal.GetFunctionPointerForDelegate(_destroy),
        };

        _surfacePtr = TerminCore.RenderSurfaceNewExternal(GCHandle.ToIntPtr(_selfHandle), ref _vtable);
        if (_surfacePtr == IntPtr.Zero)
        {
            _selfHandle.Free();
            throw new Exception("Failed to create tc_render_surface");
        }

        _control.MouseMove += OnMouseMove;
    }

    private void OnMouseMove(object sender, System.Windows.Input.MouseEventArgs e)
    {
        var pos = e.GetPosition(_control);
        _cursorX = pos.X;
        _cursorY = pos.Y;
    }

    private static WpfRenderSurface? GetSelf(IntPtr surfacePtr)
    {
        if (surfacePtr == IntPtr.Zero) return null;
        IntPtr bodyPtr = Marshal.ReadIntPtr(surfacePtr, IntPtr.Size);
        if (bodyPtr == IntPtr.Zero) return null;
        var handle = GCHandle.FromIntPtr(bodyPtr);
        return handle.Target as WpfRenderSurface;
    }

    private static uint GetFramebufferCallback(IntPtr surface) => GetSelf(surface)?._cachedFboId ?? 0;

    private static void GetSizeCallback(IntPtr surface, out int width, out int height)
    {
        var self = GetSelf(surface);
        if (self != null) { width = (int)self._control.ActualWidth; height = (int)self._control.ActualHeight; }
        else { width = 0; height = 0; }
    }

    private static void MakeCurrentCallback(IntPtr surface) { }
    private static void SwapBuffersCallback(IntPtr surface) { }
    private static nuint ContextKeyCallback(IntPtr surface) => (nuint)surface;
    private static void PollEventsCallback(IntPtr surface) { }
    private static void GetWindowSizeCallback(IntPtr surface, out int width, out int height) => GetSizeCallback(surface, out width, out height);
    private static bool ShouldCloseCallback(IntPtr surface) => GetSelf(surface)?._shouldClose ?? false;
    private static void SetShouldCloseCallback(IntPtr surface, bool value) { var self = GetSelf(surface); if (self != null) self._shouldClose = value; }

    private static void GetCursorPosCallback(IntPtr surface, out double x, out double y)
    {
        var self = GetSelf(surface);
        if (self != null) { x = self._cursorX; y = self._cursorY; }
        else { x = 0; y = 0; }
    }

    private static void DestroyCallback(IntPtr surface) { }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        _control.MouseMove -= OnMouseMove;
        if (_surfacePtr != IntPtr.Zero) { TerminCore.RenderSurfaceFreeExternal(_surfacePtr); _surfacePtr = IntPtr.Zero; }
        if (_selfHandle.IsAllocated) _selfHandle.Free();
        GC.SuppressFinalize(this);
    }

    ~WpfRenderSurface() => Dispose();
}
