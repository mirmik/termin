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
    private TerminCore.RenderSurfaceGetColorTextureIdDelegate? _getColorTextureId;
    private TerminCore.RenderSurfaceGetGraphicsDomainKeyDelegate? _getGraphicsDomainKey;
    private TerminCore.RenderSurfaceDestroyDelegate? _destroy;
    private TerminCore.RenderSurfaceVTable _vtable;

    public IntPtr SurfacePtr => _surfacePtr;

    public WpfRenderSurface(GLWpfControl control)
    {
        _control = control;
        _selfHandle = GCHandle.Alloc(this);
        _getSize = GetSize;
        _getColorTextureId = _ => 0;
        _getGraphicsDomainKey = _ => 0;
        _destroy = _ => { };
        _vtable = new TerminCore.RenderSurfaceVTable
        {
            get_size = Marshal.GetFunctionPointerForDelegate(_getSize),
            get_color_texture_id = Marshal.GetFunctionPointerForDelegate(_getColorTextureId),
            get_graphics_domain_key = Marshal.GetFunctionPointerForDelegate(_getGraphicsDomainKey),
            destroy = Marshal.GetFunctionPointerForDelegate(_destroy),
        };
        _surfacePtr = TerminCore.RenderSurfaceNewExternal(
            GCHandle.ToIntPtr(_selfHandle), ref _vtable,
            (nuint)Marshal.SizeOf<TerminCore.RenderSurfaceVTable>(), 1);
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

    public void Dispose()
    {
        if (_disposed) return;
        if (_surfacePtr != IntPtr.Zero)
        {
            if (!TerminCore.RenderSurfaceFreeExternal(_surfacePtr)) return;
            _surfacePtr = IntPtr.Zero;
        }
        _disposed = true;
        if (_selfHandle.IsAllocated) _selfHandle.Free();
        GC.SuppressFinalize(this);
    }

    ~WpfRenderSurface() => Dispose();
}
