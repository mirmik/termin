#pragma once

// TcSkeleton - RAII wrapper with handle-based access to tc_skeleton
// Uses tc_skeleton_handle with generation checking for safety

extern "C" {
#include "resources/tc_skeleton.h"
#include "resources/tc_skeleton_registry.h"
}

#include <string>
#include <tcbase/tc_string.h>

namespace termin {

    // TcSkeleton - skeleton data wrapper with registry integration
    // Stores handle (index + generation) instead of raw pointer
    class TcSkeleton {
    private:
        tc_skeleton_handle _handle = tc_skeleton_handle_invalid();

        void retain_or_invalidate() {
            if (!tc_skeleton_handle_is_invalid(_handle) && !tc_skeleton_handle_retain(_handle))
                _handle = tc_skeleton_handle_invalid();
        }

        void release() {
            if (!tc_skeleton_handle_is_invalid(_handle))
                (void)tc_skeleton_handle_release(_handle);
            _handle = tc_skeleton_handle_invalid();
        }

    public:
        TcSkeleton() = default;

        explicit TcSkeleton(tc_skeleton_handle h)
            : _handle(h) {
            retain_or_invalidate();
        }

        TcSkeleton(const TcSkeleton& other)
            : _handle(other._handle) {
            retain_or_invalidate();
        }

        TcSkeleton(TcSkeleton&& other) noexcept
            : _handle(other._handle) {
            other._handle = tc_skeleton_handle_invalid();
        }

        TcSkeleton& operator=(const TcSkeleton& other) {
            if (this == &other ||
                (_handle.index == other._handle.index && _handle.generation == other._handle.generation))
                return *this;
            release();
            _handle = other._handle;
            retain_or_invalidate();
            return *this;
        }

        TcSkeleton& operator=(TcSkeleton&& other) noexcept {
            if (this != &other) {
                release();
                _handle = other._handle;
                other._handle = tc_skeleton_handle_invalid();
            }
            return *this;
        }

        ~TcSkeleton() {
            release();
        }

        // Resolve the current pool location. The returned pointer is borrowed
        // only until the next registry mutation and must never be cached.
        const tc_skeleton* get() const {
            return tc_skeleton_get(_handle);
        }

        tc_skeleton_handle native_handle() const {
            return _handle;
        }

        // Query
        bool has_handle() const {
            return !tc_skeleton_handle_is_invalid(_handle);
        }

        bool is_valid() const {
            return tc_skeleton_is_valid(_handle);
        }

        bool refers_to(const TcSkeleton& other) const {
            return _handle.index == other._handle.index && _handle.generation == other._handle.generation;
        }

        const char* uuid() const {
            const tc_skeleton* s = get();
            return s ? s->header.uuid : "";
        }

        const char* name() const {
            const tc_skeleton* s = get();
            return (s && s->header.name) ? s->header.name : "";
        }

        uint32_t version() const {
            const tc_skeleton* s = get();
            return s ? s->header.version : 0;
        }

        bool is_loaded() const {
            return tc_skeleton_is_loaded(_handle);
        }

        size_t bone_count() const {
            const tc_skeleton* s = get();
            return s ? s->bone_count : 0;
        }

        // Bone access
        const tc_bone* bones() const {
            const tc_skeleton* s = get();
            return s ? s->bones : nullptr;
        }

        const tc_bone* get_bone(size_t index) const {
            const tc_skeleton* s = get();
            return s ? tc_skeleton_get_bone_const(s, index) : nullptr;
        }

        int find_bone(const char* bone_name) const {
            const tc_skeleton* s = get();
            return s ? tc_skeleton_find_bone(s, bone_name) : -1;
        }

        // Root bones
        const int32_t* root_indices() const {
            const tc_skeleton* s = get();
            return s ? s->root_indices : nullptr;
        }

        size_t root_count() const {
            const tc_skeleton* s = get();
            return s ? s->root_count : 0;
        }

        // Trigger lazy load
        bool ensure_loaded() {
            return tc_skeleton_ensure_loaded(_handle);
        }

        bool replace_bones(const tc_skeleton_bone_desc* bones, size_t count) {
            tc_skeleton* s = tc_skeleton_get(_handle);
            return s ? tc_skeleton_replace_bones(s, bones, count) : false;
        }

        // Get by UUID from registry
        static TcSkeleton from_uuid(const std::string& uuid) {
            tc_skeleton_handle h = tc_skeleton_find(uuid.c_str());
            if (tc_skeleton_handle_is_invalid(h)) {
                return TcSkeleton();
            }
            return TcSkeleton(h);
        }

        // Get or create by UUID
        static TcSkeleton get_or_create(const std::string& uuid) {
            tc_skeleton_handle h = tc_skeleton_get_or_create(uuid.c_str());
            if (tc_skeleton_handle_is_invalid(h)) {
                return TcSkeleton();
            }
            return TcSkeleton(h);
        }

        // Create new skeleton
        static TcSkeleton create(const std::string& name = "", const std::string& uuid_hint = "") {
            // Interning may log and invoke a user callback. Do it before
            // acquiring a pointer into the movable skeleton pool.
            const char* interned_name = name.empty() ? nullptr : tc_intern_string(name.c_str());
            const char* uuid = uuid_hint.empty() ? nullptr : uuid_hint.c_str();
            tc_skeleton_handle h = tc_skeleton_create(uuid);
            if (tc_skeleton_handle_is_invalid(h)) {
                return TcSkeleton();
            }

            tc_skeleton* s = tc_skeleton_get(h);
            if (s)
                s->header.name = interned_name;

            return TcSkeleton(h);
        }
    };

} // namespace termin
