#include <jni.h>

#include <android/native_window_jni.h>
#include <android/log.h>

#include <termin/android/bootstrap.h>
#ifdef TERMIN_QUEST_OPENXR
#include <termin/openxr/openxr_runtime.hpp>
#endif

namespace {

constexpr const char* kLogTag = "TerminAndroidJNI";

const char* jstring_chars(JNIEnv* env, jstring value) {
    if (!value) {
        return nullptr;
    }
    return env->GetStringUTFChars(value, nullptr);
}

void release_jstring_chars(JNIEnv* env, jstring value, const char* chars) {
    if (value && chars) {
        env->ReleaseStringUTFChars(value, chars);
    }
}

} // namespace

extern "C" JNIEXPORT void JNICALL
Java_org_termin_android_TerminActivity_nativeInitialize(
    JNIEnv* env,
    jclass,
    jstring app_data_dir,
    jstring asset_root,
    jstring native_lib_dir
) {
    const char* app_data_dir_chars = jstring_chars(env, app_data_dir);
    const char* asset_root_chars = jstring_chars(env, asset_root);
    const char* native_lib_dir_chars = jstring_chars(env, native_lib_dir);

    __android_log_print(
        ANDROID_LOG_INFO,
        kLogTag,
        "nativeInitialize app_data_dir='%s' asset_root='%s' native_lib_dir='%s'",
        app_data_dir_chars ? app_data_dir_chars : "",
        asset_root_chars ? asset_root_chars : "",
        native_lib_dir_chars ? native_lib_dir_chars : ""
    );
    termin_android_config config{};
    config.app_data_dir = app_data_dir_chars;
    config.asset_root = asset_root_chars;
    config.native_lib_dir = native_lib_dir_chars;

    if (!termin_android_initialize(&config)) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "termin_android_initialize failed");
    }

    release_jstring_chars(env, native_lib_dir, native_lib_dir_chars);
    release_jstring_chars(env, asset_root, asset_root_chars);
    release_jstring_chars(env, app_data_dir, app_data_dir_chars);
}

extern "C" JNIEXPORT void JNICALL
Java_org_termin_android_TerminActivity_nativeShutdown(JNIEnv*, jclass) {
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "nativeShutdown");
    termin_android_shutdown();
}

extern "C" JNIEXPORT void JNICALL
Java_org_termin_android_TerminActivity_nativeSurfaceCreated(
    JNIEnv* env,
    jclass,
    jobject surface
) {
    if (!surface) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "surface is null");
        return;
    }

    __android_log_print(ANDROID_LOG_INFO, kLogTag, "nativeSurfaceCreated");
    ANativeWindow* window = ANativeWindow_fromSurface(env, surface);
    if (!window) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "ANativeWindow_fromSurface failed");
        return;
    }

    termin_android_on_surface_created(window);
    ANativeWindow_release(window);
}

extern "C" JNIEXPORT void JNICALL
Java_org_termin_android_TerminActivity_nativeSurfaceChanged(
    JNIEnv*,
    jclass,
    jint width,
    jint height
) {
    __android_log_print(
        ANDROID_LOG_INFO,
        kLogTag,
        "nativeSurfaceChanged size=%dx%d",
        static_cast<int>(width),
        static_cast<int>(height)
    );
    termin_android_on_surface_changed(static_cast<int32_t>(width), static_cast<int32_t>(height));
}

extern "C" JNIEXPORT void JNICALL
Java_org_termin_android_TerminActivity_nativeSurfaceDestroyed(JNIEnv*, jclass) {
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "nativeSurfaceDestroyed");
    termin_android_on_surface_destroyed();
}

extern "C" JNIEXPORT jboolean JNICALL
Java_org_termin_android_TerminActivity_nativeRenderFrame(JNIEnv*, jclass) {
    int ok = termin_android_render_frame();
    if (!ok) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "nativeRenderFrame failed");
    }
    return ok ? JNI_TRUE : JNI_FALSE;
}

#ifdef TERMIN_QUEST_OPENXR
extern "C" JNIEXPORT jboolean JNICALL
Java_org_termin_android_TerminOpenXRActivity_nativeOpenXRProbe(JNIEnv* env, jclass, jobject activity) {
    JavaVM* vm = nullptr;
    if (env->GetJavaVM(&vm) != JNI_OK || !vm) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "OpenXR probe: failed to get JavaVM");
        return JNI_FALSE;
    }

    termin::openxr::OpenXRAndroidProbeResult result =
        termin::openxr::probe_android_runtime(vm, activity);

    __android_log_print(
        result.system_found ? ANDROID_LOG_INFO : ANDROID_LOG_ERROR,
        kLogTag,
        "OpenXR probe: loader=%d init=%d instance=%d system=%d stage='%s' result=%d detail='%s'",
        result.loader_loaded ? 1 : 0,
        result.loader_initialized ? 1 : 0,
        result.instance_created ? 1 : 0,
        result.system_found ? 1 : 0,
        result.stage ? result.stage : "",
        static_cast<int>(result.last_result),
        result.detail ? result.detail : ""
    );

    return result.system_found ? JNI_TRUE : JNI_FALSE;
}
#endif
