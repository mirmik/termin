using System.IO;
using System.Runtime.InteropServices;

namespace SceneApp.Infrastructure;

static class NativeLoader
{
    private static IntPtr _terminHandle = IntPtr.Zero;
    private static IntPtr _terminCoreHandle = IntPtr.Zero;
    private static IntPtr _terminMeshHandle = IntPtr.Zero;
    private static IntPtr _entityLibHandle = IntPtr.Zero;
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
        var terminCorePath = Path.Combine(exeDir, "termin_core.dll");
        var terminPath = Path.Combine(exeDir, "termin.dll");
        var entityLibPath = Path.Combine(exeDir, "entity_lib.dll");

        if (File.Exists(terminMeshPath))
            _terminMeshHandle = LoadLibrary(terminMeshPath);

        if (File.Exists(terminCorePath))
            _terminCoreHandle = LoadLibrary(terminCorePath);

        if (File.Exists(terminPath))
            _terminHandle = LoadLibrary(terminPath);

        if (File.Exists(entityLibPath))
            _entityLibHandle = LoadLibrary(entityLibPath);

        _initialized = true;
    }
}
