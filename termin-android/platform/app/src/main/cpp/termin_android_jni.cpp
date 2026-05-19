#include <jni.h>

#include <android/native_window_jni.h>
#include <android/log.h>

#include <termin/android/bootstrap.h>
#include <termin/openxr/openxr_runtime.hpp>

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
    termin::openxr::OpenXRBuildInfo xr_info = termin::openxr::build_info();
    __android_log_print(
        ANDROID_LOG_INFO,
        kLogTag,
        "OpenXR setup: headers=%d api=%u.%u.%u android='%s' vulkan='%s' vulkan2='%s'",
        xr_info.has_openxr_headers ? 1 : 0,
        static_cast<unsigned>(xr_info.api_version_major),
        static_cast<unsigned>(xr_info.api_version_minor),
        static_cast<unsigned>(xr_info.api_version_patch),
        xr_info.android_create_instance_extension,
        xr_info.vulkan_enable_extension,
        xr_info.vulkan_enable2_extension
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
Java_org_termin_android_TerminActivity_nativeSmokeRender(JNIEnv*, jclass) {
    int ok = termin_android_smoke_render();
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "nativeSmokeRender result=%d", ok);
    return ok ? JNI_TRUE : JNI_FALSE;
}
