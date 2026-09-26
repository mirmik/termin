using System.Windows;
using System.Windows.Threading;

namespace PlotDemoApp;

public partial class App : Application
{
    protected override void OnStartup(StartupEventArgs e)
    {
        base.OnStartup(e);

        if (e.Args.Contains("--smoke-2d-hosts", StringComparer.OrdinalIgnoreCase) ||
            e.Args.Contains("--smoke-2d-hosts-1x1", StringComparer.OrdinalIgnoreCase) ||
            e.Args.Contains("--smoke-2d-hosts-2x2", StringComparer.OrdinalIgnoreCase))
        {
            int bootstrapSize = e.Args.Contains("--smoke-2d-hosts-2x2", StringComparer.OrdinalIgnoreCase) ? 2 : 1;
            StartMultiHostSmoke(bootstrapSize);
            return;
        }

        if (e.Args.Contains("--smoke-color-presentation", StringComparer.OrdinalIgnoreCase))
        {
            MainWindow = new ColorPresentationSmokeWindow();
            ShutdownMode = ShutdownMode.OnMainWindowClose;
            MainWindow.Show();
            return;
        }

        if (e.Args.Contains("--smoke-axis-display", StringComparer.OrdinalIgnoreCase))
        {
            var displayWindow = new SphericalPlot3DWindow();
            MainWindow = displayWindow;
            ShutdownMode = ShutdownMode.OnMainWindowClose;
            displayWindow.Show();
            displayWindow.StartDisplaySmoke();
            return;
        }

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

    private void StartMultiHostSmoke(int bootstrapSize)
    {
        ShutdownMode = ShutdownMode.OnExplicitShutdown;
        int cycle = 0;
        var timeout = new DispatcherTimer { Interval = TimeSpan.FromSeconds(20) };
        timeout.Tick += (_, _) =>
        {
            timeout.Stop();
            Console.Error.WriteLine($"PLOT_2D_HOSTS_SMOKE_FAILED timeout bootstrap={bootstrapSize} cycle={cycle}; expected three visible series before and after resize");
            ((Plot2DWindow)MainWindow).DumpMultiHostSmokeDiagnostics();
            Shutdown(1);
        };
        DispatcherUnhandledException += (_, args) =>
        {
            Console.Error.WriteLine($"PLOT_2D_HOSTS_SMOKE_FAILED bootstrap={bootstrapSize} cycle={cycle}: {args.Exception}");
            args.Handled = true;
            timeout.Stop();
            Shutdown(1);
        };

        void OpenWindow()
        {
            ++cycle;
            var window = new Plot2DWindow(multipleHosts: true,
                smokeBootstrapSize: bootstrapSize, smokeCycle: cycle);
            MainWindow = window;
            window.MultiHostSmokeCompleted += (_, _) =>
            {
                window.Close();
                if (cycle < 2)
                {
                    // Let Unloaded/Closed finish releasing every host lease
                    // before recreating the graphics host in this process.
                    Dispatcher.BeginInvoke(DispatcherPriority.Background, new Action(OpenWindow));
                    return;
                }
                timeout.Stop();
                Console.WriteLine($"PLOT_2D_HOSTS_SMOKE_OK bootstrap={bootstrapSize} cycles={cycle}; three visible plots, resize, close and reopen");
                Shutdown(0);
            };
            Console.WriteLine($"PLOT_2D_HOSTS_WINDOW_OPEN bootstrap={bootstrapSize} cycle={cycle}");
            window.Show();
        }

        timeout.Start();
        OpenWindow();
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
        if (args.Contains("--smoke-spherical3d", StringComparer.OrdinalIgnoreCase))
        {
            return new SphericalPlot3DWindow();
        }

        return null;
    }
}
