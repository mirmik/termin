#pragma once

#include <vector>
#include <string>
#include <cstring>

extern "C" {
#include "termin_core.h"
}

namespace termin {

// View into interleaved vertex attribute data (no copying)
struct AttributeView {
    const uint8_t* base = nullptr;  // pointer to first element of attribute
    size_t stride = 0;              // bytes between vertices
    size_t count = 0;               // number of vertices
    size_t components = 0;          // floats per vertex (2, 3, or 4)

    bool valid() const { return base != nullptr && count > 0; }

    const float* at(size_t i) const {
        return reinterpret_cast<const float*>(base + i * stride);
    }

    // Copy to flat vector
    std::vector<float> to_vector() const {
        std::vector<float> result;
        if (!valid()) return result;
        result.resize(count * components);
        for (size_t i = 0; i < count; i++) {
            const float* src = at(i);
            for (size_t c = 0; c < components; c++) {
                result[i * components + c] = src[c];
            }
        }
        return result;
    }
};

// Mutable view for writing attribute data
struct MutableAttributeView {
    uint8_t* base = nullptr;
    size_t stride = 0;
    size_t count = 0;
    size_t components = 0;

    bool valid() const { return base != nullptr && count > 0; }

    float* at(size_t i) const {
        return reinterpret_cast<float*>(base + i * stride);
    }

    void set(size_t i, const float* data) const {
        float* dst = at(i);
        for (size_t c = 0; c < components; c++) {
            dst[c] = data[c];
        }
    }
};

// Base class for meshes with any vertex layout.
// Handles tc_mesh registry, reference counting, and attribute access.
class CustomMesh {
protected:
    tc_mesh* _mesh = nullptr;

public:
    // ========== Constructors / Destructor ==========

    CustomMesh() = default;

    ~CustomMesh() {
        if (_mesh) {
            tc_mesh_release(_mesh);
            _mesh = nullptr;
        }
    }

    // Copy - increment ref
    CustomMesh(const CustomMesh& other) : _mesh(other._mesh) {
        if (_mesh) tc_mesh_add_ref(_mesh);
    }

    // Move - transfer ownership
    CustomMesh(CustomMesh&& other) noexcept : _mesh(other._mesh) {
        other._mesh = nullptr;
    }

    // Copy assignment
    CustomMesh& operator=(const CustomMesh& other) {
        if (this != &other) {
            if (_mesh) tc_mesh_release(_mesh);
            _mesh = other._mesh;
            if (_mesh) tc_mesh_add_ref(_mesh);
        }
        return *this;
    }

    // Move assignment
    CustomMesh& operator=(CustomMesh&& other) noexcept {
        if (this != &other) {
            if (_mesh) tc_mesh_release(_mesh);
            _mesh = other._mesh;
            other._mesh = nullptr;
        }
        return *this;
    }

    // ========== Factory Methods ==========

    // Get existing mesh by UUID (increments ref)
    static CustomMesh from_uuid(const char* uuid) {
        CustomMesh m;
        m._mesh = tc_mesh_get(uuid);
        if (m._mesh) tc_mesh_add_ref(m._mesh);
        return m;
    }

    // ========== Initialization ==========

    // Initialize with precomputed interleaved data and auto-generated UUID
    void init_from_data(
        const void* interleaved_data,
        size_t vertex_count,
        const tc_vertex_layout* layout,
        const uint32_t* indices,
        size_t index_count,
        const char* name = nullptr
    ) {
        if (vertex_count == 0 || !layout) return;

        // Release old mesh if any
        if (_mesh) {
            tc_mesh_release(_mesh);
            _mesh = nullptr;
        }

        size_t data_size = vertex_count * layout->stride;

        // Compute UUID from data
        char uuid[40];
        tc_mesh_compute_uuid(interleaved_data, data_size, indices, index_count, uuid);

        // Get or create mesh and take ownership
        _mesh = tc_mesh_get_or_create(uuid);
        if (!_mesh) return;
        tc_mesh_add_ref(_mesh);

        // Set data if newly created
        if (_mesh->version == 1 && _mesh->vertices == nullptr) {
            tc_mesh_set_data(_mesh, interleaved_data, vertex_count, layout, indices, index_count, name);
        }
    }

    // Initialize with explicit UUID (for cached primitives)
    void init_with_uuid(
        const char* uuid,
        const void* interleaved_data,
        size_t vertex_count,
        const tc_vertex_layout* layout,
        const uint32_t* indices,
        size_t index_count,
        const char* name = nullptr
    ) {
        if (!uuid || uuid[0] == '\0') return;

        // Release old mesh if any
        if (_mesh) {
            tc_mesh_release(_mesh);
            _mesh = nullptr;
        }

        // Get or create mesh and take ownership
        _mesh = tc_mesh_get_or_create(uuid);
        if (!_mesh) return;
        tc_mesh_add_ref(_mesh);

        // Set data if newly created
        if (_mesh->vertices == nullptr && interleaved_data && layout) {
            tc_mesh_set_data(_mesh, interleaved_data, vertex_count, layout, indices, index_count, name);
        }
    }

    // ========== Accessors ==========

    bool is_valid() const { return _mesh != nullptr; }
    explicit operator bool() const { return is_valid(); }

    tc_mesh* raw() const { return _mesh; }

    const char* uuid() const {
        return _mesh ? _mesh->uuid : "";
    }

    const char* name() const {
        return _mesh && _mesh->name ? _mesh->name : "";
    }

    void set_name(const char* new_name) {
        if (!_mesh) return;
        if (_mesh->name) {
            free(const_cast<char*>(_mesh->name));
            _mesh->name = nullptr;
        }
        if (new_name && new_name[0] != '\0') {
            _mesh->name = strdup(new_name);
        }
    }

    size_t vertex_count() const {
        return _mesh ? _mesh->vertex_count : 0;
    }

    size_t index_count() const {
        return _mesh ? _mesh->index_count : 0;
    }

    size_t triangle_count() const {
        return index_count() / 3;
    }

    uint32_t version() const {
        return _mesh ? _mesh->version : 0;
    }

    const tc_vertex_layout& layout() const {
        static tc_vertex_layout empty = {};
        return _mesh ? _mesh->layout : empty;
    }

    // ========== Attribute Access ==========

    bool has_attribute(const char* name) const {
        if (!_mesh) return false;
        return tc_vertex_layout_find(&_mesh->layout, name) != nullptr;
    }

    AttributeView get_attribute(const char* attr_name) const {
        AttributeView view;
        if (!_mesh || !_mesh->vertices) return view;

        const tc_vertex_attrib* attr = tc_vertex_layout_find(&_mesh->layout, attr_name);
        if (!attr) return view;

        view.base = static_cast<const uint8_t*>(_mesh->vertices) + attr->offset;
        view.stride = _mesh->layout.stride;
        view.count = _mesh->vertex_count;
        view.components = attr->size;
        return view;
    }

    MutableAttributeView get_mutable_attribute(const char* attr_name) {
        MutableAttributeView view;
        if (!_mesh || !_mesh->vertices) return view;

        const tc_vertex_attrib* attr = tc_vertex_layout_find(&_mesh->layout, attr_name);
        if (!attr) return view;

        view.base = static_cast<uint8_t*>(_mesh->vertices) + attr->offset;
        view.stride = _mesh->layout.stride;
        view.count = _mesh->vertex_count;
        view.components = attr->size;
        return view;
    }

    // ========== Index Access ==========

    const uint32_t* indices_data() const {
        return _mesh ? _mesh->indices : nullptr;
    }

    std::vector<uint32_t> get_indices() const {
        std::vector<uint32_t> result;
        if (!_mesh || !_mesh->indices) return result;
        result.assign(_mesh->indices, _mesh->indices + _mesh->index_count);
        return result;
    }

    // ========== Raw Buffer Access ==========

    const void* vertices_data() const {
        return _mesh ? _mesh->vertices : nullptr;
    }

    size_t vertices_size_bytes() const {
        return _mesh ? _mesh->vertex_count * _mesh->layout.stride : 0;
    }

    // ========== Version Bump ==========

    void bump_version() {
        if (_mesh) _mesh->version++;
    }
};

} // namespace termin
