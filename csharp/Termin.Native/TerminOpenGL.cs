using System.Runtime.InteropServices;

namespace Termin.Native;

/// <summary>
/// P/Invoke declarations for OpenGL backend (termin.dll).
/// </summary>
public static partial class TerminOpenGL
{
    const string DLL = "termin";

    /// <summary>
    /// Initialize OpenGL backend.
    /// Must be called AFTER an OpenGL context is current.
    /// </summary>
    [LibraryImport(DLL, EntryPoint = "tc_opengl_init")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static partial bool Init();

    /// <summary>
    /// Check if OpenGL backend is initialized.
    /// </summary>
    [LibraryImport(DLL, EntryPoint = "tc_opengl_is_initialized")]
    [return: MarshalAs(UnmanagedType.U1)]
    public static partial bool IsInitialized();

    /// <summary>
    /// Shutdown OpenGL backend.
    /// </summary>
    [LibraryImport(DLL, EntryPoint = "tc_opengl_shutdown")]
    public static partial void Shutdown();

    /// <summary>
    /// Get the global OpenGL graphics backend.
    /// Returns NULL if not initialized.
    /// </summary>
    [LibraryImport(DLL, EntryPoint = "tc_opengl_get_graphics")]
    public static partial IntPtr GetGraphics();
}
