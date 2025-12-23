#pragma once

#include <vector>
#include <cstdint>
#include <new>
#include "general_transform3.hpp"

namespace termin {


struct TransformHandle {
    uint32_t index = UINT32_MAX;
    uint32_t generation = 0;

    bool is_null() const { return index == UINT32_MAX; }
    explicit operator bool() const { return !is_null(); }

    bool operator==(const TransformHandle& other) const {
        return index == other.index && generation == other.generation;
    }

    bool operator!=(const TransformHandle& other) const {
        return !(*this == other);
    }
};

class GeneralTransform3Pool {
public:
    explicit GeneralTransform3Pool(size_t initial_capacity = 256) {
        _storage.resize(initial_capacity);
        _generations.resize(initial_capacity, 0);
        _alive.resize(initial_capacity, false);
    }

    ~GeneralTransform3Pool() {
        // Destroy all alive objects
        for (size_t i = 0; i < _storage.size(); ++i) {
            if (_alive[i]) {
                get_ptr(i)->~GeneralTransform3();
            }
        }
    }

    // Non-copyable
    GeneralTransform3Pool(const GeneralTransform3Pool&) = delete;
    GeneralTransform3Pool& operator=(const GeneralTransform3Pool&) = delete;

    // Create new transform in pool
    TransformHandle create(const GeneralPose3& local_pose = GeneralPose3::identity(),
                           const std::string& name = "") {
        uint32_t idx;
        if (!_free_list.empty()) {
            idx = _free_list.back();
            _free_list.pop_back();
        } else {
            idx = static_cast<uint32_t>(_next_index);
            if (_next_index >= _storage.size()) {
                // Grow storage - but this invalidates pointers!
                // For now, we don't allow growth after construction
                // User should allocate with sufficient capacity
                return TransformHandle{}; // null handle
            }
            _next_index++;
        }

        // Construct in place
        new (get_ptr(idx)) GeneralTransform3(local_pose, name);
        _alive[idx] = true;
        _count++;

        return TransformHandle{idx, _generations[idx]};
    }

    // Destroy transform by handle
    void destroy(TransformHandle h) {
        if (!is_valid(h)) return;

        GeneralTransform3* ptr = get_ptr(h.index);

        // Unparent and detach children
        ptr->unparent();
        // Children's parent pointers are cleared, but children remain alive
        for (auto* child : ptr->children) {
            child->parent = nullptr;
        }

        // Destroy object
        ptr->~GeneralTransform3();
        _alive[h.index] = false;

        // Increment generation to invalidate old handles
        _generations[h.index]++;

        // Add to free list
        _free_list.push_back(h.index);
        _count--;
    }

    // Destroy transform by pointer (computes index from address)
    void destroy_by_ptr(GeneralTransform3* ptr) {
        if (!ptr) return;

        ptrdiff_t offset = reinterpret_cast<char*>(ptr) - reinterpret_cast<char*>(_storage.data());
        if (offset < 0) return;

        size_t idx = static_cast<size_t>(offset) / sizeof(StorageType);
        if (idx >= _storage.size() || !_alive[idx]) return;

        // Verify it's actually pointing to the start of an object
        if (get_ptr(idx) != ptr) return;

        TransformHandle h{static_cast<uint32_t>(idx), _generations[idx]};
        destroy(h);
    }

    // Get transform by handle
    GeneralTransform3* get(TransformHandle h) {
        if (!is_valid(h)) return nullptr;
        return get_ptr(h.index);
    }

    const GeneralTransform3* get(TransformHandle h) const {
        if (!is_valid(h)) return nullptr;
        return get_ptr(h.index);
    }

    // Check if handle is valid
    bool is_valid(TransformHandle h) const {
        return h.index < _storage.size() &&
               _alive[h.index] &&
               _generations[h.index] == h.generation;
    }

    // Check if pointer is valid (belongs to this pool and is alive)
    bool is_valid_ptr(const GeneralTransform3* ptr) const {
        if (!ptr) return false;

        ptrdiff_t offset = reinterpret_cast<const char*>(ptr) - reinterpret_cast<const char*>(_storage.data());
        if (offset < 0) return false;

        size_t idx = static_cast<size_t>(offset) / sizeof(StorageType);
        if (idx >= _storage.size()) return false;

        // Verify it's actually pointing to the start of an object
        if (get_ptr(idx) != ptr) return false;

        return _alive[idx];
    }

    // Get handle from pointer
    TransformHandle handle_from_ptr(const GeneralTransform3* ptr) const {
        if (!ptr) return TransformHandle{};

        ptrdiff_t offset = reinterpret_cast<const char*>(ptr) - reinterpret_cast<const char*>(_storage.data());
        if (offset < 0) return TransformHandle{};

        size_t idx = static_cast<size_t>(offset) / sizeof(StorageType);
        if (idx >= _storage.size() || !_alive[idx]) return TransformHandle{};

        if (get_ptr(idx) != ptr) return TransformHandle{};

        return TransformHandle{static_cast<uint32_t>(idx), _generations[idx]};
    }

    // Statistics
    size_t size() const { return _count; }
    size_t capacity() const { return _storage.size(); }

private:
    // Storage type with proper alignment
    using StorageType = std::aligned_storage_t<sizeof(GeneralTransform3), alignof(GeneralTransform3)>;

    std::vector<StorageType> _storage;
    std::vector<uint32_t> _generations;
    std::vector<bool> _alive;
    std::vector<uint32_t> _free_list;
    size_t _next_index = 0;
    size_t _count = 0;

    GeneralTransform3* get_ptr(size_t idx) {
        return reinterpret_cast<GeneralTransform3*>(&_storage[idx]);
    }

    const GeneralTransform3* get_ptr(size_t idx) const {
        return reinterpret_cast<const GeneralTransform3*>(&_storage[idx]);
    }
};


} // namespace termin
