using System.ComponentModel;
using System.IO;
using System.Runtime.InteropServices;

namespace SceneApp.Infrastructure;

internal static class NativeLoader
{
    private const uint LoadLibrarySearchDefaultDirs = 0x00001000;
    private static IntPtr _runtimeDirectoryCookie;
    private static IntPtr _graphicsHandle;
    private static bool _initialized;

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetDefaultDllDirectories(uint directoryFlags);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    private static extern IntPtr AddDllDirectory(string newDirectory);

    public static void Initialize()
    {
        if (_initialized)
        {
            return;
        }

        string runtimeDirectory = ResolveRuntimeDirectory();
        Console.Error.WriteLine($"[SceneApp] Configuring native runtime: {runtimeDirectory}");
        if (!SetDefaultDllDirectories(LoadLibrarySearchDefaultDirs))
        {
            throw new Win32Exception(
                Marshal.GetLastWin32Error(),
                "Failed to enable safe Windows DLL search directories.");
        }

        _runtimeDirectoryCookie = AddDllDirectory(runtimeDirectory);
        if (_runtimeDirectoryCookie == IntPtr.Zero)
        {
            throw new Win32Exception(
                Marshal.GetLastWin32Error(),
                $"Failed to add Termin native runtime directory '{runtimeDirectory}'.");
        }

        string graphicsPath = Path.Combine(runtimeDirectory, "termin_graphics2.dll");
        try
        {
            Console.Error.WriteLine($"[SceneApp] Loading native probe: {graphicsPath}");
            _graphicsHandle = NativeLibrary.Load(graphicsPath);
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(
                $"[SceneApp] Failed to load native runtime from '{runtimeDirectory}': {error}");
            throw;
        }

        _initialized = true;
        Console.WriteLine($"[SceneApp] Native runtime: {runtimeDirectory}");
    }

    private static string ResolveRuntimeDirectory()
    {
        string architecture = RuntimeInformation.ProcessArchitecture switch
        {
            Architecture.X64 => "win-x64",
            Architecture.Arm64 => "win-arm64",
            Architecture.X86 => "win-x86",
            Architecture.Arm => "win-arm",
            _ => throw new PlatformNotSupportedException(
                $"Unsupported Windows process architecture: {RuntimeInformation.ProcessArchitecture}"),
        };

        string runtimeDirectory = Path.Combine(
            AppContext.BaseDirectory,
            "runtimes",
            architecture,
            "native");
        if (!Directory.Exists(runtimeDirectory))
        {
            throw new DirectoryNotFoundException(
                $"Termin native runtime directory was not copied to '{runtimeDirectory}'.");
        }
        return runtimeDirectory;
    }
}
