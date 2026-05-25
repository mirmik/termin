using System;
using OpenTK.Graphics.OpenGL4;
using Termin.Native;

namespace Termin.Wpf;

public sealed class Tgfx2GlWpfTexturePresenter : IDisposable
{
    private const int PixelFormatRgba8UNorm = 3;
    private const uint TextureUsageSampled = 1u << 0;
    private const uint TextureUsageColorAttachment = 1u << 2;
    private const uint TextureUsageCopyDst = 1u << 5;

    private int _textureId;
    private int _readFbo;
    private int _width;
    private int _height;
    private uint _targetTextureHandle;
    private bool _disposed;

    public void Present(uint sourceTextureHandle, int width, int height, int destinationFramebuffer = 0)
    {
        if (sourceTextureHandle == 0 || width <= 0 || height <= 0) return;

        EnsureTarget(width, height);
        if (_targetTextureHandle == 0) return;

        TerminCore.Tgfx2BlitTexture(sourceTextureHandle, _targetTextureHandle, width, height);
        BlitTargetTextureToFramebuffer(width, height, destinationFramebuffer);
    }

    private void EnsureTarget(int width, int height)
    {
        if (_textureId != 0 && _width == width && _height == height) return;

        ReleaseTarget();

        _textureId = GL.GenTexture();
        GL.BindTexture(TextureTarget.Texture2D, _textureId);
        GL.TexParameter(TextureTarget.Texture2D, TextureParameterName.TextureMinFilter, (int)TextureMinFilter.Nearest);
        GL.TexParameter(TextureTarget.Texture2D, TextureParameterName.TextureMagFilter, (int)TextureMagFilter.Nearest);
        GL.TexParameter(TextureTarget.Texture2D, TextureParameterName.TextureWrapS, (int)TextureWrapMode.ClampToEdge);
        GL.TexParameter(TextureTarget.Texture2D, TextureParameterName.TextureWrapT, (int)TextureWrapMode.ClampToEdge);
        GL.TexImage2D(TextureTarget.Texture2D, 0, PixelInternalFormat.Rgba8,
                      width, height, 0, PixelFormat.Rgba, PixelType.UnsignedByte, IntPtr.Zero);
        GL.BindTexture(TextureTarget.Texture2D, 0);

        _readFbo = GL.GenFramebuffer();
        _targetTextureHandle = TerminCore.Tgfx2RegisterExternalGlTexture(
            (uint)_textureId,
            (uint)width,
            (uint)height,
            PixelFormatRgba8UNorm,
            TextureUsageSampled | TextureUsageColorAttachment | TextureUsageCopyDst);

        _width = width;
        _height = height;
    }

    private void BlitTargetTextureToFramebuffer(int width, int height, int destinationFramebuffer)
    {
        GL.GetInteger(GetPName.ReadFramebufferBinding, out int prevReadFbo);
        GL.GetInteger(GetPName.DrawFramebufferBinding, out int prevDrawFbo);
        var prevViewport = new int[4];
        GL.GetInteger(GetPName.Viewport, prevViewport);
        bool scissorWasEnabled = GL.IsEnabled(EnableCap.ScissorTest);

        GL.Disable(EnableCap.ScissorTest);
        GL.Viewport(0, 0, width, height);
        GL.BindFramebuffer(FramebufferTarget.ReadFramebuffer, _readFbo);
        GL.FramebufferTexture2D(FramebufferTarget.ReadFramebuffer,
                                FramebufferAttachment.ColorAttachment0,
                                TextureTarget.Texture2D,
                                _textureId,
                                0);
        GL.ReadBuffer(ReadBufferMode.ColorAttachment0);
        int drawFbo = destinationFramebuffer != 0 ? destinationFramebuffer : prevDrawFbo;
        GL.BindFramebuffer(FramebufferTarget.DrawFramebuffer, drawFbo);
        GL.BlitFramebuffer(0, 0, width, height,
                           0, 0, width, height,
                           ClearBufferMask.ColorBufferBit,
                           BlitFramebufferFilter.Nearest);

        GL.BindFramebuffer(FramebufferTarget.ReadFramebuffer, prevReadFbo);
        GL.BindFramebuffer(FramebufferTarget.DrawFramebuffer, prevDrawFbo);
        GL.Viewport(prevViewport[0], prevViewport[1], prevViewport[2], prevViewport[3]);
        if (scissorWasEnabled)
        {
            GL.Enable(EnableCap.ScissorTest);
        }
    }

    private void ReleaseTarget()
    {
        if (_targetTextureHandle != 0)
        {
            TerminCore.Tgfx2DestroyTextureHandle(_targetTextureHandle);
            _targetTextureHandle = 0;
        }
        if (_readFbo != 0)
        {
            GL.DeleteFramebuffer(_readFbo);
            _readFbo = 0;
        }
        if (_textureId != 0)
        {
            GL.DeleteTexture(_textureId);
            _textureId = 0;
        }
        _width = 0;
        _height = 0;
    }

    public void Dispose()
    {
        if (_disposed) return;
        _disposed = true;
        ReleaseTarget();
    }
}
