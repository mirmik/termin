using System.Windows;
using System.Windows.Threading;

namespace PlotDemoApp;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        bool smoke = e.Args.Any(arg => arg.StartsWith("--smoke-", StringComparison.OrdinalIgnoreCase));
        Window window = SmokeWindow(e.Args) ?? new MainWindow();

        MainWindow = window;
        ShutdownMode = ShutdownMode.OnMainWindowClose;
        window.Show();

        if (smoke)
        {
            var timer = new DispatcherTimer
            {
                Interval = TimeSpan.FromSeconds(3),
            };
            timer.Tick += (_, _) =>
            {
                timer.Stop();
                window.Close();
            };
            timer.Start();
        }
    }

    private static Window? SmokeWindow(string[] args)
    {
        if (args.Contains("--smoke-2d", StringComparer.OrdinalIgnoreCase))
        {
            return new Plot2DWindow();
        }
        if (args.Contains("--smoke-3d", StringComparer.OrdinalIgnoreCase))
        {
            return new Plot3DWindow();
        }
        if (args.Contains("--smoke-multi2d", StringComparer.OrdinalIgnoreCase))
        {
            return new MultiPlot2DWindow();
        }
        if (args.Contains("--smoke-scroll-multi2d", StringComparer.OrdinalIgnoreCase))
        {
            return new ScrollableMultiPlot2DWindow();
        }
        if (args.Contains("--smoke-route2d", StringComparer.OrdinalIgnoreCase))
        {
            return new RoutePlot2DWindow();
        }
        if (args.Contains("--smoke-scaled3d", StringComparer.OrdinalIgnoreCase))
        {
            return new ScaledPlot3DWindow();
        }

        return null;
    }
}
