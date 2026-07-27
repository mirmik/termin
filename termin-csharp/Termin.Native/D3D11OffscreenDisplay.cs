using System;

namespace Termin.Native;

/// <summary>
/// Owns a native display and its display-owned offscreen render surface.
/// The process-wide Tgfx2Host must outlive this object.
/// </summary>
public sealed class D3D11OffscreenDisplay : IDisposable
{
    private TcDisplayHandle _handle;

    public D3D11OffscreenDisplay(
        int width,
        int height,
        string name = "D3D11OffscreenDisplay")
    {
        if (!Tgfx2Host.IsCreated)
        {
            throw new InvalidOperationException(
                "D3D11OffscreenDisplay requires an acquired Tgfx2Host.");
        }

        _handle = TerminCore.DisplayNewD3D11OffscreenCurrent(
            Math.Max(1, width), Math.Max(1, height), name);
        if (!_handle.IsValid)
        {
            throw new InvalidOperationException(
                "Failed to create the D3D11 offscreen display. See the native log.");
        }
    }

    /// <summary>Copyable, non-owning handle used by render and presentation hosts.</summary>
    public TcDisplayHandle Handle
    {
        get
        {
            ThrowIfDisposed();
            return _handle;
        }
    }

    public void AddViewport(TcViewportHandle viewport)
    {
        ThrowIfDisposed();
        if (!viewport.IsValid)
        {
            throw new ArgumentException("Viewport handle is invalid.", nameof(viewport));
        }
        TerminCore.DisplayAddViewport(_handle, viewport);
    }

    public void RemoveViewport(TcViewportHandle viewport)
    {
        if (_handle.IsValid && viewport.IsValid)
        {
            TerminCore.DisplayRemoveViewport(_handle, viewport);
        }
    }

    public void Dispose()
    {
        if (!_handle.IsValid)
        {
            return;
        }

        TcDisplayHandle handle = _handle;
        _handle = TcDisplayHandle.Invalid;
        if (!TerminCore.DisplayFree(handle))
        {
            Console.Error.WriteLine(
                $"[Termin.Native.D3D11OffscreenDisplay] Failed to free display {handle}.");
        }
    }

    private void ThrowIfDisposed()
    {
        if (!_handle.IsValid)
        {
            throw new ObjectDisposedException(nameof(D3D11OffscreenDisplay));
        }
    }
}
