#include "tgfx2/opengl/opengl_render_device.hpp"

#include <cstdint>
#include <utility>

#include <tcbase/tc_log.hpp>

namespace tgfx {

    // --- Push constants ring buffer ---

    void OpenGLRenderDevice::ensure_push_ring() {
        if (push_ring_initialized_)
            return;

        glGetIntegerv(GL_UNIFORM_BUFFER_OFFSET_ALIGNMENT, &push_ring_alignment_);
        if (push_ring_alignment_ <= 0) {
            push_ring_alignment_ = 256;
        }

        glGenBuffers(1, &push_ring_buf_);
        glBindBuffer(GL_UNIFORM_BUFFER, push_ring_buf_);
        // GL_STREAM_DRAW hints "written once, used a few times, re-written".
        // Paired with buffer orphaning (glBufferData NULL on overflow) this
        // avoids GPU stalls on reuse.
        glBufferData(GL_UNIFORM_BUFFER, push_ring_size_, nullptr, GL_STREAM_DRAW);
        glBindBuffer(GL_UNIFORM_BUFFER, 0);

        push_ring_offset_ = 0;
        push_ring_initialized_ = true;
    }

    void OpenGLRenderDevice::push_constants_reset_frame() {
        push_ring_offset_ = 0;
    }

    GLintptr OpenGLRenderDevice::push_constants_write(const void* data, uint32_t size) {
        if (!data || size == 0) {
            return -1;
        }
        if (size > TGFX2_PUSH_CONSTANTS_MAX_BYTES) {
            tc::Log::error(
                "tgfx2: push constants payload %u bytes exceeds max %u", size, TGFX2_PUSH_CONSTANTS_MAX_BYTES);
            return -1;
        }

        ensure_push_ring();

        const GLintptr align = static_cast<GLintptr>(push_ring_alignment_);
        const GLintptr padded = (static_cast<GLintptr>(size) + align - 1) / align * align;

        // Align current offset to the UBO alignment requirement.
        GLintptr offset = (push_ring_offset_ + align - 1) / align * align;

        if (offset + padded > push_ring_size_) {
            // Ring overflow: orphan the buffer storage so the driver gives
            // us a fresh GPU allocation without stalling on old contents,
            // then rewind the write cursor. This is the "invalidate the
            // whole buffer" idiom (equivalent to glInvalidateBufferData on
            // GL 4.3+).
            glBindBuffer(GL_UNIFORM_BUFFER, push_ring_buf_);
            glBufferData(GL_UNIFORM_BUFFER, push_ring_size_, nullptr, GL_STREAM_DRAW);
            glBindBuffer(GL_UNIFORM_BUFFER, 0);
            offset = 0;
        }

        glBindBuffer(GL_UNIFORM_BUFFER, push_ring_buf_);
        glBufferSubData(GL_UNIFORM_BUFFER, offset, static_cast<GLsizeiptr>(size), data);
        glBindBuffer(GL_UNIFORM_BUFFER, 0);

        push_ring_offset_ = offset + padded;
        return offset;
    }

    // --- Transient vertex ring ---
    //
    // Mirrors push_ring_: a persistent VBO the immediate-mode draw paths
    // sub-upload into. No alignment requirement on vertex buffers (unlike
    // UBOs), so the cursor advances by raw size. On overflow the whole
    // storage is orphaned via glBufferData(NULL) and the cursor rewinds —
    // same pattern, same stall avoidance.
    //
    // The HandlePool slot is allocated once; transient_vertex_buffer()
    // returns the same BufferHandle for the process lifetime. Destructor
    // takes care of releasing both the GL id and the slot.

    void OpenGLRenderDevice::ensure_transient_vb() {
        if (transient_vb_initialized_)
            return;

        glGenBuffers(1, &transient_vb_gl_);
        glBindBuffer(GL_ARRAY_BUFFER, transient_vb_gl_);
        glBufferData(GL_ARRAY_BUFFER, transient_vb_size_, nullptr, GL_STREAM_DRAW);
        glBindBuffer(GL_ARRAY_BUFFER, 0);

        GLBuffer b;
        b.gl_id = transient_vb_gl_;
        b.desc.size = static_cast<uint64_t>(transient_vb_size_);
        b.desc.usage = BufferUsage::Vertex;
        b.target = GL_ARRAY_BUFFER;
        b.external = false;
        transient_vb_handle_ = BufferHandle{buffers_.add(std::move(b))};

        transient_vb_offset_ = 0;
        transient_vb_initialized_ = true;
    }

    BufferHandle OpenGLRenderDevice::transient_vertex_buffer() {
        ensure_transient_vb();
        return transient_vb_handle_;
    }

    void OpenGLRenderDevice::transient_vertex_reset_frame() {
        transient_vb_offset_ = 0;
    }

    uint64_t OpenGLRenderDevice::transient_vertex_write(const void* data, uint32_t size) {
        if (!data || size == 0 || size > static_cast<uint32_t>(transient_vb_size_)) {
            return UINT64_MAX;
        }

        ensure_transient_vb();

        GLintptr offset = transient_vb_offset_;
        if (offset + static_cast<GLintptr>(size) > transient_vb_size_) {
            // Orphan + rewind.
            glBindBuffer(GL_ARRAY_BUFFER, transient_vb_gl_);
            glBufferData(GL_ARRAY_BUFFER, transient_vb_size_, nullptr, GL_STREAM_DRAW);
            glBindBuffer(GL_ARRAY_BUFFER, 0);
            offset = 0;
        }

        glBindBuffer(GL_ARRAY_BUFFER, transient_vb_gl_);
        glBufferSubData(GL_ARRAY_BUFFER, offset, static_cast<GLsizeiptr>(size), data);
        glBindBuffer(GL_ARRAY_BUFFER, 0);

        transient_vb_offset_ = offset + static_cast<GLintptr>(size);
        return static_cast<uint64_t>(offset);
    }

    // --- Dynamic UBO ring ---
    //
    // Same ownership pattern as transient_vertex_buffer(): one GL buffer is
    // registered in the BufferHandle pool for command-list binding, while
    // writes sub-upload aligned ranges and rewind/orphan on overflow.

    void OpenGLRenderDevice::ensure_ring_ubo() {
        if (ring_ubo_initialized_)
            return;

        glGetIntegerv(GL_UNIFORM_BUFFER_OFFSET_ALIGNMENT, &ring_ubo_alignment_);
        if (ring_ubo_alignment_ <= 0) {
            ring_ubo_alignment_ = 256;
        }

        glGenBuffers(1, &ring_ubo_gl_);
        glBindBuffer(GL_UNIFORM_BUFFER, ring_ubo_gl_);
        glBufferData(GL_UNIFORM_BUFFER, ring_ubo_size_, nullptr, GL_STREAM_DRAW);
        glBindBuffer(GL_UNIFORM_BUFFER, 0);

        GLBuffer b;
        b.gl_id = ring_ubo_gl_;
        b.desc.size = static_cast<uint64_t>(ring_ubo_size_);
        b.desc.usage = BufferUsage::Uniform;
        b.target = GL_UNIFORM_BUFFER;
        b.external = false;
        ring_ubo_handle_ = BufferHandle{buffers_.add(std::move(b))};

        ring_ubo_offset_ = 0;
        ring_ubo_initialized_ = true;
    }

    void OpenGLRenderDevice::ring_ubo_reset_frame() {
        ring_ubo_offset_ = 0;
    }

    bool OpenGLRenderDevice::ring_ubo_write(const void* data, uint32_t size, uint32_t& out_offset) {
        if (!data || size == 0) {
            return false;
        }

        ensure_ring_ubo();

        if (size > static_cast<uint32_t>(ring_ubo_size_)) {
            tc::Log::error("OpenGLRenderDevice::ring_ubo_write: payload %u exceeds ring capacity %lld",
                           size,
                           static_cast<long long>(ring_ubo_size_));
            return false;
        }

        const GLintptr align = static_cast<GLintptr>(ring_ubo_alignment_);
        const GLintptr padded = (static_cast<GLintptr>(size) + align - 1) / align * align;

        GLintptr offset = (ring_ubo_offset_ + align - 1) / align * align;

        if (offset + padded > ring_ubo_size_) {
            glBindBuffer(GL_UNIFORM_BUFFER, ring_ubo_gl_);
            glBufferData(GL_UNIFORM_BUFFER, ring_ubo_size_, nullptr, GL_STREAM_DRAW);
            glBindBuffer(GL_UNIFORM_BUFFER, 0);
            offset = 0;
        }

        glBindBuffer(GL_UNIFORM_BUFFER, ring_ubo_gl_);
        glBufferSubData(GL_UNIFORM_BUFFER, offset, static_cast<GLsizeiptr>(size), data);
        glBindBuffer(GL_UNIFORM_BUFFER, 0);

        ring_ubo_offset_ = offset + padded;
        out_offset = static_cast<uint32_t>(offset);
        return true;
    }

} // namespace tgfx
