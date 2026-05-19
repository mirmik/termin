package org.termin.android;

import android.app.Activity;
import android.os.Bundle;
import android.view.Surface;
import android.view.SurfaceHolder;
import android.view.SurfaceView;

public final class TerminActivity extends Activity implements SurfaceHolder.Callback {
    static {
        System.loadLibrary("termin_android_jni");
    }

    private SurfaceView surfaceView;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        nativeInitialize(
                getFilesDir().getAbsolutePath(),
                getFilesDir().getAbsolutePath(),
                getApplicationInfo().nativeLibraryDir
        );

        surfaceView = new SurfaceView(this);
        surfaceView.getHolder().addCallback(this);
        setContentView(surfaceView);
    }

    @Override
    protected void onDestroy() {
        nativeShutdown();
        super.onDestroy();
    }

    @Override
    public void surfaceCreated(SurfaceHolder holder) {
        Surface surface = holder.getSurface();
        if (surface != null) {
            nativeSurfaceCreated(surface);
        }
    }

    @Override
    public void surfaceChanged(SurfaceHolder holder, int format, int width, int height) {
        nativeSurfaceChanged(width, height);
    }

    @Override
    public void surfaceDestroyed(SurfaceHolder holder) {
        nativeSurfaceDestroyed();
    }

    private static native void nativeInitialize(String appDataDir, String assetRoot, String nativeLibDir);
    private static native void nativeShutdown();
    private static native void nativeSurfaceCreated(Surface surface);
    private static native void nativeSurfaceChanged(int width, int height);
    private static native void nativeSurfaceDestroyed();
}

