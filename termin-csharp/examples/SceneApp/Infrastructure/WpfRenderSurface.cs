using System.Runtime.InteropServices;
using OpenTK.Wpf;
using Termin.Native;

namespace SceneApp.Infrastructure;

// Transitional adapter. #679 supplies the D3D11 tgfx texture and domain token;
// until then RenderingManager rejects this surface before GPU work.
public class WpfRenderSurface : IDisposable
{
    private readonly GLWpfControl _control;
    private IntPtr _surfacePtr;
    private GCHandle _selfHandle;
    private bool _disposed;
    private TerminCore.RenderSurfaceGetSizeDelegate? _getSize;
    private TerminCore.RenderSurfaceResizeDelegate? _resize;
    private TerminCore.RenderSurfaceGetColorTextureIdDelegate? _getColorTextureId;
    private TerminCore.RenderSurfaceGetGraphicsDomainKeyDelegate? _getGraphicsDomainKey;
    private TerminCore.RenderSurfaceDestroyDelegate? _destroy;
    private TerminCore.RenderSurfaceVTable _vtable;
    private bool _transferred;

    public IntPtr SurfacePtr => _transferred ? IntPtr.Zero : _surfacePtr;

    public WpfRenderSurface(GLWpfControl control)
    {
        _control = control;
        _selfHandle = GCHandle.Alloc(this);
        _getSize = GetSize;
        _resize = Resize;
        _getColorTextureId = _ => 0;
        _getGraphicsDomainKey = _ => 0;
        _destroy = Destroy;
        _vtable = new TerminCore.RenderSurfaceVTable
        {
            get_size = Marshal.GetFunctionPointerForDelegate(_getSize),
            resize = Marshal.GetFunctionPointerForDelegate(_resize),
            get_color_texture_id = Marshal.GetFunctionPointerForDelegate(_getColorTextureId),
            get_graphics_domain_key = Marshal.GetFunctionPointerForDelegate(_getGraphicsDomainKey),
            destroy = Marshal.GetFunctionPointerForDelegate(_destroy),
        };
        _surfacePtr = TerminCore.RenderSurfaceNewExternal(
            GCHandle.ToIntPtr(_selfHandle), ref _vtable,
            (nuint)Marshal.SizeOf<TerminCore.RenderSurfaceVTable>(), 2);
        if (_surfacePtr == IntPtr.Zero)
        {
            _selfHandle.Free();
            throw new Exception("Failed to create tc_render_surface");
        }
    }

    private static WpfRenderSurface? Self(IntPtr surface)
    {
        if (surface == IntPtr.Zero) return null;
        IntPtr body = Marshal.ReadIntPtr(surface, IntPtr.Size);
        return body == IntPtr.Zero ? null : GCHandle.FromIntPtr(body).Target as WpfRenderSurface;
    }

    private static void GetSize(IntPtr surface, out int width, out int height)
    {
        var self = Self(surface);
        width = self is null ? 0 : (int)self._control.ActualWidth;
        height = self is null ? 0 : (int)self._control.ActualHeight;
    }

    private static bool Resize(IntPtr surface, int width, int height)
    {
        var self = Self(surface);
        return self is not null && width > 0 && height > 0;
    }

    private static void Destroy(IntPtr surface)
    {
        var self = Self(surface);
        if (self is null) return;
        self._surfacePtr = IntPtr.Zero;
        self._transferred = true;
        self._disposed = true;
        if (self._selfHandle.IsAllocated) self._selfHandle.Free();
    }

    public void MarkTransferred()
    {
        if (_surfacePtr == IntPtr.Zero) throw new ObjectDisposedException(nameof(WpfRenderSurface));
        _transferred = true;
    }

    public void Dispose()
    {
        if (_disposed) return;
        if (_surfacePtr != IntPtr.Zero && !_transferred)
        {
            if (!TerminCore.RenderSurfaceDeleteUnowned(_surfacePtr)) return;
            _surfacePtr = IntPtr.Zero;
        }
        _disposed = true;
        GC.SuppressFinalize(this);
    }
}
