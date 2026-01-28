// Helper methods for creating SWIG wrapper types from IntPtr
// These methods expose internal constructors for external use

namespace Termin.Native;

/// <summary>
/// Helper methods for creating SWIG opaque pointer wrappers.
/// Use these when you have an IntPtr and need to pass it to SWIG-generated methods
/// that expect SWIGTYPE_* parameters.
/// </summary>
public static class SwigHelpers
{
    /// <summary>
    /// Wrap an IntPtr as SWIGTYPE_p_void for passing to SWIG methods.
    /// </summary>
    public static SWIGTYPE_p_void WrapVoidPtr(IntPtr ptr)
    {
        return new SWIGTYPE_p_void(ptr, false);
    }

    /// <summary>
    /// Wrap an IntPtr as CameraComponent for passing to SWIG methods.
    /// CameraComponent is now a fully defined type in SWIG.
    /// </summary>
    public static CameraComponent WrapCameraComponentPtr(IntPtr ptr)
    {
        return new CameraComponent(ptr, false);
    }

    /// <summary>
    /// Wrap an IntPtr as SWIGTYPE_p_tc_pass for passing to SWIG methods.
    /// </summary>
    public static SWIGTYPE_p_tc_pass WrapTcPassPtr(IntPtr ptr)
    {
        return new SWIGTYPE_p_tc_pass(ptr, false);
    }

    /// <summary>
    /// Wrap a GraphicsBackend IntPtr for passing to SWIG methods.
    /// </summary>
    public static SWIGTYPE_p_termin__GraphicsBackend WrapGraphicsBackendPtr(IntPtr ptr)
    {
        return new SWIGTYPE_p_termin__GraphicsBackend(ptr, false);
    }

    /// <summary>
    /// Wrap an IntPtr as SWIGTYPE_p_tc_display for passing to SWIG methods.
    /// </summary>
    public static SWIGTYPE_p_tc_display WrapTcDisplayPtr(IntPtr ptr)
    {
        return new SWIGTYPE_p_tc_display(ptr, false);
    }

    /// <summary>
    /// Wrap an IntPtr as SWIGTYPE_p_tc_pipeline for passing to SWIG methods.
    /// </summary>
    public static SWIGTYPE_p_tc_pipeline WrapTcPipelinePtr(IntPtr ptr)
    {
        return new SWIGTYPE_p_tc_pipeline(ptr, false);
    }

    /// <summary>
    /// Get IntPtr from SWIGTYPE_p_tc_pipeline.
    /// </summary>
    public static IntPtr GetPtr(SWIGTYPE_p_tc_pipeline obj)
    {
        return SWIGTYPE_p_tc_pipeline.getCPtr(obj).Handle;
    }
}
