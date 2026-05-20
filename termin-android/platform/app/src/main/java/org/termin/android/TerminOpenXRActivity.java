package org.termin.android;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import android.view.Choreographer;
import android.view.View;

public final class TerminOpenXRActivity extends Activity {
    private static final String TAG = "TerminOpenXRActivity";

    static {
        Log.i(TAG, "loading termin_android_jni");
        System.loadLibrary("termin_android_jni");
        Log.i(TAG, "loaded termin_android_jni");
    }

    private ProbeColorView colorView;
    private boolean loopRunning = false;
    private int frameIndex = 0;

    private final Choreographer.FrameCallback colorFrameCallback = new Choreographer.FrameCallback() {
        @Override
        public void doFrame(long frameTimeNanos) {
            if (!loopRunning) {
                return;
            }
            frameIndex += 1;
            colorView.setColorFrame(frameIndex);
            Choreographer.getInstance().postFrameCallback(this);
        }
    };

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        Log.i(TAG, "onCreate");

        boolean openxrReady = nativeOpenXRProbe(this);
        Log.i(TAG, "OpenXR probe result=" + openxrReady);

        colorView = new ProbeColorView(this);
        setContentView(colorView);
        startColorLoop();
    }

    @Override
    protected void onDestroy() {
        stopColorLoop();
        super.onDestroy();
    }

    private void startColorLoop() {
        if (loopRunning) {
            return;
        }
        loopRunning = true;
        Choreographer.getInstance().postFrameCallback(colorFrameCallback);
        Log.i(TAG, "color marker loop start");
    }

    private void stopColorLoop() {
        if (!loopRunning) {
            return;
        }
        loopRunning = false;
        Choreographer.getInstance().removeFrameCallback(colorFrameCallback);
        Log.i(TAG, "color marker loop stop");
    }

    private static native boolean nativeOpenXRProbe(Activity activity);

    private static final class ProbeColorView extends View {
        private int color = 0xff000000;

        ProbeColorView(Activity activity) {
            super(activity);
        }

        void setColorFrame(int frame) {
            int phase = (frame / 30) % 3;
            if (phase == 0) {
                color = 0xffff0000;
            } else if (phase == 1) {
                color = 0xff00ff00;
            } else {
                color = 0xff0000ff;
            }
            setBackgroundColor(color);
        }
    }
}
