using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using Termin.Native;

namespace Termin.Wpf;

public sealed class RetainedSceneFramebufferChangedEventArgs : EventArgs
{
    public RetainedSceneFramebufferChangedEventArgs(
        int width,
        int height,
        float pixelScale)
    {
        Width = width;
        Height = height;
        PixelScale = pixelScale;
    }

    public int Width { get; }
    public int Height { get; }
    public float PixelScale { get; }
}

public sealed class RetainedSceneRenderFailedEventArgs : EventArgs
{
    public RetainedSceneRenderFailedEventArgs(Exception error)
    {
        Error = error ?? throw new ArgumentNullException(nameof(error));
    }

    public Exception Error { get; }
}

/// <summary>
/// WPF presentation host for any retained TcVisualScene2D. Native scene
/// items may also serve as layout anchors for ordinary WPF controls.
/// </summary>
public sealed class RetainedScene2DHost : Grid, IDisposable
{
    private sealed class Portal
    {
        public Portal(GraphicItemRef2D anchor, FrameworkElement content)
        {
            Anchor = anchor;
            Content = content;
        }

        public GraphicItemRef2D Anchor { get; }
        public FrameworkElement Content { get; }
    }

    private readonly Tgfx2D3D11ImageHost _renderHost = new();
    private readonly Canvas _portalLayer = new();
    private readonly List<Portal> _portals = new();
    private RetainedSceneRenderer2D? _renderer;
    private TcVisualScene2D? _scene;
    private bool _renderingSubscribed;
    private bool _disposed;
    private int _lastWidth;
    private int _lastHeight;
    private float _lastPixelScale;

    public RetainedScene2DHost()
    {
        ClipToBounds = true;
        Children.Add(_renderHost);
        Children.Add(_portalLayer);
        Panel.SetZIndex(_portalLayer, 1);

        Loaded += OnLoaded;
        Unloaded += OnUnloaded;
    }

    public TcVisualScene2D? Scene => _scene;
    public Tgfx2D3D11ImageHost RenderHost => _renderHost;

    public event EventHandler<RetainedSceneFramebufferChangedEventArgs>?
        FramebufferChanged;
    public event EventHandler<RetainedSceneRenderFailedEventArgs>?
        RenderFailed;

    public void Attach(GpuHost host, TcVisualScene2D scene)
    {
        ThrowIfDisposed();
        if (host is null)
            throw new ArgumentNullException(nameof(host));
        if (scene is null)
            throw new ArgumentNullException(nameof(scene));

        Detach();
        _renderer = new RetainedSceneRenderer2D(host, scene);
        _scene = scene;
        _lastWidth = 0;
        _lastHeight = 0;
        _lastPixelScale = 0;
        SubscribeRendering();
    }

    public void Detach()
    {
        UnsubscribeRendering();
        ClearPortals();
        _renderer?.Dispose();
        _renderer = null;
        _scene = null;
        _lastWidth = 0;
        _lastHeight = 0;
        _lastPixelScale = 0;
    }

    public void AddPortal(
        GraphicItemRef2D anchor,
        FrameworkElement content)
    {
        ThrowIfDisposed();
        if (anchor is null)
            throw new ArgumentNullException(nameof(anchor));
        if (content is null)
            throw new ArgumentNullException(nameof(content));
        if (_scene is null)
            throw new InvalidOperationException(
                "Attach a retained scene before adding a portal.");
        if (!anchor.IsValid || anchor.Handle.SceneId != _scene.Id)
            throw new ArgumentException(
                "Portal anchor must be a live item in the attached scene.",
                nameof(anchor));
        if (content.Parent is not null)
            throw new ArgumentException(
                "Portal content already has a WPF parent.",
                nameof(content));

        _portals.Add(new Portal(anchor, content));
        _portalLayer.Children.Add(content);
        UpdatePortals();
    }

    public bool RemovePortal(FrameworkElement content)
    {
        ThrowIfDisposed();
        if (content is null)
            throw new ArgumentNullException(nameof(content));

        int index = _portals.FindIndex(
            portal => ReferenceEquals(portal.Content, content));
        if (index < 0)
            return false;
        _portals.RemoveAt(index);
        _portalLayer.Children.Remove(content);
        return true;
    }

    public void ClearPortals()
    {
        _portals.Clear();
        _portalLayer.Children.Clear();
    }

    public void RenderFrame()
    {
        ThrowIfDisposed();
        if (_renderer is null)
            return;

        int width = Math.Max(1, _renderHost.FramebufferWidth);
        int height = Math.Max(1, _renderHost.FramebufferHeight);
        DpiScale dpi = VisualTreeHelper.GetDpi(this);
        float pixelScale = (float)dpi.DpiScaleX;
        if (width != _lastWidth ||
            height != _lastHeight ||
            Math.Abs(pixelScale - _lastPixelScale) > 0.0001f) {
            _lastWidth = width;
            _lastHeight = height;
            _lastPixelScale = pixelScale;
            FramebufferChanged?.Invoke(
                this,
                new RetainedSceneFramebufferChangedEventArgs(
                    width, height, pixelScale));
        }

        uint texture = _renderer.RenderToTextureHandleId(width, height);
        if (!_renderHost.Present(texture, width, height))
            throw new InvalidOperationException(
                "Failed to present retained scene through the WPF D3DImage bridge.");
        UpdatePortals();
    }

    public void Dispose()
    {
        if (_disposed)
            return;
        UnsubscribeRendering();
        ClearPortals();
        _renderHost.ReleaseNativeResources();
        _renderer?.Dispose();
        _renderer = null;
        _scene = null;
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
        _renderer?.ReleaseGpuResources();
    }

    private void SubscribeRendering()
    {
        if (_renderingSubscribed || !IsLoaded || _renderer is null)
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
            Trace.TraceError(
                $"RetainedScene2DHost rendering stopped: {error}");
            UnsubscribeRendering();
            RenderFailed?.Invoke(
                this, new RetainedSceneRenderFailedEventArgs(error));
        }
    }

    private void UpdatePortals()
    {
        DpiScale dpi = VisualTreeHelper.GetDpi(this);
        double scaleX = dpi.DpiScaleX;
        double scaleY = dpi.DpiScaleY;

        foreach (Portal portal in _portals)
        {
            if (!portal.Anchor.IsValid ||
                !portal.Anchor.TryGetWorldBounds(out VisualBounds2f bounds))
            {
                portal.Content.Visibility = Visibility.Collapsed;
                continue;
            }

            portal.Content.Visibility = Visibility.Visible;
            Canvas.SetLeft(portal.Content, bounds.X0 / scaleX);
            Canvas.SetTop(portal.Content, bounds.Y0 / scaleY);
            portal.Content.Width =
                Math.Max(0, (bounds.X1 - bounds.X0) / scaleX);
            portal.Content.Height =
                Math.Max(0, (bounds.Y1 - bounds.Y0) / scaleY);
        }
    }

    private void ThrowIfDisposed()
    {
        if (_disposed)
            throw new ObjectDisposedException(nameof(RetainedScene2DHost));
    }
}
