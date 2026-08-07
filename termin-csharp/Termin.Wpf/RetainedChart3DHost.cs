using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Termin.Native;

namespace Termin.Wpf;

/// <summary>
/// Presents a retained Chart3D through one D3DImage and overlays ordinary WPF
/// controls. The chart remains owned by the caller.
/// </summary>
public sealed class RetainedChart3DHost : Grid, IDisposable
{
    private readonly Tgfx2D3D11ImageHost _renderHost = new();
    private readonly Canvas _portalLayer = new();
    private readonly Dictionary<FrameworkElement, Rect> _portals = new();
    private RetainedChart3D? _chart;
    private bool _renderingSubscribed;
    private bool _disposed;
    private int _lastWidth;
    private int _lastHeight;
    private float _lastPixelScale;

    public RetainedChart3DHost()
    {
        ClipToBounds = true;
        Children.Add(_renderHost);
        Children.Add(_portalLayer);
        Panel.SetZIndex(_portalLayer, 1);

        _renderHost.FramebufferMouseDown += OnMouseDown;
        _renderHost.FramebufferMouseMove += OnMouseMove;
        _renderHost.FramebufferMouseUp += OnMouseUp;
        _renderHost.FramebufferMouseWheel += OnMouseWheel;
        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
    }

    public RetainedChart3D? Chart => _chart;
    public Tgfx2D3D11ImageHost RenderHost => _renderHost;

    public event EventHandler<RetainedSceneFramebufferChangedEventArgs>?
        FramebufferChanged;
    public event EventHandler<RetainedSceneRenderFailedEventArgs>?
        RenderFailed;

    public void Attach(RetainedChart3D chart)
    {
        ThrowIfDisposed();
        _chart = chart ?? throw new ArgumentNullException(nameof(chart));
        _lastWidth = 0;
        _lastHeight = 0;
        _lastPixelScale = 0;
        SubscribeRendering();
    }

    public void Detach()
    {
        UnsubscribeRendering();
        _chart = null;
    }

    public void AddPortal(FrameworkElement content, Rect bounds)
    {
        ThrowIfDisposed();
        if (content is null)
            throw new ArgumentNullException(nameof(content));
        if (content.Parent is not null)
            throw new ArgumentException(
                "Portal content already has a WPF parent.", nameof(content));
        ValidateBounds(bounds);
        _portals.Add(content, bounds);
        _portalLayer.Children.Add(content);
        ApplyPortalBounds(content, bounds);
    }

    public void SetPortalBounds(FrameworkElement content, Rect bounds)
    {
        ThrowIfDisposed();
        if (!_portals.ContainsKey(content))
            throw new ArgumentException(
                "The control is not attached to this portal layer.",
                nameof(content));
        ValidateBounds(bounds);
        _portals[content] = bounds;
        ApplyPortalBounds(content, bounds);
    }

    public bool RemovePortal(FrameworkElement content)
    {
        ThrowIfDisposed();
        if (!_portals.Remove(content))
            return false;
        _portalLayer.Children.Remove(content);
        return true;
    }

    public void RenderFrame()
    {
        ThrowIfDisposed();
        if (_chart is null)
            return;

        int width = Math.Max(1, _renderHost.FramebufferWidth);
        int height = Math.Max(1, _renderHost.FramebufferHeight);
        DpiScale dpi = VisualTreeHelper.GetDpi(this);
        float pixelScale = (float)dpi.DpiScaleX;
        if (width != _lastWidth ||
            height != _lastHeight ||
            Math.Abs(pixelScale - _lastPixelScale) > 0.0001f)
        {
            _lastWidth = width;
            _lastHeight = height;
            _lastPixelScale = pixelScale;
            FramebufferChanged?.Invoke(
                this,
                new RetainedSceneFramebufferChangedEventArgs(
                    width, height, pixelScale));
        }

        uint texture = _chart.RenderToTextureHandleId(width, height);
        if (!_renderHost.Present(texture, width, height))
            throw new InvalidOperationException(
                "Failed to present retained Chart3D through the WPF D3DImage bridge.");
    }

    public void Dispose()
    {
        if (_disposed)
            return;
        UnsubscribeRendering();
        _renderHost.ReleaseNativeResources();
        _portals.Clear();
        _portalLayer.Children.Clear();
        _chart = null;
        _disposed = true;
        GC.SuppressFinalize(this);
    }

    private void OnLoaded(object sender, RoutedEventArgs e)
    {
        SubscribeRendering();
    }

    private void OnUnloaded(object sender, RoutedEventArgs e)
    {
        UnsubscribeRendering();
        _renderHost.ReleaseNativeResources();
        _chart?.ReleaseGpuResources();
    }

    private void SubscribeRendering()
    {
        if (_renderingSubscribed || !IsLoaded || _chart is null)
            return;
        CompositionTarget.Rendering += OnRendering;
        _renderingSubscribed = true;
    }

    private void UnsubscribeRendering()
    {
        if (!_renderingSubscribed)
            return;
        CompositionTarget.Rendering -= OnRendering;
        _renderingSubscribed = false;
    }

    private void OnRendering(object? sender, EventArgs e)
    {
        try
        {
            RenderFrame();
        }
        catch (Exception error)
        {
            Trace.TraceError($"RetainedChart3DHost rendering stopped: {error}");
            UnsubscribeRendering();
            RenderFailed?.Invoke(
                this, new RetainedSceneRenderFailedEventArgs(error));
        }
    }

    private void OnMouseDown(
        object? sender,
        Tgfx2D3D11MouseButtonEventArgs e)
    {
        if (_chart is null)
            return;
        _renderHost.FocusNativeWindow();
        e.Handled = _chart.PointerDown(e.X, e.Y, e.Button);
    }

    private void OnMouseMove(
        object? sender,
        Tgfx2D3D11MouseMoveEventArgs e)
    {
        _chart?.PointerMove(e.X, e.Y);
    }

    private void OnMouseUp(
        object? sender,
        Tgfx2D3D11MouseButtonEventArgs e)
    {
        if (_chart is null)
            return;
        _chart.PointerUp(e.X, e.Y, e.Button);
        e.Handled = true;
    }

    private void OnMouseWheel(
        object? sender,
        Tgfx2D3D11MouseWheelEventArgs e)
    {
        if (_chart is null)
            return;
        e.Handled = _chart.Wheel(e.X, e.Y, e.Delta);
    }

    private static void ValidateBounds(Rect bounds)
    {
        if (bounds.IsEmpty || bounds.Width < 0 || bounds.Height < 0 ||
            double.IsNaN(bounds.X) || double.IsNaN(bounds.Y) ||
            double.IsNaN(bounds.Width) || double.IsNaN(bounds.Height) ||
            double.IsInfinity(bounds.X) || double.IsInfinity(bounds.Y) ||
            double.IsInfinity(bounds.Width) || double.IsInfinity(bounds.Height))
            throw new ArgumentException(
                "Portal bounds must be finite and non-negative.",
                nameof(bounds));
    }

    private static void ApplyPortalBounds(
        FrameworkElement content,
        Rect bounds)
    {
        Canvas.SetLeft(content, bounds.X);
        Canvas.SetTop(content, bounds.Y);
        content.Width = bounds.Width;
        content.Height = bounds.Height;
    }

    private void ThrowIfDisposed()
    {
        if (_disposed)
            throw new ObjectDisposedException(nameof(RetainedChart3DHost));
    }
}
