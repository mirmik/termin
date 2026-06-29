using System;
using System.Runtime.InteropServices;

namespace Termin.Native;

/// <summary>
/// Minimal P/Invoke surface for the plot-only C# runtime profile.
/// </summary>
public static class TerminCore
{
    private const string BASE_DLL = "termin_base";
    private const string TGFX2_DLL = "termin_graphics2";

    public static void Init()
    {
        ConfigurePlotRuntime();
    }

    public static void InitFull()
    {
        ConfigurePlotRuntime();
    }

    public static void Shutdown()
    {
    }

    public static void ConfigurePlotRuntime()
    {
        NativeRuntimeSearchPath.Configure();
        ShaderRuntime.ConfigureFromAssemblyDirectory();
    }

    [DllImport(TGFX2_DLL, EntryPoint = "tgfx2_interop_register_external_gl_texture")]
    public static extern uint Tgfx2RegisterExternalGlTexture(
        uint glTextureId,
        uint width,
        uint height,
        int format,
        uint usage);

    [DllImport(TGFX2_DLL, EntryPoint = "tgfx2_interop_destroy_texture_handle")]
    public static extern void Tgfx2DestroyTextureHandle(uint handleId);

    [DllImport(TGFX2_DLL, EntryPoint = "tgfx2_interop_blit_texture")]
    public static extern void Tgfx2BlitTexture(
        uint srcHandleId,
        uint dstHandleId,
        int width,
        int height);

    [DllImport(TGFX2_DLL, EntryPoint = "tgfx2_interop_create_d3d11_swapchain")]
    public static extern IntPtr Tgfx2CreateD3D11Swapchain(
        IntPtr hwnd,
        uint width,
        uint height);

    [DllImport(TGFX2_DLL, EntryPoint = "tgfx2_interop_destroy_d3d11_swapchain")]
    public static extern void Tgfx2DestroyD3D11Swapchain(IntPtr swapchain);

    [DllImport(TGFX2_DLL, EntryPoint = "tgfx2_interop_resize_d3d11_swapchain")]
    public static extern int Tgfx2ResizeD3D11Swapchain(
        IntPtr swapchain,
        uint width,
        uint height);

    [DllImport(TGFX2_DLL, EntryPoint = "tgfx2_interop_present_d3d11_swapchain")]
    public static extern int Tgfx2PresentD3D11Swapchain(
        IntPtr swapchain,
        uint sourceHandleId,
        uint syncInterval);

    [DllImport(TGFX2_DLL, EntryPoint = "tgfx2_interop_create_d3d11_d3dimage_bridge")]
    public static extern IntPtr Tgfx2CreateD3D11D3DImageBridge(
        uint width,
        uint height);

    [DllImport(TGFX2_DLL, EntryPoint = "tgfx2_interop_destroy_d3d11_d3dimage_bridge")]
    public static extern void Tgfx2DestroyD3D11D3DImageBridge(IntPtr bridge);

    [DllImport(TGFX2_DLL, EntryPoint = "tgfx2_interop_resize_d3d11_d3dimage_bridge")]
    public static extern int Tgfx2ResizeD3D11D3DImageBridge(
        IntPtr bridge,
        uint width,
        uint height);

    [DllImport(TGFX2_DLL, EntryPoint = "tgfx2_interop_present_d3d11_d3dimage_bridge")]
    public static extern int Tgfx2PresentD3D11D3DImageBridge(
        IntPtr bridge,
        uint sourceHandleId);

    [DllImport(TGFX2_DLL, EntryPoint = "tgfx2_interop_get_d3d11_d3dimage_surface")]
    public static extern IntPtr Tgfx2GetD3D11D3DImageSurface(IntPtr bridge);

    public enum TcLogLevel
    {
        Trace = 0,
        Debug = 1,
        Info = 2,
        Warn = 3,
        Error = 4,
        Fatal = 5,
    }

    public delegate void TcLogCallback(TcLogLevel level, [MarshalAs(UnmanagedType.LPUTF8Str)] string message);

    [DllImport(BASE_DLL, EntryPoint = "tc_log_set_callback")]
    public static extern void LogSetCallback(TcLogCallback? callback);

    [DllImport(BASE_DLL, EntryPoint = "tc_log_set_level")]
    public static extern void LogSetLevel(TcLogLevel level);
}
