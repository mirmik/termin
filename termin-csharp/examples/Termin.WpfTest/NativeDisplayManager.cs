using Termin.Native;
using WpfInput = Termin.WpfTest.Input;

namespace Termin.WpfTest;

/// <summary>
/// Manages a generation handle to tc_display for WPF.
///
/// Flow:
/// 1. WpfRenderSurface wraps GLWpfControl as tc_render_surface
/// 2. tc_display owns the surface and viewport list
/// 3. tc_display_input_router routes events to viewport input managers
/// 4. GlWpfBackend events are forwarded to tc_input_manager_dispatch_*
/// </summary>
public class NativeDisplayManager : IDisposable
{
    private readonly WpfRenderSurface _renderSurface;
    private readonly GlWpfBackend _backend;
    private TcDisplayHandle _displayHandle = TcDisplayHandle.Invalid;
    private IntPtr _inputManagerPtr;
    private bool _disposed;

    /// <summary>
    /// Copyable non-owning tc_display handle.
    /// </summary>
    public TcDisplayHandle DisplayHandle => _displayHandle;

    /// <summary>
    /// Native tc_input_manager pointer.
    /// </summary>
    public IntPtr InputManagerPtr => _inputManagerPtr;

    public NativeDisplayManager(WpfRenderSurface renderSurface, GlWpfBackend backend, string name = "WpfDisplay")
    {
        _renderSurface = renderSurface;
        _backend = backend;

        // Create tc_display with render surface
        _displayHandle = TerminCore.DisplayNew(name, _renderSurface.SurfacePtr);
        if (!_displayHandle.IsValid)
        {
            throw new Exception("Failed to create tc_display");
        }

        _inputManagerPtr = TerminCore.DisplayGetInputManager(_displayHandle);
        if (_inputManagerPtr == IntPtr.Zero)
        {
            TerminCore.DisplayFree(_displayHandle);
            _displayHandle = TcDisplayHandle.Invalid;
            throw new Exception("Failed to resolve tc_display input endpoint");
        }

        // Subscribe to backend events
        _backend.OnMouseButton += OnMouseButton;
        _backend.OnMouseMove += OnMouseMove;
        _backend.OnScroll += OnScroll;
        _backend.OnKey += OnKey;

        Console.WriteLine($"[NativeDisplayManager] Created: display={_displayHandle}, input_manager=0x{_inputManagerPtr:X}");
    }

    /// <summary>
    /// Add a viewport to the display.
    /// </summary>
    public void AddViewport(TcViewportHandle viewport)
    {
        if (_displayHandle.IsValid && viewport.IsValid)
        {
            TerminCore.DisplayAddViewport(_displayHandle, viewport);
        }
    }

    /// <summary>
    /// Remove a viewport from the display.
    /// </summary>
    public void RemoveViewport(TcViewportHandle viewport)
    {
        if (_displayHandle.IsValid && viewport.IsValid)
        {
            TerminCore.DisplayRemoveViewport(_displayHandle, viewport);
        }
    }

    private void OnMouseButton(WpfInput.MouseButtonEvent evt)
    {
        if (_inputManagerPtr == IntPtr.Zero) return;

        int button = (int)evt.Button;
        int action = (int)evt.Action;
        int mods = (int)evt.Modifiers;

        TerminCore.InputManagerDispatchMouseButton(_inputManagerPtr, button, action, mods);
    }

    private void OnMouseMove(WpfInput.MouseMoveEvent evt)
    {
        if (_inputManagerPtr == IntPtr.Zero) return;

        TerminCore.InputManagerDispatchMouseMove(_inputManagerPtr, evt.X, evt.Y);
    }

    private void OnScroll(WpfInput.ScrollEvent evt)
    {
        if (_inputManagerPtr == IntPtr.Zero) return;

        int mods = (int)evt.Modifiers;

        TerminCore.InputManagerDispatchScroll(_inputManagerPtr, evt.OffsetX, evt.OffsetY, mods);
    }

    private void OnKey(WpfInput.KeyEvent evt)
    {
        if (_inputManagerPtr == IntPtr.Zero) return;

        int key = (int)evt.Key;
        int scancode = evt.ScanCode;
        int action = (int)evt.Action;
        int mods = (int)evt.Modifiers;

        TerminCore.InputManagerDispatchKey(_inputManagerPtr, key, scancode, action, mods);
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;

        // Unsubscribe from events
        _backend.OnMouseButton -= OnMouseButton;
        _backend.OnMouseMove -= OnMouseMove;
        _backend.OnScroll -= OnScroll;
        _backend.OnKey -= OnKey;

        _inputManagerPtr = IntPtr.Zero;
        if (_displayHandle.IsValid)
        {
            TerminCore.DisplayFree(_displayHandle);
            _displayHandle = TcDisplayHandle.Invalid;
        }

        GC.SuppressFinalize(this);
    }

}
