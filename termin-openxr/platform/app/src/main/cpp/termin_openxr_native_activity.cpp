#include <android/input.h>
#include <android/looper.h>
#include <android/log.h>
#include <android/asset_manager.h>
#include <android/native_activity.h>
#include <jni.h>

#include <atomic>
#include <chrono>
#include <cerrno>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>
#include <vector>
#include <sys/stat.h>

#include <termin/openxr/openxr_runtime.hpp>

namespace {

constexpr const char* kLogTag = "TerminOpenXRActivity";

struct NativeActivityState {
    ANativeActivity* activity = nullptr;
    jobject activity_ref = nullptr;
    std::string asset_root;
    std::atomic<bool> resumed{false};
    std::atomic<bool> focused{false};
    std::atomic<bool> native_running{false};
    std::atomic<uint32_t> start_generation{0};
    std::atomic<bool> input_running{false};
    std::atomic<ALooper*> input_looper{nullptr};
    std::thread input_thread;
    std::mutex input_mutex;
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

bool ensure_directory(const std::string& path) {
    if (path.empty()) {
        return false;
    }
    std::string current;
    size_t index = 0;
    if (path[0] == '/') {
        current = "/";
        index = 1;
    }
    while (index <= path.size()) {
        size_t next = path.find('/', index);
        std::string part = path.substr(index, next == std::string::npos ? std::string::npos : next - index);
        if (!part.empty()) {
            if (current.size() > 1) {
                current += "/";
            }
            current += part;
            if (mkdir(current.c_str(), 0700) != 0 && errno != EEXIST) {
                __android_log_print(
                    ANDROID_LOG_ERROR,
                    kLogTag,
                    "mkdir failed '%s': %s",
                    current.c_str(),
                    std::strerror(errno)
                );
                return false;
            }
        }
        if (next == std::string::npos) {
            break;
        }
        index = next + 1;
    }
    return true;
}

bool copy_asset_file(AAssetManager* assets, const std::string& asset_path, const std::string& target_path) {
    AAsset* asset = AAssetManager_open(assets, asset_path.c_str(), AASSET_MODE_STREAMING);
    if (!asset) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "open asset failed '%s'", asset_path.c_str());
        return false;
    }

    const size_t slash = target_path.find_last_of('/');
    if (slash != std::string::npos && !ensure_directory(target_path.substr(0, slash))) {
        AAsset_close(asset);
        return false;
    }

    FILE* out = std::fopen(target_path.c_str(), "wb");
    if (!out) {
        __android_log_print(
            ANDROID_LOG_ERROR,
            kLogTag,
            "open target failed '%s': %s",
            target_path.c_str(),
            std::strerror(errno)
        );
        AAsset_close(asset);
        return false;
    }

    std::vector<char> buffer(8192);
    int read = 0;
    bool ok = true;
    while ((read = AAsset_read(asset, buffer.data(), buffer.size())) > 0) {
        if (std::fwrite(buffer.data(), 1, static_cast<size_t>(read), out) != static_cast<size_t>(read)) {
            __android_log_print(
                ANDROID_LOG_ERROR,
                kLogTag,
                "write target failed '%s': %s",
                target_path.c_str(),
                std::strerror(errno)
            );
            ok = false;
            break;
        }
    }
    if (read < 0) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "read asset failed '%s'", asset_path.c_str());
        ok = false;
    }

    std::fclose(out);
    AAsset_close(asset);
    return ok;
}

bool copy_asset_tree(AAssetManager* assets, const std::string& asset_path, const std::string& target_path) {
    AAssetDir* dir = AAssetManager_openDir(assets, asset_path.c_str());
    if (!dir) {
        return copy_asset_file(assets, asset_path, target_path);
    }

    std::vector<std::string> children;
    const char* child = nullptr;
    while ((child = AAssetDir_getNextFileName(dir)) != nullptr) {
        children.emplace_back(child);
    }
    AAssetDir_close(dir);

    if (children.empty()) {
        if (asset_path.empty()) {
            return ensure_directory(target_path);
        }
        return copy_asset_file(assets, asset_path, target_path);
    }

    bool has_children = false;
    bool ok = ensure_directory(target_path);
    for (const std::string& child_name : children) {
        has_children = true;
        std::string child_asset = asset_path.empty() ? child_name : asset_path + "/" + child_name;
        std::string child_target = target_path + "/" + child_name;
        if (!copy_asset_tree(assets, child_asset, child_target)) {
            ok = false;
        }
    }

    if (!has_children && !asset_path.empty()) {
        return copy_asset_file(assets, asset_path, target_path);
    }
    return ok;
}

bool read_asset_text(AAssetManager* assets, const std::string& asset_path, std::string& out) {
    AAsset* asset = AAssetManager_open(assets, asset_path.c_str(), AASSET_MODE_BUFFER);
    if (!asset) {
        return false;
    }
    const off_t length = AAsset_getLength(asset);
    out.resize(static_cast<size_t>(length));
    const int read = AAsset_read(asset, out.data(), out.size());
    AAsset_close(asset);
    return read == length;
}

bool copy_asset_index(AAssetManager* assets, const std::string& target_root) {
    std::string index;
    if (!read_asset_text(assets, "termin_asset_index.txt", index)) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "termin_asset_index.txt not found");
        return false;
    }
    if (!ensure_directory(target_root)) {
        return false;
    }

    bool ok = true;
    size_t pos = 0;
    while (pos < index.size()) {
        size_t end = index.find('\n', pos);
        if (end == std::string::npos) {
            end = index.size();
        }
        std::string path = index.substr(pos, end - pos);
        if (!path.empty() && path != "termin_asset_index.txt") {
            if (!copy_asset_file(assets, path, target_root + "/" + path)) {
                ok = false;
            }
        }
        pos = end + 1;
    }
    return ok;
}

int consume_input_events(int, int, void* data) {
    auto* queue = static_cast<AInputQueue*>(data);
    AInputEvent* event = nullptr;
    while (AInputQueue_getEvent(queue, &event) >= 0) {
        if (AInputQueue_preDispatchEvent(queue, event)) {
            continue;
        }
        AInputQueue_finishEvent(queue, event, 0);
    }
    return 1;
}

void stop_input() {
    std::lock_guard<std::mutex> lock(g_state.input_mutex);
    if (!g_state.input_running.exchange(false)) {
        return;
    }

    ALooper* looper = g_state.input_looper.load();
    if (looper) {
        ALooper_wake(looper);
    }
    if (g_state.input_thread.joinable()) {
        g_state.input_thread.join();
    }
    g_state.input_looper.store(nullptr);
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
            termin::openxr::start_android_scene_smoke(
                g_state.activity->vm,
                g_state.activity_ref,
                g_state.asset_root.c_str()
            );
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
    stop_input();

    if (g_state.activity_ref) {
        JNIEnv* env = attach_env(activity->vm);
        if (env) {
            env->DeleteGlobalRef(g_state.activity_ref);
        }
    }
    g_state.activity = nullptr;
    g_state.activity_ref = nullptr;
    g_state.asset_root.clear();
    g_state.resumed.store(false);
    g_state.focused.store(false);
    g_state.native_running.store(false);
    g_state.input_running.store(false);
    g_state.input_looper.store(nullptr);
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

void on_input_queue_created(ANativeActivity*, AInputQueue* queue) {
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "onInputQueueCreated");
    stop_input();

    std::lock_guard<std::mutex> lock(g_state.input_mutex);
    g_state.input_running.store(true);
    g_state.input_thread = std::thread([queue]() {
        ALooper* looper = ALooper_prepare(ALOOPER_PREPARE_ALLOW_NON_CALLBACKS);
        g_state.input_looper.store(looper);
        AInputQueue_attachLooper(queue, looper, 1, consume_input_events, queue);

        while (g_state.input_running.load()) {
            ALooper_pollOnce(-1, nullptr, nullptr, nullptr);
        }

        AInputQueue_detachLooper(queue);
        g_state.input_looper.store(nullptr);
        __android_log_print(ANDROID_LOG_INFO, kLogTag, "input pump stopped");
    });
}

void on_input_queue_destroyed(ANativeActivity*, AInputQueue*) {
    __android_log_print(ANDROID_LOG_INFO, kLogTag, "onInputQueueDestroyed");
    stop_input();
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
    g_state.asset_root = activity->internalDataPath
        ? std::string(activity->internalDataPath) + "/assets"
        : "";
    if (g_state.asset_root.empty()) {
        __android_log_print(ANDROID_LOG_ERROR, kLogTag, "internalDataPath is empty");
    } else if (!copy_asset_index(activity->assetManager, g_state.asset_root) &&
               !copy_asset_tree(activity->assetManager, "", g_state.asset_root)) {
        __android_log_print(
            ANDROID_LOG_ERROR,
            kLogTag,
            "asset copy failed into '%s'",
            g_state.asset_root.c_str()
        );
    } else {
        __android_log_print(
            ANDROID_LOG_INFO,
            kLogTag,
            "assets copied into '%s'",
            g_state.asset_root.c_str()
        );
    }

    activity->callbacks->onStart = on_start;
    activity->callbacks->onResume = on_resume;
    activity->callbacks->onPause = on_pause;
    activity->callbacks->onStop = on_stop;
    activity->callbacks->onDestroy = on_destroy;
    activity->callbacks->onWindowFocusChanged = on_window_focus_changed;
    activity->callbacks->onInputQueueCreated = on_input_queue_created;
    activity->callbacks->onInputQueueDestroyed = on_input_queue_destroyed;
}
