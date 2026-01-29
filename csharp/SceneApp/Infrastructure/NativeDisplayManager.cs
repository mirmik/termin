using Termin.Native;
using WpfInput = SceneApp.Input;

namespace SceneApp.Infrastructure;

public class NativeDisplayManager : IDisposable
{
    private readonly WpfRenderSurface _renderSurface;
    private readonly GlWpfBackend _backend;
    private IntPtr _displayPtr;
    private IntPtr _simpleInputManagerPtr;
    private IntPtr _inputManagerPtr;
    private bool _disposed;

    public IntPtr DisplayPtr => _displayPtr;
    public IntPtr InputManagerPtr => _inputManagerPtr;

    public NativeDisplayManager(WpfRenderSurface renderSurface, GlWpfBackend backend, string name = "WpfDisplay")
    {
        _renderSurface = renderSurface;
        _backend = backend;

        _displayPtr = TerminCore.DisplayNew(name, _renderSurface.SurfacePtr);
        if (_displayPtr == IntPtr.Zero)
            throw new Exception("Failed to create tc_display");

        _simpleInputManagerPtr = TerminCore.SimpleInputManagerNew(_displayPtr);
        if (_simpleInputManagerPtr == IntPtr.Zero)
        {
            TerminCore.DisplayFree(_displayPtr);
            _displayPtr = IntPtr.Zero;
            throw new Exception("Failed to create tc_simple_input_manager");
        }

        _inputManagerPtr = TerminCore.SimpleInputManagerBase(_simpleInputManagerPtr);

        _backend.OnMouseButton += OnMouseButton;
        _backend.OnMouseMove += OnMouseMove;
        _backend.OnScroll += OnScroll;
        _backend.OnKey += OnKey;
    }

    public void AddViewport(IntPtr viewportPtr)
    {
        if (_displayPtr != IntPtr.Zero && viewportPtr != IntPtr.Zero)
            TerminCore.DisplayAddViewport(_displayPtr, viewportPtr);
    }

    public void RemoveViewport(IntPtr viewportPtr)
    {
        if (_displayPtr != IntPtr.Zero && viewportPtr != IntPtr.Zero)
            TerminCore.DisplayRemoveViewport(_displayPtr, viewportPtr);
    }

    private void OnMouseButton(WpfInput.MouseButtonEvent evt)
    {
        if (_inputManagerPtr == IntPtr.Zero) return;
        TerminCore.InputManagerDispatchMouseButton(_inputManagerPtr, (int)evt.Button, (int)evt.Action, (int)evt.Modifiers);
    }

    private void OnMouseMove(WpfInput.MouseMoveEvent evt)
    {
        if (_inputManagerPtr == IntPtr.Zero) return;
        TerminCore.InputManagerDispatchMouseMove(_inputManagerPtr, evt.X, evt.Y);
    }

    private void OnScroll(WpfInput.ScrollEvent evt)
    {
        if (_inputManagerPtr == IntPtr.Zero) return;
        TerminCore.InputManagerDispatchScroll(_inputManagerPtr, evt.OffsetX, evt.OffsetY, (int)evt.Modifiers);
    }

    private void OnKey(WpfInput.KeyEvent evt)
    {
        if (_inputManagerPtr == IntPtr.Zero) return;
        TerminCore.InputManagerDispatchKey(_inputManagerPtr, (int)evt.Key, evt.ScanCode, (int)evt.Action, (int)evt.Modifiers);
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;

        _backend.OnMouseButton -= OnMouseButton;
        _backend.OnMouseMove -= OnMouseMove;
        _backend.OnScroll -= OnScroll;
        _backend.OnKey -= OnKey;

        if (_simpleInputManagerPtr != IntPtr.Zero)
        {
            TerminCore.SimpleInputManagerFree(_simpleInputManagerPtr);
            _simpleInputManagerPtr = IntPtr.Zero;
            _inputManagerPtr = IntPtr.Zero;
        }

        if (_displayPtr != IntPtr.Zero)
        {
            TerminCore.DisplayFree(_displayPtr);
            _displayPtr = IntPtr.Zero;
        }

        GC.SuppressFinalize(this);
    }

    ~NativeDisplayManager() => Dispose();
}
