using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;

namespace Termin.Native;

internal static class NativeRuntimeSearchPath
{
    private static readonly object Lock = new();
    private static bool s_configured;

    public static void Configure()
    {
        if (s_configured)
        {
            return;
        }

        lock (Lock)
        {
            if (s_configured)
            {
                return;
            }

            if (RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
            {
                string? nativeDir = FindWindowsNativeDirectory();
                if (!string.IsNullOrWhiteSpace(nativeDir) && !SetDllDirectory(nativeDir))
                {
                    throw new InvalidOperationException(
                        $"NativeRuntimeSearchPath: failed to add native DLL directory '{nativeDir}' " +
                        $"(Win32 error {Marshal.GetLastWin32Error()}).");
                }
            }

            s_configured = true;
        }
    }

    private static string? FindWindowsNativeDirectory()
    {
        string rid = RuntimeInformation.ProcessArchitecture switch
        {
            Architecture.X64 => "win-x64",
            Architecture.X86 => "win-x86",
            Architecture.Arm64 => "win-arm64",
            _ => "win-x64",
        };

        foreach (var baseDir in CandidateBaseDirectories())
        {
            if (string.IsNullOrWhiteSpace(baseDir))
            {
                continue;
            }

            var runtimeDir = Path.Combine(baseDir, "runtimes", rid, "native");
            if (File.Exists(Path.Combine(runtimeDir, "termin.dll")))
            {
                return runtimeDir;
            }

            if (File.Exists(Path.Combine(baseDir, "termin.dll")))
            {
                return baseDir;
            }
        }

        return null;
    }

    private static IEnumerable<string> CandidateBaseDirectories()
    {
        yield return AppContext.BaseDirectory;

        var assemblyDir = Path.GetDirectoryName(Assembly.GetExecutingAssembly().Location);
        if (!string.IsNullOrWhiteSpace(assemblyDir))
        {
            yield return assemblyDir;
        }

        yield return Environment.CurrentDirectory;
    }

    [DllImport("kernel32.dll", SetLastError = true, CharSet = CharSet.Unicode)]
    [return: MarshalAs(UnmanagedType.Bool)]
    private static extern bool SetDllDirectory(string lpPathName);
}