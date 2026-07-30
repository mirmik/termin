package org.termin.android;

import android.app.Activity;
import android.content.res.Configuration;
import android.graphics.PixelFormat;
import android.graphics.Insets;
import android.os.Bundle;
import android.os.Build;
import android.util.DisplayMetrics;
import android.util.Log;
import android.view.Choreographer;
import android.view.DisplayCutout;
import android.view.Surface;
import android.view.SurfaceHolder;
import android.view.SurfaceView;
import android.view.MotionEvent;
import android.view.WindowInsets;
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
    private int renderFrameLogCounter = 0;
    private WindowInsets currentWindowInsets;

    private final Choreographer.FrameCallback renderFrameCallback = new Choreographer.FrameCallback() {
        @Override
        public void doFrame(long frameTimeNanos) {
            if (!surfaceAlive || !renderLoopRunning) {
                renderLoopRunning = false;
                return;
            }
            boolean ok = nativeRenderFrame(frameTimeNanos);
            renderFrameLogCounter += 1;
            if (!ok || renderFrameLogCounter % 60 == 0) {
                Log.i(TAG, "renderFrame result=" + ok + " frame=" + renderFrameLogCounter);
            }
            if (!ok) {
                renderLoopRunning = false;
                Log.e(TAG, "renderLoop stopped after renderFrame failure");
                return;
            }
            Choreographer.getInstance().postFrameCallback(this);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Log.i(TAG, "onCreate");
        copyAssetTree("", getFilesDir());
        nativeInitialize(
                getFilesDir().getAbsolutePath(),
                getFilesDir().getAbsolutePath(),
                getApplicationInfo().nativeLibraryDir
        );

        surfaceView = new SurfaceView(this);
        surfaceView.setZOrderOnTop(true);
        surfaceView.getHolder().setFormat(PixelFormat.OPAQUE);
        surfaceView.getHolder().addCallback(this);
        surfaceView.setOnTouchListener((view, event) -> {
            dispatchPointerEvent(event);
            return true;
        });
        surfaceView.setOnApplyWindowInsetsListener((view, insets) -> {
            currentWindowInsets = insets;
            publishPresentationMetrics();
            return insets;
        });
        setContentView(surfaceView);
        publishPresentationMetrics();
        surfaceView.requestApplyInsets();
    }

    @Override
    public void onConfigurationChanged(Configuration configuration) {
        super.onConfigurationChanged(configuration);
        Log.i(TAG, "onConfigurationChanged densityDpi=" + configuration.densityDpi
                + " fontScale=" + configuration.fontScale
                + " orientation=" + configuration.orientation);
        publishPresentationMetrics();
        surfaceView.requestApplyInsets();
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
        stopRenderLoop();
        nativeSurfaceChanged(width, height);
        publishPresentationMetrics();
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
    private static native void nativePresentationMetricsChanged(
            float densityScale,
            float fontScale,
            float safeInsetLeft,
            float safeInsetTop,
            float safeInsetRight,
            float safeInsetBottom);
    private static native void nativeSurfaceDestroyed();
    private static native void nativePointer(
            long pointerId,
            int device,
            int phase,
            float x,
            float y,
            float pressure);
    private static native boolean nativeRenderFrame(long frameTimeNanos);

    private static final int POINTER_MOUSE = 0;
    private static final int POINTER_TOUCH = 1;
    private static final int POINTER_PEN = 2;
    private static final int POINTER_DOWN = 0;
    private static final int POINTER_MOVE = 1;
    private static final int POINTER_UP = 2;
    private static final int POINTER_CANCEL = 3;

    private void dispatchPointerEvent(MotionEvent event) {
        int action = event.getActionMasked();
        if (action == MotionEvent.ACTION_MOVE) {
            for (int index = 0; index < event.getPointerCount(); ++index) {
                dispatchPointer(event, index, POINTER_MOVE);
            }
            return;
        }
        if (action == MotionEvent.ACTION_CANCEL) {
            for (int index = 0; index < event.getPointerCount(); ++index) {
                dispatchPointer(event, index, POINTER_CANCEL);
            }
            return;
        }

        int phase;
        if (action == MotionEvent.ACTION_DOWN || action == MotionEvent.ACTION_POINTER_DOWN) {
            phase = POINTER_DOWN;
        } else if (action == MotionEvent.ACTION_UP || action == MotionEvent.ACTION_POINTER_UP) {
            phase = POINTER_UP;
        } else {
            return;
        }
        dispatchPointer(event, event.getActionIndex(), phase);
    }

    private void dispatchPointer(MotionEvent event, int index, int phase) {
        nativePointer(
                event.getPointerId(index),
                pointerDevice(event.getToolType(index)),
                phase,
                event.getX(index),
                event.getY(index),
                event.getPressure(index)
        );
    }

    private static int pointerDevice(int toolType) {
        if (toolType == MotionEvent.TOOL_TYPE_MOUSE) {
            return POINTER_MOUSE;
        }
        if (toolType == MotionEvent.TOOL_TYPE_STYLUS
                || toolType == MotionEvent.TOOL_TYPE_ERASER) {
            return POINTER_PEN;
        }
        return POINTER_TOUCH;
    }

    private void publishPresentationMetrics() {
        DisplayMetrics displayMetrics = getResources().getDisplayMetrics();
        float density = displayMetrics.density;
        float fontScale = density > 0.0f
                ? displayMetrics.scaledDensity / density
                : 0.0f;
        int left = 0;
        int top = 0;
        int right = 0;
        int bottom = 0;

        if (currentWindowInsets != null) {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.R) {
                Insets insets = currentWindowInsets.getInsets(
                        WindowInsets.Type.systemBars()
                                | WindowInsets.Type.displayCutout());
                left = insets.left;
                top = insets.top;
                right = insets.right;
                bottom = insets.bottom;
            } else {
                left = currentWindowInsets.getSystemWindowInsetLeft();
                top = currentWindowInsets.getSystemWindowInsetTop();
                right = currentWindowInsets.getSystemWindowInsetRight();
                bottom = currentWindowInsets.getSystemWindowInsetBottom();
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.P) {
                    DisplayCutout cutout = currentWindowInsets.getDisplayCutout();
                    if (cutout != null) {
                        left = Math.max(left, cutout.getSafeInsetLeft());
                        top = Math.max(top, cutout.getSafeInsetTop());
                        right = Math.max(right, cutout.getSafeInsetRight());
                        bottom = Math.max(bottom, cutout.getSafeInsetBottom());
                    }
                }
            }
        }

        Log.i(TAG, "presentationMetrics density=" + density
                + " fontScale=" + fontScale
                + " insets=[" + left + "," + top + "," + right + "," + bottom + "]");
        nativePresentationMetricsChanged(
                density,
                fontScale,
                left,
                top,
                right,
                bottom);
    }

    private void startRenderLoop() {
        if (renderLoopRunning) {
            return;
        }
        renderLoopRunning = true;
        renderFrameLogCounter = 0;
        Log.i(TAG, "renderLoop start");
        Choreographer.getInstance().postFrameCallback(renderFrameCallback);
    }

    private void stopRenderLoop() {
        if (!renderLoopRunning) {
            return;
        }
        renderLoopRunning = false;
        Choreographer.getInstance().removeFrameCallback(renderFrameCallback);
        Log.i(TAG, "renderLoop stop");
    }

    private void copyAssetTree(String assetPath, File target) {
        try {
            String[] children = getAssets().list(assetPath);
            if (children == null || children.length == 0) {
                if (assetPath.isEmpty()) {
                    return;
                }
                copyAssetFile(assetPath, target);
                return;
            }
            if (!target.isDirectory() && !target.mkdirs()) {
                Log.e(TAG, "failed to create asset directory: " + target);
                return;
            }
            for (String child : children) {
                String childAssetPath = assetPath.isEmpty() ? child : assetPath + "/" + child;
                copyAssetTree(childAssetPath, new File(target, child));
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
