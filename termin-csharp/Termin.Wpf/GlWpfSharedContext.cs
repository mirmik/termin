using OpenTK.Wpf;

namespace Termin.Wpf;

public static class GlWpfSharedContext
{
    private static OpenTK.Windowing.Desktop.IGLFWGraphicsContext? s_context;

    public static GLWpfControlSettings CreateSettings()
    {
        var settings = new GLWpfControlSettings
        {
            MajorVersion = 4,
            MinorVersion = 5,
        };

        if (s_context != null)
        {
            settings.SharedContext = s_context;
        }

        return settings;
    }

    public static void CaptureIfFirst(GLWpfControl control)
    {
        s_context ??= control.Context as OpenTK.Windowing.Desktop.IGLFWGraphicsContext;
    }
}
