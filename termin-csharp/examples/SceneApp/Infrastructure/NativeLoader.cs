using System.IO;
using System.Runtime.InteropServices;

namespace SceneApp.Infrastructure;

static class NativeLoader
{
    private static IntPtr _terminHandle = IntPtr.Zero;
    private static IntPtr _terminBootstrapHandle = IntPtr.Zero;
    private static IntPtr _terminGraphicsHandle = IntPtr.Zero;
    private static IntPtr _terminMeshHandle = IntPtr.Zero;
    private static IntPtr _terminCollisionHandle = IntPtr.Zero;
    private static bool _initialized;

    [DllImport("kernel32.dll", SetLastError = true)]
    private static extern IntPtr LoadLibrary(string lpFileName);

    public static void Initialize()
    {
        if (_initialized) return;

        // Get the directory where the executable is located
        var exeDir = AppContext.BaseDirectory;

        // Load native DLLs in dependency order
        var terminMeshPath = Path.Combine(exeDir, "termin_mesh.dll");
        var terminGraphicsPath = Path.Combine(exeDir, "termin_graphics.dll");
        var terminBootstrapPath = Path.Combine(exeDir, "termin_bootstrap.dll");
        var terminCollisionPath = Path.Combine(exeDir, "termin_collision.dll");
        var terminPath = Path.Combine(exeDir, "termin.dll");

        if (File.Exists(terminMeshPath))
            _terminMeshHandle = LoadLibrary(terminMeshPath);

        if (File.Exists(terminGraphicsPath))
            _terminGraphicsHandle = LoadLibrary(terminGraphicsPath);

        if (File.Exists(terminBootstrapPath))
            _terminBootstrapHandle = LoadLibrary(terminBootstrapPath);

        if (File.Exists(terminCollisionPath))
            _terminCollisionHandle = LoadLibrary(terminCollisionPath);

        if (File.Exists(terminPath))
            _terminHandle = LoadLibrary(terminPath);

        _initialized = true;
    }
}
