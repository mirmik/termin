package org.termin.android;

import android.app.Activity;
import android.graphics.PixelFormat;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import android.view.Surface;
import android.view.SurfaceHolder;
import android.view.SurfaceView;

public final class TerminActivity extends Activity implements SurfaceHolder.Callback {
    private static final String TAG = "TerminActivity";

    static {
        Log.i(TAG, "loading termin_android_jni");
        System.loadLibrary("termin_android_jni");
        Log.i(TAG, "loaded termin_android_jni");
    }

    private SurfaceView surfaceView;
    private final Handler handler = new Handler(Looper.getMainLooper());
    private boolean surfaceAlive = false;
    private int smokeFramesQueued = 0;

    private final Runnable smokeRenderRunnable = new Runnable() {
        @Override
        public void run() {
            if (!surfaceAlive) {
                Log.i(TAG, "smokeRender skipped: surface is not alive");
                return;
            }
            boolean ok = nativeSmokeRender();
            Log.i(TAG, "smokeRender frame result=" + ok);
            smokeFramesQueued -= 1;
            if (surfaceAlive && smokeFramesQueued > 0) {
                handler.postDelayed(this, 250);
            }
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Log.i(TAG, "onCreate");
        nativeInitialize(
                getFilesDir().getAbsolutePath(),
                getFilesDir().getAbsolutePath(),
                getApplicationInfo().nativeLibraryDir
        );

        surfaceView = new SurfaceView(this);
        surfaceView.setZOrderOnTop(true);
        surfaceView.getHolder().setFormat(PixelFormat.OPAQUE);
        surfaceView.getHolder().addCallback(this);
        setContentView(surfaceView);
    }

    @Override
    protected void onDestroy() {
        Log.i(TAG, "onDestroy");
        handler.removeCallbacks(smokeRenderRunnable);
        nativeShutdown();
        super.onDestroy();
    }

    @Override
    public void surfaceCreated(SurfaceHolder holder) {
        Log.i(TAG, "surfaceCreated");
        surfaceAlive = true;
        Surface surface = holder.getSurface();
        if (surface != null) {
            nativeSurfaceCreated(surface);
        } else {
            Log.e(TAG, "surfaceCreated with null Surface");
        }
    }

    @Override
    public void surfaceChanged(SurfaceHolder holder, int format, int width, int height) {
        Log.i(TAG, "surfaceChanged format=" + format + " size=" + width + "x" + height);
        nativeSurfaceChanged(width, height);
        smokeFramesQueued = 4;
        handler.removeCallbacks(smokeRenderRunnable);
        handler.postDelayed(smokeRenderRunnable, 100);
    }

    @Override
    public void surfaceDestroyed(SurfaceHolder holder) {
        Log.i(TAG, "surfaceDestroyed");
        surfaceAlive = false;
        smokeFramesQueued = 0;
        handler.removeCallbacks(smokeRenderRunnable);
        nativeSurfaceDestroyed();
    }

    private static native void nativeInitialize(String appDataDir, String assetRoot, String nativeLibDir);
    private static native void nativeShutdown();
    private static native void nativeSurfaceCreated(Surface surface);
    private static native void nativeSurfaceChanged(int width, int height);
    private static native void nativeSurfaceDestroyed();
    private static native boolean nativeSmokeRender();
}
