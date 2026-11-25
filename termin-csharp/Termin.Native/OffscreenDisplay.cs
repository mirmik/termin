using System;

namespace Termin.Native;

/// <summary>
/// Owns a texture-backed display on the active graphics device.
/// Initialize the full runtime and acquire a D3D11 or Vulkan
/// <see cref="Tgfx2Host"/> lease before creating the display.
/// </summary>
/// <remarks>
/// Use the display on the rendering thread. Unregister it from the rendering
/// manager and dispose it before releasing the host lease or shutting down the
/// runtime. Multiple displays can borrow the same device.
/// </remarks>
public sealed class OffscreenDisplay : IDisposable
{
    private TcDisplayHandle _handle;
    private int _width;
    private int _height;

    public OffscreenDisplay(int width, int height, string? name = null)
    {
        ValidateSize(width, height);
        if (!Tgfx2Host.IsCreated)
            throw new InvalidOperationException("OffscreenDisplay requires an acquired Tgfx2Host.");

        _handle = TerminCore.DisplayNewOffscreenCurrent(width, height, name);
        if (!_handle.IsValid)
            throw new InvalidOperationException("Failed to create the offscreen display. See the native log.");
        _width = width;
        _height = height;
    }

    /// <summary>Borrowed handle for viewport attachment and rendering.</summary>
    public TcDisplayHandle Handle
    {
        get
        {
            if (!_handle.IsValid)
                throw new ObjectDisposedException(nameof(OffscreenDisplay));
            return _handle;
        }
    }

    /// <summary>Resize the display in physical pixels. Render again before reading.</summary>
    public void Resize(int width, int height)
    {
        var handle = Handle;
        ValidateSize(width, height);
        if (width == _width && height == _height)
            return;
        if (!TerminCore.DisplayResize(handle, width, height))
            throw new InvalidOperationException($"Failed to resize the offscreen display to {width}x{height}. See the native log.");
        _width = width;
        _height = height;
    }

    /// <summary>
    /// Synchronize and read the composed frame as opaque sRGB BGRA8888, top
    /// row first. The destination remains owned by the caller. Its capacity
    /// must include at least the last pixel. Row padding is preserved.
    /// </summary>
    public void ReadBgra(IntPtr destination, int rowBytes, nuint bufferBytes)
    {
        var handle = Handle;
        if (destination == IntPtr.Zero)
            throw new ArgumentNullException(nameof(destination));
        if (rowBytes <= 0)
            throw new ArgumentOutOfRangeException(nameof(rowBytes));
        if (!TerminCore.DisplayReadOffscreenBgraCurrent(handle, _width, _height,
            destination, (nuint)rowBytes, bufferBytes))
            throw new InvalidOperationException("Failed to read the offscreen display. See the native log.");
    }

    public void Dispose()
    {
        if (!_handle.IsValid)
            return;

        var handle = _handle;
        _handle = TcDisplayHandle.Invalid;
        if (!TerminCore.DisplayFree(handle))
            Console.Error.WriteLine($"[Termin.Native.OffscreenDisplay] Failed to free display {handle}.");
    }

    private static void ValidateSize(int width, int height)
    {
        if (width <= 0)
            throw new ArgumentOutOfRangeException(nameof(width));
        if (height <= 0)
            throw new ArgumentOutOfRangeException(nameof(height));
    }
}
