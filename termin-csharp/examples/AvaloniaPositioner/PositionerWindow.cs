using System;
using System.Diagnostics;
using System.Globalization;
using Avalonia;
using Avalonia.Controls;
using Avalonia.Controls.Primitives;
using Avalonia.Input;
using Avalonia.Layout;
using Avalonia.Media;
using Avalonia.Media.Imaging;
using Avalonia.Platform;
using Avalonia.Threading;

namespace AvaloniaPositioner;

internal sealed partial class PositionerWindow : Window
{
    private const double DefaultOrbit = -45;
    private const double DefaultElevation = 27;
    private const double DefaultDistance = 5.8;
    private static readonly TimeSpan ScanInterval = TimeSpan.FromMilliseconds(33);
    private static readonly IBrush ViewportBackground = new SolidColorBrush(Color.Parse("#151C24"));
    private static readonly IBrush ReadoutColor = new SolidColorBrush(Color.Parse("#A7B7C8"));

    private readonly Action<Exception> _reportFailure;
    private readonly Image _viewport = new()
    {
        Stretch = Stretch.Fill,
        HorizontalAlignment = HorizontalAlignment.Stretch,
        VerticalAlignment = VerticalAlignment.Stretch,
    };
    private readonly Border _viewportHost;
    private readonly Slider _azimuth = new() { Minimum = 0, Maximum = 360 };
    private readonly Slider _height = new() { Minimum = 0, Maximum = 1.6 };
    private readonly TextBlock _azimuthValue = new() { Foreground = ReadoutColor };
    private readonly TextBlock _heightValue = new() { Foreground = ReadoutColor };
    private readonly Button _scan = new() { Content = "Start scan", HorizontalContentAlignment = HorizontalAlignment.Center };
    private readonly DispatcherTimer _timer = new() { Interval = ScanInterval };
    private readonly Stopwatch _scanClock = new();

    private PositionerScene? _scene;
    private WriteableBitmap? _bitmap;
    private IPointer? _orbitPointer;
    private Point _lastPointer;
    private double _scanStartAzimuth;
    private double _orbit = DefaultOrbit;
    private double _elevation = DefaultElevation;
    private double _distance = DefaultDistance;
    private double _bitmapScale;
    private bool _updatingControls;
    private bool _frameRequested;
    private bool _rendering;
    private bool _closed;
    private Exception? _renderError;

    public PositionerWindow(Action<Exception> reportFailure)
    {
        _reportFailure = reportFailure;
        Title = "Az/Z positioner";
        Width = 900;
        Height = 540;
        MinWidth = 650;
        MinHeight = 360;
        WindowStartupLocation = WindowStartupLocation.CenterScreen;
        Background = new SolidColorBrush(Color.Parse("#10151C"));

        _viewportHost = new Border
        {
            Background = ViewportBackground,
            ClipToBounds = true,
            CornerRadius = new CornerRadius(8),
            Child = _viewport,
        };
        _viewportHost.PointerPressed += OnOrbitPressed;
        _viewportHost.PointerMoved += OnOrbitMoved;
        _viewportHost.PointerReleased += OnOrbitReleased;
        _viewportHost.PointerCaptureLost += (_, _) => _orbitPointer = null;
        _viewportHost.PointerWheelChanged += OnZoom;

        var resetCamera = new Button
        {
            Content = "Reset camera",
            HorizontalAlignment = HorizontalAlignment.Stretch,
            HorizontalContentAlignment = HorizontalAlignment.Center,
        };
        resetCamera.Click += (_, _) => SetCamera(DefaultOrbit, DefaultElevation, DefaultDistance);
        _scan.HorizontalAlignment = HorizontalAlignment.Stretch;
        _scan.Click += (_, _) => ToggleScan();

        var sidebar = new StackPanel
        {
            Spacing = 16,
            Children =
            {
                new TextBlock { Text = "Az/Z positioner", FontSize = 21, FontWeight = FontWeight.SemiBold },
                AxisControls("Azimuth", _azimuthValue, _azimuth),
                AxisControls("Carriage height", _heightValue, _height),
                _scan,
                new Separator(),
                new TextBlock { Text = "Drag to orbit · Scroll to zoom", Foreground = ReadoutColor, TextWrapping = TextWrapping.Wrap },
                resetCamera,
            },
        };
        var grid = new Grid
        {
            ColumnDefinitions = new ColumnDefinitions("*,246"),
            Margin = new Thickness(16),
            Children = { _viewportHost },
        };
        Grid.SetColumn(sidebar, 1);
        sidebar.Margin = new Thickness(18, 2, 0, 0);
        grid.Children.Add(sidebar);
        Content = grid;

        UpdateReadouts();
        _azimuth.ValueChanged += OnPoseSliderChanged;
        _height.ValueChanged += OnPoseSliderChanged;
        _timer.Tick += (_, _) => AdvanceScan();
        _viewportHost.SizeChanged += (_, _) => RequestFrame();
        Opened += (_, _) => RequestFrame();
        ScalingChanged += (_, _) => RequestFrame();
        Closed += (_, _) => ReleaseScene();
    }

    private static StackPanel AxisControls(string label, TextBlock readout, Slider slider)
    {
        var labels = new Grid
        {
            ColumnDefinitions = new ColumnDefinitions("*,Auto"),
            Children = { new TextBlock { Text = label } },
        };
        Grid.SetColumn(readout, 1);
        labels.Children.Add(readout);
        return new StackPanel { Spacing = 6, Children = { labels, slider } };
    }

    private void OnPoseSliderChanged(object? sender, RangeBaseValueChangedEventArgs args)
    {
        if (_updatingControls)
            return;
        UpdateReadouts();
        RequestFrame();
    }

    private void SetPose(double azimuthDegrees, double heightMeters)
    {
        _updatingControls = true;
        try
        {
            _azimuth.Value = azimuthDegrees;
            _height.Value = heightMeters;
        }
        finally
        {
            _updatingControls = false;
        }
        UpdateReadouts();
        RequestFrame();
    }

    private void UpdateReadouts()
    {
        _azimuthValue.Text = _azimuth.Value.ToString("0.0", CultureInfo.InvariantCulture) + "°";
        _heightValue.Text = _height.Value.ToString("0.00", CultureInfo.InvariantCulture) + " m";
    }

    private void ToggleScan()
    {
        if (_timer.IsEnabled)
        {
            StopScan();
            return;
        }
        _scanStartAzimuth = _azimuth.Value;
        _scan.Content = "Stop scan";
        _azimuth.IsEnabled = false;
        _height.IsEnabled = false;
        _scanClock.Restart();
        _timer.Start();
    }

    private void StopScan()
    {
        _timer.Stop();
        _scanClock.Stop();
        _scan.Content = "Start scan";
        _azimuth.IsEnabled = true;
        _height.IsEnabled = true;
    }

    private void AdvanceScan()
    {
        double elapsed = _scanClock.Elapsed.TotalSeconds;
        SetPose((_scanStartAzimuth + 36 * elapsed) % 360, 0.8 * (1 - Math.Cos(elapsed * 0.9)));
    }

    private void SetCamera(double orbit, double elevation, double distance)
    {
        _orbit = orbit;
        _elevation = Math.Clamp(elevation, -10, 82);
        _distance = Math.Clamp(distance, 2.7, 14);
        RequestFrame();
    }

    private void OnOrbitPressed(object? sender, PointerPressedEventArgs args)
    {
        if (sender is not Control control || !args.GetCurrentPoint(control).Properties.IsLeftButtonPressed)
            return;
        _orbitPointer = args.Pointer;
        _lastPointer = args.GetPosition(control);
        args.Pointer.Capture(control);
        args.Handled = true;
    }

    private void OnOrbitMoved(object? sender, PointerEventArgs args)
    {
        if (_orbitPointer != args.Pointer || sender is not Control control)
            return;
        Point point = args.GetPosition(control);
        SetCamera(_orbit - (point.X - _lastPointer.X) * 0.45,
            _elevation + (point.Y - _lastPointer.Y) * 0.35, _distance);
        _lastPointer = point;
        args.Handled = true;
    }

    private void OnOrbitReleased(object? sender, PointerReleasedEventArgs args)
    {
        if (_orbitPointer != args.Pointer)
            return;
        _orbitPointer = null;
        args.Pointer.Capture(null);
        args.Handled = true;
    }

    private void OnZoom(object? sender, PointerWheelEventArgs args)
    {
        SetCamera(_orbit, _elevation, _distance * Math.Pow(0.87, args.Delta.Y));
        args.Handled = true;
    }

    private void RequestFrame()
    {
        if (_frameRequested || _closed || _renderError is not null)
            return;
        _frameRequested = true;
        Dispatcher.UIThread.Post(() =>
        {
            if (!_frameRequested)
                return;
            try
            {
                DrawFrame();
            }
            catch (Exception error)
            {
                _renderError = error;
                StopScan();
                _reportFailure(error);
            }
        }, DispatcherPriority.Render);
    }

    private void DrawFrame()
    {
        Dispatcher.UIThread.VerifyAccess();
        _frameRequested = false;
        var bounds = _viewportHost.Bounds;
        if (_rendering || _closed || !IsVisible || bounds.Width < 1 || bounds.Height < 1)
            return;

        _rendering = true;
        try
        {
            double scale = RenderScaling;
            var size = new PixelSize(
                (int)Math.Ceiling(bounds.Width * scale),
                (int)Math.Ceiling(bounds.Height * scale));
            _scene ??= new PositionerScene(size.Width, size.Height);
            if (_bitmap?.PixelSize != size || _bitmapScale != scale)
            {
                _scene.Resize(size.Width, size.Height);
                var next = new WriteableBitmap(size, new Vector(96 * scale, 96 * scale),
                    PixelFormat.Bgra8888, AlphaFormat.Opaque);
                var previous = _bitmap;
                _viewport.Source = next;
                _bitmap = next;
                _bitmapScale = scale;
                previous?.Dispose();
            }
            _scene.SetPose(_azimuth.Value, _height.Value);
            _scene.SetCamera(_orbit, _elevation, _distance);
            using (var frame = _bitmap.Lock())
                _scene.Render(frame.Address, frame.RowBytes);
            _viewport.InvalidateVisual();
        }
        finally
        {
            _rendering = false;
        }
    }

    private void ReleaseScene()
    {
        _closed = true;
        _frameRequested = false;
        _timer.Stop();
        _scanClock.Stop();
        _orbitPointer?.Capture(null);
        _orbitPointer = null;
        var scene = _scene;
        var bitmap = _bitmap;
        _scene = null;
        _bitmap = null;
        _viewport.Source = null;
        try
        {
            bitmap?.Dispose();
        }
        finally
        {
            scene?.Dispose();
        }
    }
}
