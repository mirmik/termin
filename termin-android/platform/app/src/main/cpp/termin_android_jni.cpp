#include <jni.h>

#include <android/native_window_jni.h>
#include <android/log.h>

#include <termin/android/bootstrap.h>

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
    termin_android_on_surface_changed(static_cast<int32_t>(width), static_cast<int32_t>(height));
}

extern "C" JNIEXPORT void JNICALL
Java_org_termin_android_TerminActivity_nativeSurfaceDestroyed(JNIEnv*, jclass) {
    termin_android_on_surface_destroyed();
}

