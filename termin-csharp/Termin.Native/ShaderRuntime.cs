using System;
using System.Collections.Generic;
using System.IO;
using System.Reflection;

namespace Termin.Native;

public static class ShaderRuntime
{
    private const string ArtifactRootEnv = "TERMIN_SHADER_ARTIFACT_ROOT";

    public static void ConfigureFromAssemblyDirectory()
    {
        if (!string.IsNullOrWhiteSpace(Environment.GetEnvironmentVariable(ArtifactRootEnv)))
        {
            return;
        }

        foreach (var root in CandidateRoots())
        {
            if (IsUsableArtifactRoot(root))
            {
                Environment.SetEnvironmentVariable(ArtifactRootEnv, root);
                return;
            }
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

    private static bool IsUsableArtifactRoot(string root)
    {
        if (!Directory.Exists(root))
        {
            return false;
        }

        var catalog = Path.Combine(root, "builtin_shaders", "engine-shader-catalog.json");
        var tcplot = Path.Combine(root, "shaders", "opengl", "termin-engine-tcplot-3d.vert.glsl");
        var text3d = Path.Combine(root, "shaders", "opengl", "termin-engine-text3d.vert.glsl");
        return File.Exists(catalog) && File.Exists(tcplot) && File.Exists(text3d);
    }
}