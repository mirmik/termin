using Termin.Native;
using WpfInput = Termin.WpfTest.Input;

namespace Termin.WpfTest;

/// <summary>
/// Manages tc_display and tc_simple_input_manager for WPF.
///
/// Flow:
/// 1. WpfRenderSurface wraps GLWpfControl as tc_render_surface
/// 2. tc_display owns the surface and viewport list
/// 3. tc_simple_input_manager routes events to scene InputComponents
/// 4. GlWpfBackend events are forwarded to tc_input_manager_dispatch_*
/// </summary>
public class NativeDisplayManager : IDisposable
{
    private readonly WpfRenderSurface _renderSurface;
    private readonly GlWpfBackend _backend;
    private IntPtr _displayPtr;
    private IntPtr _simpleInputManagerPtr;
    private IntPtr _inputManagerPtr;
    private bool _disposed;

    /// <summary>
    /// Native tc_display pointer.
    /// </summary>
    public IntPtr DisplayPtr => _displayPtr;

    /// <summary>
    /// Native tc_input_manager pointer.
    /// </summary>
    public IntPtr InputManagerPtr => _inputManagerPtr;

    public NativeDisplayManager(WpfRenderSurface renderSurface, GlWpfBackend backend, string name = "WpfDisplay")
    {
        _renderSurface = renderSurface;
        _backend = backend;

        // Create tc_display with render surface
        _displayPtr = TerminCore.DisplayNew(name, _renderSurface.SurfacePtr);
        if (_displayPtr == IntPtr.Zero)
        {
            throw new Exception("Failed to create tc_display");
        }

        // Create tc_simple_input_manager
        _simpleInputManagerPtr = TerminCore.SimpleInputManagerNew(_displayPtr);
        if (_simpleInputManagerPtr == IntPtr.Zero)
        {
            TerminCore.DisplayFree(_displayPtr);
            _displayPtr = IntPtr.Zero;
            throw new Exception("Failed to create tc_simple_input_manager");
        }

        // Get tc_input_manager pointer
        _inputManagerPtr = TerminCore.SimpleInputManagerBase(_simpleInputManagerPtr);

        // Subscribe to backend events
        _backend.OnMouseButton += OnMouseButton;
        _backend.OnMouseMove += OnMouseMove;
        _backend.OnScroll += OnScroll;
        _backend.OnKey += OnKey;

        Console.WriteLine($"[NativeDisplayManager] Created: display=0x{_displayPtr:X}, input_manager=0x{_inputManagerPtr:X}");
    }

    /// <summary>
    /// Add a viewport to the display.
    /// </summary>
    public void AddViewport(IntPtr viewportPtr)
    {
        if (_displayPtr != IntPtr.Zero && viewportPtr != IntPtr.Zero)
        {
            TerminCore.DisplayAddViewport(_displayPtr, viewportPtr);
        }
    }

    /// <summary>
    /// Remove a viewport from the display.
    /// </summary>
    public void RemoveViewport(IntPtr viewportPtr)
    {
        if (_displayPtr != IntPtr.Zero && viewportPtr != IntPtr.Zero)
        {
            TerminCore.DisplayRemoveViewport(_displayPtr, viewportPtr);
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

        // Free simple input manager first (it detaches from surface)
        if (_simpleInputManagerPtr != IntPtr.Zero)
        {
            TerminCore.SimpleInputManagerFree(_simpleInputManagerPtr);
            _simpleInputManagerPtr = IntPtr.Zero;
            _inputManagerPtr = IntPtr.Zero;
        }

        // Free display
        if (_displayPtr != IntPtr.Zero)
        {
            TerminCore.DisplayFree(_displayPtr);
            _displayPtr = IntPtr.Zero;
        }

        GC.SuppressFinalize(this);
    }

    ~NativeDisplayManager()
    {
        Dispose();
    }
}
