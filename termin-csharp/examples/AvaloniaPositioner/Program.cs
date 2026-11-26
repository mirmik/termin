using System;
using System.Linq;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.ApplicationLifetimes;
using Avalonia.Styling;
using Avalonia.Themes.Fluent;
using Avalonia.Threading;

namespace AvaloniaPositioner;

internal static class Program
{
    [STAThread]
    public static int Main(string[] args) =>
        AppBuilder.Configure<PositionerApp>()
            .UsePlatformDetect()
            .StartWithClassicDesktopLifetime(args);
}

internal sealed class PositionerApp : Application
{
    public override void Initialize()
    {
        RequestedThemeVariant = ThemeVariant.Dark;
        Styles.Add(new FluentTheme());
    }

    public override void OnFrameworkInitializationCompleted()
    {
        if (ApplicationLifetime is IClassicDesktopStyleApplicationLifetime desktop)
        {
            var smoke = desktop.Args?.Contains("--smoke", StringComparer.Ordinal) == true;
            if (smoke)
            {
                desktop.ShutdownMode = ShutdownMode.OnExplicitShutdown;
                bool verifyLineRenderer = desktop.Args?.Contains("--verify-line-renderer", StringComparer.Ordinal) == true;
                Dispatcher.UIThread.Post(() => RunSmoke(desktop, verifyLineRenderer));
            }
            else
            {
                desktop.MainWindow = new PositionerWindow(error =>
                {
                    Console.Error.WriteLine(error);
                    desktop.Shutdown(1);
                });
            }
        }
        base.OnFrameworkInitializationCompleted();
    }

    private static async void RunSmoke(IClassicDesktopStyleApplicationLifetime desktop, bool verifyLineRenderer)
    {
        PositionerWindow? window = null;
        try
        {
            window = new PositionerWindow(Console.Error.WriteLine);
            window.Show();
            await window.VerifySmokeAsync(verifyLineRenderer);
            window.Close();
            window.VerifyClosed();

            window = new PositionerWindow(Console.Error.WriteLine);
            window.Show();
            await window.VerifyReopenedAsync();
            window.Close();
            window.VerifyClosed();
            Console.WriteLine("AVALONIA_POSITIONER_SMOKE_OK");
            desktop.Shutdown(0);
        }
        catch (Exception error)
        {
            Console.Error.WriteLine($"AVALONIA_POSITIONER_SMOKE_FAILED {error}");
            if (window?.IsVisible == true)
                window.Close();
            desktop.Shutdown(1);
        }
    }
}
