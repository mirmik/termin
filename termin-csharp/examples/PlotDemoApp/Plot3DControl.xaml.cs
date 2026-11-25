using System;
using System.Windows;
using System.Windows.Controls;
using Termin.Native;

namespace PlotDemoApp;

public partial class Plot3DControl : UserControl, IDisposable
{
    private RetainedChart3D? _chart;
    private bool _hostLeaseHeld;
    private bool _disposed;

    public Plot3DControl()
    {
        InitializeComponent();
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
    }

    public RetainedChart3D Chart => _chart ??
        throw new InvalidOperationException("The retained 3D chart is not initialized.");

    public event EventHandler? NativeInitialized;

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        Loaded -= OnLoaded;
        GpuHost host = Tgfx2Host.Acquire(App.FindSystemFont());
        _hostLeaseHeld = true;
        try
        {
            _chart = new RetainedChart3D(host);
            ChartHost.RenderFailed += App.LogRenderFailure;
            ChartHost.Attach(_chart);
            NativeInitialized?.Invoke(this, EventArgs.Empty);
        }
        catch
        {
            Dispose();
            throw;
        }
    }

    private void OnUnloaded(object sender, RoutedEventArgs e) => Dispose();

    public void Dispose()
    {
        if (_disposed)
            return;
        Dispatcher.VerifyAccess();
        _disposed = true;
        Loaded -= OnLoaded;
        Unloaded -= OnUnloaded;
        ChartHost.Dispose();
        _chart?.Dispose();
        _chart = null;
        if (_hostLeaseHeld)
        {
            Tgfx2Host.Release();
            _hostLeaseHeld = false;
        }
    }
}
