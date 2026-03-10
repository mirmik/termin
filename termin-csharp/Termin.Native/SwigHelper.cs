using System;
namespace Termin.Native;

/// <summary>
/// Helper class to access internal SWIG pointers from external assemblies.
/// </summary>
public static class SwigHelper
{
    /// <summary>
    /// Get the native pointer from a SWIG-wrapped Camera object.
    /// </summary>
    public static IntPtr GetCameraPtr(Camera camera)
    {
        return Camera.getCPtr(camera).Handle;
    }
}
