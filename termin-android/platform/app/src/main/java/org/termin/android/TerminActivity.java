package org.termin.android;

import android.app.Activity;
import android.graphics.PixelFormat;
import android.os.Bundle;
import android.util.Log;
import android.view.Choreographer;
import android.view.Surface;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;

public final class TerminActivity extends Activity implements SurfaceHolder.Callback {
    private static final String TAG = "TerminActivity";

    static {
        Log.i(TAG, "loading termin_android_jni");
        System.loadLibrary("termin_android_jni");
        Log.i(TAG, "loaded termin_android_jni");
    }

    private SurfaceView surfaceView;
    private boolean surfaceAlive = false;
    private boolean renderLoopRunning = false;
    private int smokeFrameLogCounter = 0;

    private final Choreographer.FrameCallback smokeRenderFrameCallback = new Choreographer.FrameCallback() {
        @Override
        public void doFrame(long frameTimeNanos) {
            if (!surfaceAlive || !renderLoopRunning) {
                renderLoopRunning = false;
                return;
            }
            boolean ok = nativeSmokeRender();
            smokeFrameLogCounter += 1;
            if (!ok || smokeFrameLogCounter % 60 == 0) {
                Log.i(TAG, "smokeRender frame result=" + ok + " frame=" + smokeFrameLogCounter);
            }
            Choreographer.getInstance().postFrameCallback(this);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Log.i(TAG, "onCreate");
        copyAssetTree("shaders", new File(getFilesDir(), "shaders"));
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
        stopRenderLoop();
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
        startRenderLoop();
    }

    @Override
    public void surfaceDestroyed(SurfaceHolder holder) {
        Log.i(TAG, "surfaceDestroyed");
        surfaceAlive = false;
        stopRenderLoop();
        nativeSurfaceDestroyed();
    }

    private static native void nativeInitialize(String appDataDir, String assetRoot, String nativeLibDir);
    private static native void nativeShutdown();
    private static native void nativeSurfaceCreated(Surface surface);
    private static native void nativeSurfaceChanged(int width, int height);
    private static native void nativeSurfaceDestroyed();
    private static native boolean nativeSmokeRender();

    private void startRenderLoop() {
        if (renderLoopRunning) {
            return;
        }
        renderLoopRunning = true;
        smokeFrameLogCounter = 0;
        Log.i(TAG, "renderLoop start");
        Choreographer.getInstance().postFrameCallback(smokeRenderFrameCallback);
    }

    private void stopRenderLoop() {
        if (!renderLoopRunning) {
            return;
        }
        renderLoopRunning = false;
        Choreographer.getInstance().removeFrameCallback(smokeRenderFrameCallback);
        Log.i(TAG, "renderLoop stop");
    }

    private void copyAssetTree(String assetPath, File target) {
        try {
            String[] children = getAssets().list(assetPath);
            if (children == null || children.length == 0) {
                copyAssetFile(assetPath, target);
                return;
            }
            if (!target.isDirectory() && !target.mkdirs()) {
                Log.e(TAG, "failed to create asset directory: " + target);
                return;
            }
            for (String child : children) {
                copyAssetTree(assetPath + "/" + child, new File(target, child));
            }
        } catch (IOException e) {
            Log.e(TAG, "failed to copy asset tree '" + assetPath + "' to " + target, e);
        }
    }

    private void copyAssetFile(String assetPath, File target) throws IOException {
        File parent = target.getParentFile();
        if (parent != null && !parent.isDirectory() && !parent.mkdirs()) {
            Log.e(TAG, "failed to create asset file parent: " + parent);
            return;
        }
        try (InputStream in = getAssets().open(assetPath);
             OutputStream out = new FileOutputStream(target)) {
            byte[] buffer = new byte[8192];
            int read;
            while ((read = in.read(buffer)) != -1) {
                out.write(buffer, 0, read);
            }
        }
        Log.i(TAG, "copied asset " + assetPath + " -> " + target.getAbsolutePath());
    }
}
