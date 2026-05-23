#include <jni.h>

#include <android/log.h>

#include <termin/openxr/openxr_runtime.hpp>

namespace {

constexpr const char* kLogTag = "TerminOpenXRJNI";
jobject g_activity = nullptr;

} // namespace

extern "C" JNIEXPORT jboolean JNICALL
Java_org_termin_openxr_TerminOpenXRActivity_nativeStart(JNIEnv* env, jclass, jobject activity) {
    if (!activity) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "nativeStart: activity is null");
        return JNI_FALSE;
    }

    JavaVM* vm = nullptr;
    if (env->GetJavaVM(&vm) != JNI_OK || !vm) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "nativeStart: failed to get JavaVM");
        return JNI_FALSE;
    }

    if (g_activity) {
        env->DeleteGlobalRef(g_activity);
    }
    g_activity = env->NewGlobalRef(activity);
    if (!g_activity) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "nativeStart: NewGlobalRef failed");
        return JNI_FALSE;
    }

    termin::openxr::OpenXRAndroidStartResult result =
        termin::openxr::start_android_color_smoke(vm, g_activity);
    __android_log_print(
        result.started ? ANDROID_LOG_INFO : ANDROID_LOG_ERROR,
        kLogTag,
        "start OpenXR smoke: started=%d stage='%s' detail='%s'",
        result.started ? 1 : 0,
        result.stage ? result.stage : "",
        result.detail ? result.detail : ""
    );
    return result.started ? JNI_TRUE : JNI_FALSE;
}

extern "C" JNIEXPORT void JNICALL
Java_org_termin_openxr_TerminOpenXRActivity_nativeStop(JNIEnv* env, jclass) {
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "nativeStop");
    termin::openxr::stop_android_color_smoke();
    if (g_activity) {
        env->DeleteGlobalRef(g_activity);
        g_activity = nullptr;
    }
}
