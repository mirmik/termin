#include <android/log.h>
#include <android/native_activity.h>
#include <jni.h>

#include <atomic>
#include <chrono>
#include <thread>

#include <termin/openxr/openxr_runtime.hpp>

namespace {

constexpr const char* kLogTag = "TerminOpenXRActivity";

struct NativeActivityState {
    ANativeActivity* activity = nullptr;
    jobject activity_ref = nullptr;
    std::atomic<bool> resumed{false};
    std::atomic<bool> focused{false};
    std::atomic<bool> native_running{false};
    std::atomic<uint32_t> start_generation{0};
};

NativeActivityState g_state;

JNIEnv* attach_env(JavaVM* vm) {
    JNIEnv* env = nullptr;
    if (vm->GetEnv(reinterpret_cast<void**>(&env), JNI_VERSION_1_6) == JNI_OK) {
        return env;
    }
    if (vm->AttachCurrentThread(&env, nullptr) != JNI_OK) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "AttachCurrentThread failed");
        return nullptr;
    }
    return env;
}

void stop_native() {
    if (!g_state.native_running.exchange(false)) {
        return;
    }
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "stop OpenXR smoke");
    termin::openxr::stop_android_color_smoke();
}

void schedule_start_if_ready() {
    if (!g_state.activity || !g_state.activity_ref || g_state.native_running.load()) {
        return;
    }
    if (!g_state.resumed.load() || !g_state.focused.load()) {
        return;
    }

    const uint32_t generation = ++g_state.start_generation;
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "schedule OpenXR smoke start generation=%u", generation);
    std::thread([generation]() {
        std::this_thread::sleep_for(std::chrono::milliseconds(500));
        if (generation != g_state.start_generation.load() ||
            !g_state.activity ||
            !g_state.activity_ref ||
            !g_state.resumed.load() ||
            !g_state.focused.load() ||
            g_state.native_running.load()) {
            __android_log_print(ANDROID_LOG_INFO, kLogTag, "skip OpenXR smoke start generation=%u", generation);
            return;
        }

        termin::openxr::OpenXRAndroidStartResult result =
            termin::openxr::start_android_color_smoke(g_state.activity->vm, g_state.activity_ref);
        g_state.native_running.store(result.started);
        __android_log_print(
            result.started ? ANDROID_LOG_INFO : ANDROID_LOG_ERROR,
            kLogTag,
            "start OpenXR smoke: started=%d stage='%s' detail='%s'",
            result.started ? 1 : 0,
            result.stage ? result.stage : "",
            result.detail ? result.detail : ""
        );
    }).detach();
}

void on_start(ANativeActivity*) {
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "onStart");
}

void on_resume(ANativeActivity*) {
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "onResume focused=%d", g_state.focused.load() ? 1 : 0);
    g_state.resumed.store(true);
    schedule_start_if_ready();
}

void on_pause(ANativeActivity*) {
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "onPause");
    g_state.resumed.store(false);
    ++g_state.start_generation;
    stop_native();
}

void on_stop(ANativeActivity*) {
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "onStop");
}

void on_destroy(ANativeActivity* activity) {
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "onDestroy");
    ++g_state.start_generation;
    stop_native();

    if (g_state.activity_ref) {
        JNIEnv* env = attach_env(activity->vm);
        if (env) {
            env->DeleteGlobalRef(g_state.activity_ref);
        }
    }
    g_state.activity = nullptr;
    g_state.activity_ref = nullptr;
    g_state.resumed.store(false);
    g_state.focused.store(false);
    g_state.native_running.store(false);
    g_state.start_generation.store(0);
}

void on_window_focus_changed(ANativeActivity*, int has_focus) {
    __android_log_print(
        ANDROID_LOG_INFO,
        kLogTag,
        "onWindowFocusChanged focused=%d resumed=%d",
        has_focus ? 1 : 0,
        g_state.resumed.load() ? 1 : 0
    );
    g_state.focused.store(has_focus != 0);
    if (has_focus) {
        schedule_start_if_ready();
    } else {
        ++g_state.start_generation;
    }
}

} // namespace

extern "C" void ANativeActivity_onCreate(
    ANativeActivity* activity,
    void*,
    size_t
) {
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "ANativeActivity_onCreate");
    JNIEnv* env = attach_env(activity->vm);
    if (!env) {
        return;
    }

    g_state.activity = activity;
    g_state.activity_ref = env->NewGlobalRef(activity->clazz);
    if (!g_state.activity_ref) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "NewGlobalRef(activity) failed");
        return;
    }

    activity->callbacks->onStart = on_start;
    activity->callbacks->onResume = on_resume;
    activity->callbacks->onPause = on_pause;
    activity->callbacks->onStop = on_stop;
    activity->callbacks->onDestroy = on_destroy;
    activity->callbacks->onWindowFocusChanged = on_window_focus_changed;
}
