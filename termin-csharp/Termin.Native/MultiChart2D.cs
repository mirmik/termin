using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

namespace Termin.Native;

[StructLayout(LayoutKind.Sequential)]
internal readonly struct MultiChartPanelHandle2D
{
    internal readonly ulong MultiChartId;
    internal readonly uint Index;
    internal readonly uint Generation;

    internal bool IsValid => MultiChartId != 0 && Generation != 0;
}

[StructLayout(LayoutKind.Sequential)]
internal readonly struct NativeMultiChartSnapshot2D
{
    internal readonly PlotRect2D Viewport;
    internal readonly PlotRange2D SharedRange;
    internal readonly float PixelScale;
    internal readonly float PanelHeight;
    internal readonly float PanelGap;
    internal readonly float ScrollOffset;
    internal readonly float TotalVirtualHeight;
    internal readonly float MaximumScrollOffset;
    internal readonly nuint PanelCount;
    internal readonly ulong LayoutRevision;
}

public readonly struct MultiChartSnapshot2D
{
    public PlotRect2D Viewport { get; }
    public double SharedXMinimum { get; }
    public double SharedXMaximum { get; }
    public float PixelScale { get; }
    public float PanelHeight { get; }
    public float PanelGap { get; }
    public float ScrollOffset { get; }
    public float TotalVirtualHeight { get; }
    public float MaximumScrollOffset { get; }
    public int PanelCount { get; }
    public ulong LayoutRevision { get; }

    internal MultiChartSnapshot2D(NativeMultiChartSnapshot2D value)
    {
        Viewport = value.Viewport;
        SharedXMinimum = value.SharedRange.XMin;
        SharedXMaximum = value.SharedRange.XMax;
        PixelScale = value.PixelScale;
        PanelHeight = value.PanelHeight;
        PanelGap = value.PanelGap;
        ScrollOffset = value.ScrollOffset;
        TotalVirtualHeight = value.TotalVirtualHeight;
        MaximumScrollOffset = value.MaximumScrollOffset;
        PanelCount = checked((int)value.PanelCount);
        LayoutRevision = value.LayoutRevision;
    }
}

public sealed class MultiChartPanel2D
{
    private readonly MultiChart2D _owner;
    internal MultiChartPanelHandle2D Handle { get; }

    internal MultiChartPanel2D(
        MultiChart2D owner,
        MultiChartPanelHandle2D handle,
        Chart2D chart)
    {
        _owner = owner;
        Handle = handle;
        Chart = chart;
    }

    public int Index => checked((int)Handle.Index);
    public Chart2D Chart { get; }
    public bool IsValid => _owner.IsPanelValid(Handle) && Chart.Root.IsValid;
}

/// <summary>
/// Non-owning coordinated state for two or more native multi-charts, such as
/// Alliance time/frequency columns. It forwards shared X, panel geometry and
/// clamped virtual scroll without duplicating projection or layout math.
/// </summary>
public sealed class MultiChart2DGroup
{
    private readonly List<MultiChart2D> _charts = new();

    public MultiChart2DGroup(params MultiChart2D[] charts)
    {
        if (charts is null)
            throw new ArgumentNullException(nameof(charts));
        if (charts.Length == 0)
            throw new ArgumentException(
                "At least one multi-chart is required.", nameof(charts));
        foreach (MultiChart2D chart in charts)
        {
            if (chart is null)
                throw new ArgumentException(
                    "A multi-chart group cannot contain null.", nameof(charts));
            if (_charts.Contains(chart))
                throw new ArgumentException(
                    "A multi-chart group cannot contain duplicates.",
                    nameof(charts));
            _charts.Add(chart);
        }
    }

    public IReadOnlyList<MultiChart2D> Charts => _charts;

    public float MaximumScrollOffset
    {
        get
        {
            float result = float.PositiveInfinity;
            foreach (MultiChart2D chart in _charts)
                result = Math.Min(
                    result, chart.Snapshot.MaximumScrollOffset);
            return float.IsPositiveInfinity(result) ? 0 : result;
        }
    }

    public float ScrollOffset
    {
        get => _charts[0].Snapshot.ScrollOffset;
        set
        {
            float resolved = Math.Clamp(value, 0, MaximumScrollOffset);
            foreach (MultiChart2D chart in _charts)
                chart.ScrollOffset = resolved;
        }
    }

    public bool Contains(MultiChart2D chart) => _charts.Contains(chart);

    public void SetSharedX(double minimum, double maximum)
    {
        foreach (MultiChart2D chart in _charts)
            chart.SetSharedX(minimum, maximum);
    }

    public void SetPanelLayout(float panelHeight, float panelGap = 0)
    {
        foreach (MultiChart2D chart in _charts)
            chart.SetPanelLayout(panelHeight, panelGap);
    }

    public void SetPanelCount(int panelCount)
    {
        var previous = new int[_charts.Count];
        int changed = 0;
        try
        {
            for (; changed < _charts.Count; ++changed)
            {
                previous[changed] = _charts[changed].Panels.Count;
                _charts[changed].SetPanelCount(panelCount);
            }
        }
        catch
        {
            for (int index = changed - 1; index >= 0; --index)
                _charts[index].SetPanelCount(previous[index]);
            throw;
        }
    }

    public void ApplyTheme(Chart2DTheme theme)
    {
        foreach (MultiChart2D chart in _charts)
            chart.ApplyTheme(theme);
    }
}

/// <summary>
/// Native coordinator for multiple RetainedChart2D panels in one public
/// scene. It owns shared-X state, panel geometry and virtual scrolling while
/// each panel remains available through a borrowed Chart2D projection.
/// </summary>
public sealed class MultiChart2D : IDisposable
{
    private readonly GpuHost _host;
    private readonly string _fontUri;
    private readonly List<MultiChartPanel2D> _panels = new();
    private IntPtr _native;
    private bool _disposed;

    public MultiChart2D(
        GpuHost host,
        float widthPx,
        float heightPx,
        int panelCount,
        PlotRange2D initialRange,
        float panelHeight = 0,
        float panelGap = 0,
        string fontUri = "ui://default-font",
        float pixelScale = 1,
        Chart2DTheme? theme = null)
    {
        _host = host ?? throw new ArgumentNullException(nameof(host));
        if (panelCount < 0)
            throw new ArgumentOutOfRangeException(nameof(panelCount));
        if (string.IsNullOrWhiteSpace(fontUri))
            throw new ArgumentException(
                "A retained text font URI is required.", nameof(fontUri));
        _fontUri = fontUri;
        Theme = theme ?? Chart2DTheme.Default;
        Chart2DNative.Theme nativeTheme = Theme.ToNative();
        _native = MultiChart2DNative.Create(
            GpuHost.getCPtr(host).Handle,
            new PlotRect2D(0, 0, widthPx, heightPx),
            initialRange,
            checked((nuint)panelCount),
            panelHeight,
            panelGap,
            fontUri,
            pixelScale,
            ref nativeTheme);
        if (_native == IntPtr.Zero)
            throw new InvalidOperationException(
                "Failed to create native RetainedMultiChart2D. See native log.");

        try
        {
            Scene = TcVisualScene2D.Borrow(MultiChart2DNative.Scene(_native));
            Root = GroupItemRef2D.Cast(new GraphicItemRef2D(
                Scene.NativeHandle,
                RequireHandle(MultiChart2DNative.Root(_native))));
            AppendPanelWrappers(0, panelCount);
        }
        catch
        {
            DisposePanelWrappers();
            MultiChart2DNative.Destroy(_native);
            _native = IntPtr.Zero;
            Scene?.Dispose();
            throw;
        }
    }

    public TcVisualScene2D Scene { get; } = null!;
    public GroupItemRef2D Root { get; } = null!;
    public Chart2DTheme Theme { get; private set; }
    public IReadOnlyList<MultiChartPanel2D> Panels => _panels;

    public MultiChartSnapshot2D Snapshot
    {
        get
        {
            ThrowIfDisposed();
            if (!MultiChart2DNative.GetSnapshot(_native, out var snapshot))
                throw new InvalidOperationException(
                    "Failed to snapshot native RetainedMultiChart2D.");
            return new MultiChartSnapshot2D(snapshot);
        }
    }

    public float ScrollOffset
    {
        get => Snapshot.ScrollOffset;
        set
        {
            ThrowIfDisposed();
            Require(MultiChart2DNative.SetScrollOffset(_native, value));
        }
    }

    public void SetViewport(VisualRect2f viewport, float pixelScale = 1)
    {
        ThrowIfDisposed();
        Require(MultiChart2DNative.SetViewport(
            _native,
            new PlotRect2D(
                viewport.X, viewport.Y, viewport.Width, viewport.Height),
            pixelScale));
    }

    public void Resize(float widthPx, float heightPx, float pixelScale = 1)
    {
        PlotRect2D viewport = Snapshot.Viewport;
        SetViewport(
            new VisualRect2f(viewport.X, viewport.Y, widthPx, heightPx),
            pixelScale);
    }

    public void SetPanelLayout(float panelHeight, float panelGap = 0)
    {
        ThrowIfDisposed();
        Require(MultiChart2DNative.SetPanelLayout(
            _native, panelHeight, panelGap));
    }

    public void SetPanelCount(int panelCount)
    {
        if (panelCount < 0)
            throw new ArgumentOutOfRangeException(nameof(panelCount));
        ThrowIfDisposed();
        int oldCount = _panels.Count;
        Require(MultiChart2DNative.SetPanelCount(
            _native, checked((nuint)panelCount)));
        if (panelCount < oldCount)
        {
            for (int index = oldCount - 1; index >= panelCount; --index)
            {
                _panels[index].Chart.Dispose();
                _panels.RemoveAt(index);
            }
        }
        else if (panelCount > oldCount)
        {
            try
            {
                AppendPanelWrappers(oldCount, panelCount);
            }
            catch
            {
                MultiChart2DNative.SetPanelCount(
                    _native, checked((nuint)oldCount));
                while (_panels.Count > oldCount)
                {
                    _panels[^1].Chart.Dispose();
                    _panels.RemoveAt(_panels.Count - 1);
                }
                throw;
            }
        }
    }

    public void SetSharedX(double minimum, double maximum)
    {
        ThrowIfDisposed();
        Require(MultiChart2DNative.SetSharedX(
            _native, minimum, maximum));
    }

    public void ApplyTheme(Chart2DTheme theme)
    {
        if (theme is null)
            throw new ArgumentNullException(nameof(theme));
        ThrowIfDisposed();
        Chart2DNative.Theme nativeTheme = theme.ToNative();
        Require(MultiChart2DNative.SetTheme(_native, ref nativeTheme));
        Theme = theme;
        foreach (MultiChartPanel2D panel in _panels)
            panel.Chart.AdoptTheme(theme);
    }

    public void Dispose()
    {
        if (_disposed)
            return;
        DisposePanelWrappers();
        if (_native != IntPtr.Zero)
            MultiChart2DNative.Destroy(_native);
        _native = IntPtr.Zero;
        Scene.Dispose();
        _disposed = true;
        GC.SuppressFinalize(this);
    }

    internal bool IsPanelValid(MultiChartPanelHandle2D panel) =>
        !_disposed && _native != IntPtr.Zero &&
        MultiChart2DNative.PanelIsValid(_native, panel);

    private void AppendPanelWrappers(int start, int count)
    {
        for (int index = start; index < count; ++index)
        {
            MultiChartPanelHandle2D handle =
                MultiChart2DNative.PanelAt(_native, checked((nuint)index));
            if (!handle.IsValid)
                throw new InvalidOperationException(
                    $"Native multi-chart returned an invalid panel {index}.");
            IntPtr nativeChart = MultiChart2DNative.PanelChart(_native, handle);
            if (nativeChart == IntPtr.Zero)
                throw new InvalidOperationException(
                    $"Native multi-chart panel {index} has no chart.");
            var chart = new Chart2D(
                _host, Scene, nativeChart, _fontUri, Theme);
            _panels.Add(new MultiChartPanel2D(this, handle, chart));
        }
    }

    private void DisposePanelWrappers()
    {
        foreach (MultiChartPanel2D panel in _panels)
            panel.Chart.Dispose();
        _panels.Clear();
    }

    private static GraphicItemHandle2D RequireHandle(
        GraphicItemHandle2D handle) => handle.IsValid
        ? handle
        : throw new InvalidOperationException(
            "Native multi-chart returned an invalid root item.");

    private static void Require(bool success)
    {
        if (!success)
            throw new InvalidOperationException(
                "Native RetainedMultiChart2D operation was rejected. " +
                "See native log.");
    }

    private void ThrowIfDisposed()
    {
        if (_disposed || _native == IntPtr.Zero)
            throw new ObjectDisposedException(nameof(MultiChart2D));
    }
}

internal static class MultiChart2DNative
{
    private const string Dll = "tcplot";

    [DllImport(Dll, EntryPoint = "tc_retained_multi_chart2d_create")]
    internal static extern IntPtr Create(
        IntPtr gpuHost,
        PlotRect2D viewport,
        PlotRange2D initialRange,
        nuint panelCount,
        float panelHeight,
        float panelGap,
        [MarshalAs(UnmanagedType.LPUTF8Str)] string fontUri,
        float pixelScale,
        ref Chart2DNative.Theme theme);

    [DllImport(Dll, EntryPoint = "tc_retained_multi_chart2d_destroy")]
    internal static extern void Destroy(IntPtr chart);

    [DllImport(Dll, EntryPoint = "tc_retained_multi_chart2d_scene")]
    internal static extern VisualSceneNativeHandle Scene(IntPtr chart);

    [DllImport(Dll, EntryPoint = "tc_retained_multi_chart2d_root")]
    internal static extern GraphicItemHandle2D Root(IntPtr chart);

    [DllImport(Dll, EntryPoint = "tc_retained_multi_chart2d_snapshot")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool GetSnapshot(
        IntPtr chart,
        out NativeMultiChartSnapshot2D snapshot);

    [DllImport(Dll, EntryPoint = "tc_retained_multi_chart2d_set_viewport")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool SetViewport(
        IntPtr chart,
        PlotRect2D viewport,
        float pixelScale);

    [DllImport(Dll, EntryPoint = "tc_retained_multi_chart2d_set_panel_count")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool SetPanelCount(IntPtr chart, nuint count);

    [DllImport(Dll, EntryPoint = "tc_retained_multi_chart2d_set_panel_layout")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool SetPanelLayout(
        IntPtr chart,
        float panelHeight,
        float panelGap);

    [DllImport(Dll, EntryPoint = "tc_retained_multi_chart2d_set_scroll_offset")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool SetScrollOffset(IntPtr chart, float offset);

    [DllImport(Dll, EntryPoint = "tc_retained_multi_chart2d_set_shared_x")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool SetSharedX(
        IntPtr chart,
        double minimum,
        double maximum);

    [DllImport(Dll, EntryPoint = "tc_retained_multi_chart2d_set_theme")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool SetTheme(
        IntPtr chart,
        ref Chart2DNative.Theme theme);

    [DllImport(Dll, EntryPoint = "tc_retained_multi_chart2d_panel_at")]
    internal static extern MultiChartPanelHandle2D PanelAt(
        IntPtr chart,
        nuint index);

    [DllImport(Dll, EntryPoint = "tc_retained_multi_chart2d_panel_is_valid")]
    [return: MarshalAs(UnmanagedType.I1)]
    internal static extern bool PanelIsValid(
        IntPtr chart,
        MultiChartPanelHandle2D panel);

    [DllImport(Dll, EntryPoint = "tc_retained_multi_chart2d_panel_chart")]
    internal static extern IntPtr PanelChart(
        IntPtr chart,
        MultiChartPanelHandle2D panel);
}
