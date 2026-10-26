using System;
using System.Collections.Concurrent;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

namespace Termin.Native;

public enum NativeUiPointerEventType
{
    Move, Down, Up, Wheel, Enter, Leave, Cancel
}
public enum NativeUiPointerCancelReason
{
    Explicit, CaptureReplaced, SubtreeIneffective, ModalOpened, WindowFocusLost, HostCaptureLost
}
public enum NativeUiCursor
{
    Inherit, Default, Text, Hand, Crosshair, Move, ResizeHorizontal, ResizeVertical, ResizeNwse, ResizeNesw
}
[Flags]
public enum NativeUiModifiers
{
    None = 0, Shift = 1, Control = 2, Alt = 4, Super = 8
}
public enum NativeUiKeyEventType
{
    Down, Up
}
[StructLayout(LayoutKind.Sequential)]
public struct NativeUiPointerEvent
{
    public NativeUiPointerEventType Type;
    public float X, Y;
    public int Button;
    public uint ClickCount;
    public NativeUiModifiers Modifiers;
    public float WheelX, WheelY;
    public NativeUiPointerCancelReason CancelReason;
}
[StructLayout(LayoutKind.Sequential)]
public struct NativeUiKeyEvent
{
    public NativeUiKeyEventType Type;
    public int Key, Scancode;
    public NativeUiModifiers Modifiers;
    [MarshalAs(UnmanagedType.I1)] public bool Repeat;
}

/// <summary>Synchronous platform callbacks on the renderer UI thread.</summary>
public interface INativeDocumentPlatformServices
{
    bool SetTextInputEnabled(bool enabled);
    string GetClipboardText();
    bool SetClipboardText(string text);
    bool SetCursor(NativeUiCursor cursor);
}

/// <summary>
/// Renders a borrowed native document using the borrowed GPU host. Its output
/// uses DisplayLinear; present it with the existing D3DImage presentation bridge.
/// Dispose before the document and GPU host. The renderer owns no event loop.
/// </summary>
public sealed class NativeDocumentRenderer : IDisposable
{
    private static long _nextToken;
    private static readonly ConcurrentDictionary<IntPtr, NativeDocumentRenderer> Live = new();
    private static readonly NativeDocumentRendererInterop.SetTextInput TextInputCallback = SetTextInput;
    private static readonly NativeDocumentRendererInterop.CopyClipboard ClipboardGetCallback = CopyClipboard;
    private static readonly NativeDocumentRendererInterop.SetClipboard ClipboardSetCallback = SetClipboard;
    private static readonly NativeDocumentRendererInterop.SetCursor CursorCallback = SetCursor;
    private readonly GpuHost _host;
    private readonly NativeUiDocument _document;
    private readonly INativeDocumentPlatformServices _platform;
    private readonly IntPtr _token;
    private NativeUiHandle _handle;
    private int _callbackDepth;
    private bool _disposed;

    public NativeDocumentRenderer(GpuHost host, NativeUiDocument document, string fontPath,
        INativeDocumentPlatformServices? platform = null, int fontSize = 14)
    {
        _host = host ?? throw new ArgumentNullException(nameof(host));
        _document = document ?? throw new ArgumentNullException(nameof(document));
        _platform = platform ?? new MemoryPlatformServices();
        if (fontPath is null)
            throw new ArgumentNullException(nameof(fontPath));
        if (fontPath.IndexOf('\0') >= 0)
            throw new ArgumentException("Font path must not contain NUL.", nameof(fontPath));
        if (fontSize <= 0)
            throw new ArgumentOutOfRangeException(nameof(fontSize));
        _document.AcquireBorrower();
        _token = new IntPtr(Interlocked.Increment(ref _nextToken));
        Live[_token] = this;
        try
        {
            if (GpuHost.getCPtr(_host).Handle == IntPtr.Zero)
                throw new ObjectDisposedException(nameof(GpuHost));
            var config = new NativeDocumentRendererInterop.Config
            {
                StructSize = (nuint)Marshal.SizeOf<NativeDocumentRendererInterop.Config>(),
                FontPath = fontPath,
                FontSize = fontSize,
                Width = 1,
                Height = 1,
                DensityScale = 1,
                Userdata = _token,
                SetTextInput = TextInputCallback,
                CopyClipboard = ClipboardGetCallback,
                SetClipboard = ClipboardSetCallback,
                SetCursor = CursorCallback
            };
            _handle = NativeDocumentRendererInterop.Create(_document.Handle, new IntPtr(unchecked((long)_host.native_graphics_host())), ref config);
            if (!_handle.IsValid)
                throw new InvalidOperationException("Failed to create native document renderer. See native log.");
            ThrowIfCallbackFailed();
        }
        catch
        {
            if (_handle.IsValid)
                NativeDocumentRendererInterop.Destroy(_handle);
            Live.TryRemove(_token, out _);
            _document.ReleaseBorrower();
            _disposed = true;
            throw;
        }
    }
    public NativeUiDocument Document => _document;
    public Exception? LastCallbackError
    {
        get; private set;
    }
    public bool HasPointerCapture
    {
        get
        {
            VerifyAccess();
            return NativeDocumentRendererInterop.HasPointerCapture(_handle);
        }
    }
    public bool RepaintRequested
    {
        get
        {
            VerifyAccess();
            return NativeDocumentRendererInterop.RepaintRequested(_handle);
        }
    }

    public void SetMetrics(int width, int height, float densityScale = 1)
    {
        VerifyAccess();
        Check(NativeDocumentRendererInterop.SetMetrics(_handle, width, height, densityScale), "set metrics");
    }
    public uint RenderToTextureHandleId(int width, int height, float densityScale = 1)
    {
        SetMetrics(width, height, densityScale);
        Check(NativeDocumentRendererInterop.Render(_handle, out uint texture), "render");
        ThrowIfCallbackFailed();
        return texture;
    }
    public bool DispatchPointer(NativeUiPointerEvent pointer)
    {
        VerifyAccess();
        Check(NativeDocumentRendererInterop.DispatchPointer(_handle, ref pointer, out int result), "dispatch pointer");
        ThrowIfCallbackFailed();
        return result != 0;
    }
    public bool DispatchKey(NativeUiKeyEvent key)
    {
        VerifyAccess();
        Check(NativeDocumentRendererInterop.DispatchKey(_handle, ref key, out int result), "dispatch key");
        ThrowIfCallbackFailed();
        return result != 0;
    }
    public bool DispatchText(string text)
    {
        VerifyAccess();
        if (text is null)
            throw new ArgumentNullException(nameof(text));
        if (text.IndexOf('\0') >= 0)
            throw new ArgumentException("Input text must not contain NUL.", nameof(text));
        Check(NativeDocumentRendererInterop.DispatchText(_handle, text, out int result), "dispatch text");
        ThrowIfCallbackFailed();
        return result != 0;
    }
    public void CancelInteraction(NativeUiPointerCancelReason reason = NativeUiPointerCancelReason.Explicit)
    {
        VerifyAccess();
        Check(NativeDocumentRendererInterop.CancelInteraction(_handle, reason), "cancel interaction");
        ThrowIfCallbackFailed();
    }
    public void SetFocus(bool focused)
    {
        VerifyAccess();
        Check(NativeDocumentRendererInterop.SetFocus(_handle, focused), "set focus");
        ThrowIfCallbackFailed();
    }
    public void RequestRepaint()
    {
        VerifyAccess();
        Check(NativeDocumentRendererInterop.RequestRepaint(_handle), "request repaint");
    }
    public void ThrowIfCallbackFailed()
    {
        if (LastCallbackError is Exception error)
        {
            LastCallbackError = null;
            throw new InvalidOperationException("A native document platform callback failed. See error log.", error);
        }
    }
    private void VerifyAccess()
    {
        if (_disposed)
            throw new ObjectDisposedException(nameof(NativeDocumentRenderer));
        _document.VerifyAccess();
        if (GpuHost.getCPtr(_host).Handle == IntPtr.Zero)
            throw new ObjectDisposedException(nameof(GpuHost));
        if (_callbackDepth != 0)
            throw new InvalidOperationException("Do not reenter or dispose the native document renderer from a platform callback.");
    }
    private void Check(bool success, string operation)
    {
        ThrowIfCallbackFailed();
        _document.ThrowPendingCallbackExceptions();
        if (success)
            return;
        nuint size = NativeDocumentRendererInterop.CopyError(_handle, IntPtr.Zero, 0);
        string message = "";
        if (size > 0)
        {
            IntPtr buffer = Marshal.AllocHGlobal(checked((int)size));
            try
            {
                NativeDocumentRendererInterop.CopyError(_handle, buffer, size);
                message = Marshal.PtrToStringUTF8(buffer) ?? "";
            }
            finally
            {
                Marshal.FreeHGlobal(buffer);
            }
        }
        throw new InvalidOperationException($"Native document renderer failed to {operation}: {message}. See native log.");
    }
    public void Dispose()
    {
        if (_disposed)
            return;
        VerifyAccess();
        if (!NativeDocumentRendererInterop.Destroy(_handle))
            Check(false, "destroy");
        Live.TryRemove(_token, out _);
        _document.ReleaseBorrower();
        _disposed = true;
        GC.SuppressFinalize(this);
        // Destroy can invoke platform callbacks. Native ownership has already
        // ended even if one of those managed callbacks reported a failure.
        ThrowIfCallbackFailed();
        _document.ThrowPendingCallbackExceptions();
    }
    private T RunCallback<T>(Func<T> callback, T failure)
    {
        ++_callbackDepth;
        try
        {
            return callback();
        }
        catch (Exception error)
        {
            LastCallbackError = error;
            Console.Error.WriteLine($"[Termin.Native.DocumentRenderer] Managed platform callback failed: {error}");
            return failure;
        }
        finally
        {
            --_callbackDepth;
        }
    }
    private static bool SetTextInput(IntPtr token, bool enabled) => Live.TryGetValue(token, out var renderer) && renderer.RunCallback(() => renderer._platform.SetTextInputEnabled(enabled), false);
    private static bool SetCursor(IntPtr token, NativeUiCursor cursor) => Live.TryGetValue(token, out var renderer) && renderer.RunCallback(() => renderer._platform.SetCursor(cursor), false);
    private static bool SetClipboard(IntPtr token, IntPtr text, nuint length)
    {
        return Live.TryGetValue(token, out var renderer) && renderer.RunCallback(() =>
        {
            int count = checked((int)length);
            byte[] bytes = new byte[count];
            if (count > 0)
                Marshal.Copy(text, bytes, 0, count);
            return renderer._platform.SetClipboardText(Encoding.UTF8.GetString(bytes));
        }, false);
    }
    private static nuint CopyClipboard(IntPtr token, IntPtr buffer, nuint capacity)
    {
        if (!Live.TryGetValue(token, out var renderer))
            return 0;
        return renderer.RunCallback(() =>
        {
            string text = renderer._platform.GetClipboardText();
            if (text.IndexOf('\0') >= 0)
                throw new ArgumentException("Clipboard text must not contain NUL.");
            byte[] bytes = Encoding.UTF8.GetBytes(text);
            if (buffer != IntPtr.Zero && capacity > 0)
            {
                int count = Math.Min(bytes.Length, checked((int)capacity) - 1);
                Marshal.Copy(bytes, 0, buffer, count);
                Marshal.WriteByte(buffer, count, 0);
            }
            return (nuint)bytes.Length + 1;
        }, (nuint)0);
    }
    private sealed class MemoryPlatformServices : INativeDocumentPlatformServices
    {
        private string _clipboard = "";
        public bool SetTextInputEnabled(bool enabled) => true;
        public string GetClipboardText() => _clipboard;
        public bool SetClipboardText(string text)
        {
            _clipboard = text;
            return true;
        }
        public bool SetCursor(NativeUiCursor cursor) => true;
    }
}

internal static class NativeDocumentRendererInterop
{
    private const string Dll = "termin_gui_native_document_renderer";
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)][return: MarshalAs(UnmanagedType.I1)] internal delegate bool SetTextInput(IntPtr userdata, [MarshalAs(UnmanagedType.I1)] bool enabled);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)] internal delegate nuint CopyClipboard(IntPtr userdata, IntPtr buffer, nuint capacity);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)][return: MarshalAs(UnmanagedType.I1)] internal delegate bool SetClipboard(IntPtr userdata, IntPtr text, nuint length);
    [UnmanagedFunctionPointer(CallingConvention.Cdecl)][return: MarshalAs(UnmanagedType.I1)] internal delegate bool SetCursor(IntPtr userdata, NativeUiCursor cursor);
    [StructLayout(LayoutKind.Sequential)]
    internal struct Config
    {
        internal nuint StructSize;
        [MarshalAs(UnmanagedType.LPUTF8Str)] internal string FontPath;
        internal int FontSize, Width, Height;
        internal float DensityScale;
        internal IntPtr Userdata;
        internal SetTextInput SetTextInput;
        internal CopyClipboard CopyClipboard;
        internal SetClipboard SetClipboard;
        internal SetCursor SetCursor;
    }
    [DllImport(Dll, EntryPoint = "tc_document_renderer_create", CallingConvention = CallingConvention.Cdecl)] internal static extern NativeUiHandle Create(NativeUiHandle document, IntPtr graphics, ref Config config);
    [DllImport(Dll, EntryPoint = "tc_document_renderer_destroy", CallingConvention = CallingConvention.Cdecl)][return: MarshalAs(UnmanagedType.I1)] internal static extern bool Destroy(NativeUiHandle renderer);
    [DllImport(Dll, EntryPoint = "tc_document_renderer_set_metrics", CallingConvention = CallingConvention.Cdecl)][return: MarshalAs(UnmanagedType.I1)] internal static extern bool SetMetrics(NativeUiHandle renderer, int width, int height, float density);
    [DllImport(Dll, EntryPoint = "tc_document_renderer_render", CallingConvention = CallingConvention.Cdecl)][return: MarshalAs(UnmanagedType.I1)] internal static extern bool Render(NativeUiHandle renderer, out uint texture);
    [DllImport(Dll, EntryPoint = "tc_document_renderer_dispatch_pointer", CallingConvention = CallingConvention.Cdecl)][return: MarshalAs(UnmanagedType.I1)] internal static extern bool DispatchPointer(NativeUiHandle renderer, ref NativeUiPointerEvent pointer, out int result);
    [DllImport(Dll, EntryPoint = "tc_document_renderer_dispatch_key", CallingConvention = CallingConvention.Cdecl)][return: MarshalAs(UnmanagedType.I1)] internal static extern bool DispatchKey(NativeUiHandle renderer, ref NativeUiKeyEvent key, out int result);
    [DllImport(Dll, EntryPoint = "tc_document_renderer_dispatch_text", CallingConvention = CallingConvention.Cdecl)][return: MarshalAs(UnmanagedType.I1)] internal static extern bool DispatchText(NativeUiHandle renderer, [MarshalAs(UnmanagedType.LPUTF8Str)] string text, out int result);
    [DllImport(Dll, EntryPoint = "tc_document_renderer_cancel_interaction", CallingConvention = CallingConvention.Cdecl)][return: MarshalAs(UnmanagedType.I1)] internal static extern bool CancelInteraction(NativeUiHandle renderer, NativeUiPointerCancelReason reason);
    [DllImport(Dll, EntryPoint = "tc_document_renderer_set_focus", CallingConvention = CallingConvention.Cdecl)][return: MarshalAs(UnmanagedType.I1)] internal static extern bool SetFocus(NativeUiHandle renderer, [MarshalAs(UnmanagedType.I1)] bool focus);
    [DllImport(Dll, EntryPoint = "tc_document_renderer_has_pointer_capture", CallingConvention = CallingConvention.Cdecl)][return: MarshalAs(UnmanagedType.I1)] internal static extern bool HasPointerCapture(NativeUiHandle renderer);
    [DllImport(Dll, EntryPoint = "tc_document_renderer_repaint_requested", CallingConvention = CallingConvention.Cdecl)][return: MarshalAs(UnmanagedType.I1)] internal static extern bool RepaintRequested(NativeUiHandle renderer);
    [DllImport(Dll, EntryPoint = "tc_document_renderer_request_repaint", CallingConvention = CallingConvention.Cdecl)][return: MarshalAs(UnmanagedType.I1)] internal static extern bool RequestRepaint(NativeUiHandle renderer);
    [DllImport(Dll, EntryPoint = "tc_document_renderer_copy_last_error", CallingConvention = CallingConvention.Cdecl)] internal static extern nuint CopyError(NativeUiHandle renderer, IntPtr buffer, nuint capacity);
}
