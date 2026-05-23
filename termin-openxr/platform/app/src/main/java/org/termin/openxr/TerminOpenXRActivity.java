package org.termin.openxr;

import android.app.Activity;
import android.os.Bundle;
import android.util.Log;
import android.view.View;

public final class TerminOpenXRActivity extends Activity {
    private static final String TAG = "TerminOpenXRActivity";
    private boolean nativeRunning = false;
    private boolean startPending = false;

    private final Runnable startNativeRunnable = new Runnable() {
        @Override
        public void run() {
            startPending = false;
            if (!nativeRunning) {
                nativeRunning = nativeStart(TerminOpenXRActivity.this);
            }
        }
    };

    static {
        Log.i(TAG, "loading termin_openxr_smoke_jni");
        System.loadLibrary("termin_openxr_smoke_jni");
        Log.i(TAG, "loaded termin_openxr_smoke_jni");
    }

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        getWindow().getDecorView().setSystemUiVisibility(
                View.SYSTEM_UI_FLAG_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_IMMERSIVE_STICKY
                        | View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                        | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
                        | View.SYSTEM_UI_FLAG_LAYOUT_STABLE);
    }

    @Override
    protected void onResume() {
        super.onResume();
        if (!nativeRunning && !startPending) {
            startPending = true;
            getWindow().getDecorView().postDelayed(startNativeRunnable, 500);
        }
    }

    @Override
    protected void onDestroy() {
        if (startPending) {
            getWindow().getDecorView().removeCallbacks(startNativeRunnable);
            startPending = false;
        }
        if (nativeRunning) {
            nativeStop();
            nativeRunning = false;
        }
        super.onDestroy();
    }

    private static native boolean nativeStart(Activity activity);
    private static native void nativeStop();
}
