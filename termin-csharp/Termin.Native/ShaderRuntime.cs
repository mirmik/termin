using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;

namespace Termin.Native;

public static class ShaderRuntime
{
    private const string ArtifactRootEnv = "TERMIN_SHADER_ARTIFACT_ROOT";
    private const string UcrtDll = "ucrtbase";

    [DllImport(UcrtDll, EntryPoint = "_putenv_s", CallingConvention = CallingConvention.Cdecl, CharSet = CharSet.Ansi)]
    private static extern int PutEnv(string name, string value);

    [DllImport("termin_graphics2", EntryPoint = "tgfx2_set_shader_artifact_root", CharSet = CharSet.Ansi)]
    private static extern void Tgfx2SetShaderArtifactRoot(string root);

    public static void ConfigureFromAssemblyDirectory()
    {
        var configuredRoot = Environment.GetEnvironmentVariable(ArtifactRootEnv);
        if (IsUsableArtifactRoot(configuredRoot))
        {
            ApplyArtifactRoot(configuredRoot!);
            return;
        }

        foreach (var root in CandidateRoots())
        {
            if (IsUsableArtifactRoot(root))
            {
                ApplyArtifactRoot(root);
                return;
            }
        }
    }

    private static void ApplyArtifactRoot(string root)
    {
        Environment.SetEnvironmentVariable(ArtifactRootEnv, root);
        Tgfx2SetShaderArtifactRoot(root);
        if (!RuntimeInformation.IsOSPlatform(OSPlatform.Windows))
        {
            return;
        }

        int result = PutEnv(ArtifactRootEnv, root);
        if (result != 0)
        {
            throw new InvalidOperationException(
                $"ShaderRuntime: failed to set CRT environment {ArtifactRootEnv}='{root}' (rc={result})");
        }
    }

    private static IEnumerable<string> CandidateRoots()
    {
        foreach (var baseDir in CandidateBaseDirectories())
        {
            if (string.IsNullOrWhiteSpace(baseDir))
            {
                continue;
            }

            yield return Path.Combine(baseDir, "share", "termin");
        }
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

    private static bool IsUsableArtifactRoot(string? root)
    {
        if (string.IsNullOrWhiteSpace(root))
        {
            return false;
        }

        if (!Directory.Exists(root))
        {
            return false;
        }

        var catalog = Path.Combine(root, "builtin_shaders", "engine-shader-catalog.json");
        var tcplot = Path.Combine(root, "shaders", "d3d11", "termin-engine-tcplot-3d.vs.cso");
        var text3d = Path.Combine(root, "shaders", "d3d11", "termin-engine-text3d.vs.cso");
        return File.Exists(catalog) && File.Exists(tcplot) && File.Exists(text3d);
    }
}
