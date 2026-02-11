// tc_gpu.c - GPU operations implementation
#include "tc_gpu.h"
#include "tc_log.h"
#include "resources/tc_material.h"
#include "resources/tc_shader_registry.h"
#include "resources/tc_texture_registry.h"
#include <string.h>
#include <stdlib.h>

// Global GPU ops pointer (set by rendering backend)
static const tc_gpu_ops* g_gpu_ops = NULL;

// Separate shader preprocess callback (set from Python after fallback loader is ready)
static tc_shader_preprocess_fn g_shader_preprocess = NULL;

// ============================================================================
// GPU ops registration
// ============================================================================

void tc_gpu_set_ops(const tc_gpu_ops* ops) {
    g_gpu_ops = ops;
}

const tc_gpu_ops* tc_gpu_get_ops(void) {
    return g_gpu_ops;
}

void tc_gpu_set_shader_preprocess(tc_shader_preprocess_fn fn) {
    g_shader_preprocess = fn;
}

bool tc_gpu_available(void) {
    return g_gpu_ops != NULL;
}

// ============================================================================
// Texture GPU operations
// ============================================================================

bool tc_texture_needs_upload(const tc_texture* tex) {
    if (!tex) return false;
    tc_gpu_context* ctx = tc_gpu_get_context();
    if (!ctx) {
        return tex->gpu_id == 0 || tex->gpu_version != (int32_t)tex->header.version;
    }
    tc_gpu_slot* slot = tc_gpu_context_texture_slot(ctx, tex->header.pool_index);
    if (!slot) return true;
    return slot->gl_id == 0 || slot->version != (int32_t)tex->header.version;
}

bool tc_texture_upload_gpu(tc_texture* tex) {
    if (!tex || !tex->data) {
        return false;
    }

    if (!g_gpu_ops) {
        tc_log(TC_LOG_ERROR, "tc_texture_upload_gpu: GPU ops not set");
        return false;
    }

    tc_gpu_context* ctx = tc_gpu_get_context();
    if (!ctx) {
        tc_log(TC_LOG_ERROR, "tc_texture_upload_gpu: no GPUContext set");
        return false;
    }

    tc_gpu_slot* slot = tc_gpu_context_texture_slot(ctx, tex->header.pool_index);
    if (!slot) {
        tc_log(TC_LOG_ERROR, "tc_texture_upload_gpu: failed to get context slot");
        return false;
    }

    // Already up to date?
    if (slot->gl_id != 0 && slot->version == (int32_t)tex->header.version) {
        tex->gpu_id = slot->gl_id;
        tex->gpu_version = slot->version;
        return true;
    }

    // Delete old GPU texture if exists
    if (slot->gl_id != 0 && g_gpu_ops->texture_delete) {
        g_gpu_ops->texture_delete(slot->gl_id);
    }

    uint32_t gpu_id = 0;

    // Check if this is a depth texture
    if (tex->format == TC_TEXTURE_DEPTH24) {
        if (!g_gpu_ops->depth_texture_upload) {
            tc_log(TC_LOG_ERROR, "tc_texture_upload_gpu: depth_texture_upload not set");
            return false;
        }
        gpu_id = g_gpu_ops->depth_texture_upload(
            (const float*)tex->data,
            (int)tex->width,
            (int)tex->height,
            tex->compare_mode != 0
        );
    } else {
        if (!g_gpu_ops->texture_upload) {
            tc_log(TC_LOG_ERROR, "tc_texture_upload_gpu: texture_upload not set");
            return false;
        }
        gpu_id = g_gpu_ops->texture_upload(
            (const uint8_t*)tex->data,
            (int)tex->width,
            (int)tex->height,
            (int)tex->channels,
            tex->mipmap != 0,
            tex->clamp != 0
        );
    }

    if (gpu_id == 0) {
        tc_log(TC_LOG_ERROR, "tc_texture_upload_gpu: upload failed for '%s'",
               tex->header.name ? tex->header.name : tex->header.uuid);
        return false;
    }

    // Store in context slot
    slot->gl_id = gpu_id;
    slot->version = (int32_t)tex->header.version;

    // Write-through cache
    tex->gpu_id = gpu_id;
    tex->gpu_version = (int32_t)tex->header.version;
    return true;
}

bool tc_texture_bind_gpu(tc_texture* tex, int unit) {
    if (!tex) {
        return false;
    }

    if (!g_gpu_ops) {
        tc_log(TC_LOG_ERROR, "tc_texture_bind_gpu: GPU ops not set");
        return false;
    }

    // Upload if needed
    if (tc_texture_needs_upload(tex)) {
        if (!tc_texture_upload_gpu(tex)) {
            return false;
        }
    }

    // Bind using appropriate function for texture type
    if (tex->format == TC_TEXTURE_DEPTH24) {
        if (!g_gpu_ops->depth_texture_bind) {
            tc_log(TC_LOG_ERROR, "tc_texture_bind_gpu: depth_texture_bind not set");
            return false;
        }
        g_gpu_ops->depth_texture_bind(tex->gpu_id, unit);
    } else {
        if (!g_gpu_ops->texture_bind) {
            tc_log(TC_LOG_ERROR, "tc_texture_bind_gpu: texture_bind not set");
            return false;
        }
        g_gpu_ops->texture_bind(tex->gpu_id, unit);
    }
    return true;
}

void tc_texture_delete_gpu(tc_texture* tex) {
    if (!tex) return;

    tc_gpu_context* ctx = tc_gpu_get_context();
    if (!ctx) {
        // No context — just clear cache. GPU resources will be cleaned up
        // when the owning GPUContext is freed.
        tex->gpu_id = 0;
        tex->gpu_version = -1;
        return;
    }

    tc_gpu_slot* slot = tc_gpu_context_texture_slot(ctx, tex->header.pool_index);
    if (slot) {
        if (slot->gl_id != 0 && g_gpu_ops && g_gpu_ops->texture_delete) {
            g_gpu_ops->texture_delete(slot->gl_id);
        }
        slot->gl_id = 0;
        slot->version = -1;
    }

    tex->gpu_id = 0;
    tex->gpu_version = -1;
}

// ============================================================================
// Shader GPU operations
// ============================================================================

uint32_t tc_shader_compile_gpu(tc_shader* shader) {
    if (!shader) {
        tc_log(TC_LOG_ERROR, "tc_shader_compile_gpu: shader is NULL");
        return 0;
    }

    if (!g_gpu_ops || !g_gpu_ops->shader_compile) {
        tc_log(TC_LOG_ERROR, "tc_shader_compile_gpu: GPU ops not set");
        return 0;
    }

    tc_gpu_context* ctx = tc_gpu_get_context();
    if (!ctx) {
        tc_log(TC_LOG_ERROR, "tc_shader_compile_gpu: no GPUContext set");
        return 0;
    }

    tc_gpu_slot* slot = tc_gpu_context_shader_slot(ctx, shader->pool_index);
    if (!slot) {
        tc_log(TC_LOG_ERROR, "tc_shader_compile_gpu: failed to get context slot");
        return 0;
    }

    // Already compiled and up to date?
    if (slot->gl_id != 0 && slot->version == (int32_t)shader->version) {
        shader->gpu_program = slot->gl_id;
        shader->gpu_version = slot->version;
        return slot->gl_id;
    }

    // Check if sources are available
    if (!shader->vertex_source || !shader->fragment_source) {
        tc_log(TC_LOG_ERROR, "tc_shader_compile_gpu: missing sources for '%s' (vertex=%p, fragment=%p)",
               shader->name ? shader->name : shader->uuid,
               (void*)shader->vertex_source, (void*)shader->fragment_source);
        return 0;
    }

    // Delete old program if exists
    if (slot->gl_id != 0 && g_gpu_ops->shader_delete) {
        g_gpu_ops->shader_delete(slot->gl_id);
    }

    // Preprocess sources if preprocessor is available
    const char* vertex_src = shader->vertex_source;
    const char* fragment_src = shader->fragment_source;
    const char* geometry_src = shader->geometry_source;

    char* preprocessed_vertex = NULL;
    char* preprocessed_fragment = NULL;
    char* preprocessed_geometry = NULL;

    const char* shader_name = shader->name ? shader->name : shader->uuid;

    if (g_shader_preprocess) {
        if (vertex_src && strstr(vertex_src, "#include")) {
            preprocessed_vertex = g_shader_preprocess(vertex_src, shader_name);
            if (preprocessed_vertex) {
                vertex_src = preprocessed_vertex;
            }
        }
        if (fragment_src && strstr(fragment_src, "#include")) {
            preprocessed_fragment = g_shader_preprocess(fragment_src, shader_name);
            if (preprocessed_fragment) {
                fragment_src = preprocessed_fragment;
            }
        }
        if (geometry_src && strstr(geometry_src, "#include")) {
            preprocessed_geometry = g_shader_preprocess(geometry_src, shader_name);
            if (preprocessed_geometry) {
                geometry_src = preprocessed_geometry;
            }
        }
    }

    // Compile new program
    uint32_t program = g_gpu_ops->shader_compile(
        vertex_src,
        fragment_src,
        geometry_src
    );

    // Free preprocessed sources
    free(preprocessed_vertex);
    free(preprocessed_fragment);
    free(preprocessed_geometry);

    if (program == 0) {
        tc_log(TC_LOG_ERROR, "tc_shader_compile_gpu: compile failed for '%s'",
               shader_name);
        return 0;
    }

    // Store in context slot
    slot->gl_id = program;
    slot->version = (int32_t)shader->version;

    // Write-through cache
    shader->gpu_program = program;
    shader->gpu_version = (int32_t)shader->version;
    return program;
}

void tc_shader_use_gpu(tc_shader* shader) {
    if (!shader) {
        return;
    }

    tc_gpu_context* ctx = tc_gpu_get_context();
    if (!ctx) {
        return;
    }

    tc_gpu_slot* slot = tc_gpu_context_shader_slot(ctx, shader->pool_index);
    uint32_t program = slot ? slot->gl_id : 0;

    if (program == 0 || (slot && slot->version != (int32_t)shader->version)) {
        program = tc_shader_compile_gpu(shader);
        if (program == 0) {
            return;
        }
    }

    if (g_gpu_ops && g_gpu_ops->shader_use) {
        g_gpu_ops->shader_use(program);
    }
}

void tc_shader_delete_gpu(tc_shader* shader) {
    if (!shader) return;

    tc_gpu_context* ctx = tc_gpu_get_context();
    if (!ctx) {
        // No context — just clear cache.
        shader->gpu_program = 0;
        shader->gpu_version = -1;
        return;
    }

    tc_gpu_slot* slot = tc_gpu_context_shader_slot(ctx, shader->pool_index);
    if (slot) {
        if (slot->gl_id != 0 && g_gpu_ops && g_gpu_ops->shader_delete) {
            g_gpu_ops->shader_delete(slot->gl_id);
        }
        slot->gl_id = 0;
        slot->version = -1;
    }

    shader->gpu_program = 0;
    shader->gpu_version = -1;
}

// ============================================================================
// Mesh GPU operations
// ============================================================================

uint32_t tc_mesh_upload_gpu(tc_mesh* mesh) {
    if (!mesh || !mesh->vertices) {
        return 0;
    }

    if (!g_gpu_ops || !g_gpu_ops->mesh_upload) {
        tc_log(TC_LOG_ERROR, "tc_mesh_upload_gpu: GPU ops not set");
        return 0;
    }

    tc_gpu_context* ctx = tc_gpu_get_context();
    if (!ctx) {
        tc_log(TC_LOG_ERROR, "tc_mesh_upload_gpu: no GPUContext set");
        return 0;
    }

    tc_gpu_share_group* group = ctx->share_group;
    tc_gpu_mesh_data_slot* shared = tc_gpu_share_group_mesh_data_slot(group, mesh->header.pool_index);
    tc_gpu_vao_slot* vao_slot = tc_gpu_context_vao_slot(ctx, mesh->header.pool_index);
    if (!shared || !vao_slot) {
        tc_log(TC_LOG_ERROR, "tc_mesh_upload_gpu: failed to get slots");
        return 0;
    }

    bool data_current = (shared->vbo != 0 &&
                         shared->version == (int32_t)mesh->header.version);

    if (data_current) {
        // VBO/EBO data is up to date. Check if VAO exists and is not stale.
        if (vao_slot->vao != 0 &&
            vao_slot->bound_vbo == shared->vbo &&
            vao_slot->bound_ebo == shared->ebo) {
            mesh->gpu_vao = vao_slot->vao;
            return vao_slot->vao;
        }

        // VAO missing or stale — (re)create from shared VBO/EBO
        if (vao_slot->vao != 0 && g_gpu_ops->mesh_delete) {
            g_gpu_ops->mesh_delete(vao_slot->vao);
        }

        // Write-through needed for mesh_create_vao which reads mesh->gpu_vbo/ebo
        mesh->gpu_vbo = shared->vbo;
        mesh->gpu_ebo = shared->ebo;

        uint32_t vao = 0;
        if (g_gpu_ops->mesh_create_vao) {
            vao = g_gpu_ops->mesh_create_vao(mesh);
        }
        if (vao == 0) {
            tc_log(TC_LOG_ERROR, "tc_mesh_upload_gpu: mesh_create_vao failed for '%s'",
                   mesh->header.name ? mesh->header.name : mesh->header.uuid);
            return 0;
        }

        vao_slot->vao = vao;
        vao_slot->bound_vbo = shared->vbo;
        vao_slot->bound_ebo = shared->ebo;
        mesh->gpu_vao = vao;
        return vao;
    }

    // VBO/EBO data needs upload (first time or version changed).
    // Delete existing per-context VAO
    if (vao_slot->vao != 0 && g_gpu_ops->mesh_delete) {
        g_gpu_ops->mesh_delete(vao_slot->vao);
        vao_slot->vao = 0;
        vao_slot->bound_vbo = 0;
        vao_slot->bound_ebo = 0;
    }
    // Delete old shared VBO/EBO
    if (shared->vbo != 0 && g_gpu_ops->buffer_delete) {
        g_gpu_ops->buffer_delete(shared->vbo);
    }
    if (shared->ebo != 0 && g_gpu_ops->buffer_delete) {
        g_gpu_ops->buffer_delete(shared->ebo);
    }
    shared->vbo = 0;
    shared->ebo = 0;

    mesh->gpu_vao = 0;
    mesh->gpu_vbo = 0;
    mesh->gpu_ebo = 0;

    // Full upload: creates VBO + EBO + VAO
    uint32_t vao = g_gpu_ops->mesh_upload(mesh);
    if (vao == 0) {
        tc_log(TC_LOG_ERROR, "tc_mesh_upload_gpu: upload failed for '%s'",
               mesh->header.name ? mesh->header.name : mesh->header.uuid);
        return 0;
    }

    // Store shared data (mesh_upload writes gpu_vbo/gpu_ebo to mesh)
    shared->vbo = mesh->gpu_vbo;
    shared->ebo = mesh->gpu_ebo;
    shared->version = (int32_t)mesh->header.version;

    // Store per-context VAO
    vao_slot->vao = vao;
    vao_slot->bound_vbo = mesh->gpu_vbo;
    vao_slot->bound_ebo = mesh->gpu_ebo;

    mesh->gpu_vao = vao;
    mesh->gpu_version = (int32_t)mesh->header.version;
    return vao;
}

void tc_mesh_draw_gpu(tc_mesh* mesh) {
    if (!mesh) {
        return;
    }

    tc_gpu_context* ctx = tc_gpu_get_context();
    if (!ctx) {
        return;
    }

    tc_gpu_share_group* group = ctx->share_group;
    tc_gpu_mesh_data_slot* shared = tc_gpu_share_group_mesh_data_slot(group, mesh->header.pool_index);
    tc_gpu_vao_slot* vao_slot = tc_gpu_context_vao_slot(ctx, mesh->header.pool_index);
    if (!shared || !vao_slot) {
        return;
    }

    // Check if VBO/EBO data is current
    bool data_stale = (shared->vbo == 0 ||
                       shared->version != (int32_t)mesh->header.version);

    if (data_stale || vao_slot->vao == 0 ||
        vao_slot->bound_vbo != shared->vbo ||
        vao_slot->bound_ebo != shared->ebo) {
        // Need upload or VAO recreation
        if (tc_mesh_upload_gpu(mesh) == 0) {
            return;
        }
    } else {
        mesh->gpu_vao = vao_slot->vao;
    }

    if (g_gpu_ops && g_gpu_ops->mesh_draw) {
        g_gpu_ops->mesh_draw(mesh);
    }
}

void tc_mesh_delete_gpu(tc_mesh* mesh) {
    if (!mesh) {
        return;
    }

    tc_gpu_context* ctx = tc_gpu_get_context();
    if (!ctx) {
        // No context — just clear cache.
        mesh->gpu_vao = 0;
        mesh->gpu_vbo = 0;
        mesh->gpu_ebo = 0;
        mesh->gpu_version = -1;
        return;
    }

    // Delete per-context VAO
    tc_gpu_vao_slot* vao_slot = tc_gpu_context_vao_slot(ctx, mesh->header.pool_index);
    if (vao_slot) {
        if (vao_slot->vao != 0 && g_gpu_ops && g_gpu_ops->mesh_delete) {
            g_gpu_ops->mesh_delete(vao_slot->vao);
        }
        vao_slot->vao = 0;
        vao_slot->bound_vbo = 0;
        vao_slot->bound_ebo = 0;
    }

    // Delete shared VBO/EBO
    tc_gpu_share_group* group = ctx->share_group;
    tc_gpu_mesh_data_slot* shared = tc_gpu_share_group_mesh_data_slot(group, mesh->header.pool_index);
    if (shared && g_gpu_ops) {
        if (shared->vbo != 0 && g_gpu_ops->buffer_delete) {
            g_gpu_ops->buffer_delete(shared->vbo);
        }
        if (shared->ebo != 0 && g_gpu_ops->buffer_delete) {
            g_gpu_ops->buffer_delete(shared->ebo);
        }
        shared->vbo = 0;
        shared->ebo = 0;
        shared->version = -1;
    }

    mesh->gpu_vao = 0;
    mesh->gpu_vbo = 0;
    mesh->gpu_ebo = 0;
    mesh->gpu_version = -1;
}

// ============================================================================
// Shader uniform operations
// ============================================================================

void tc_shader_set_int(tc_shader* shader, const char* name, int value) {
    if (!shader || shader->gpu_program == 0) return;
    if (g_gpu_ops && g_gpu_ops->shader_set_int) {
        g_gpu_ops->shader_set_int(shader->gpu_program, name, value);
    }
}

void tc_shader_set_float(tc_shader* shader, const char* name, float value) {
    if (!shader || shader->gpu_program == 0) return;
    if (g_gpu_ops && g_gpu_ops->shader_set_float) {
        g_gpu_ops->shader_set_float(shader->gpu_program, name, value);
    }
}

void tc_shader_set_vec2(tc_shader* shader, const char* name, float x, float y) {
    if (!shader || shader->gpu_program == 0) return;
    if (g_gpu_ops && g_gpu_ops->shader_set_vec2) {
        g_gpu_ops->shader_set_vec2(shader->gpu_program, name, x, y);
    }
}

void tc_shader_set_vec3(tc_shader* shader, const char* name, float x, float y, float z) {
    if (!shader || shader->gpu_program == 0) return;
    if (g_gpu_ops && g_gpu_ops->shader_set_vec3) {
        g_gpu_ops->shader_set_vec3(shader->gpu_program, name, x, y, z);
    }
}

void tc_shader_set_vec4(tc_shader* shader, const char* name, float x, float y, float z, float w) {
    if (!shader || shader->gpu_program == 0) return;
    if (g_gpu_ops && g_gpu_ops->shader_set_vec4) {
        g_gpu_ops->shader_set_vec4(shader->gpu_program, name, x, y, z, w);
    }
}

void tc_shader_set_mat4(tc_shader* shader, const char* name, const float* data, bool transpose) {
    if (!shader || shader->gpu_program == 0) return;
    if (g_gpu_ops && g_gpu_ops->shader_set_mat4) {
        g_gpu_ops->shader_set_mat4(shader->gpu_program, name, data, transpose);
    }
}

void tc_shader_set_mat4_array(tc_shader* shader, const char* name, const float* data, int count, bool transpose) {
    if (!shader || shader->gpu_program == 0) return;
    if (g_gpu_ops && g_gpu_ops->shader_set_mat4_array) {
        g_gpu_ops->shader_set_mat4_array(shader->gpu_program, name, data, count, transpose);
    }
}

void tc_shader_set_block_binding(tc_shader* shader, const char* block_name, int binding_point) {
    if (!shader || shader->gpu_program == 0) return;
    if (g_gpu_ops && g_gpu_ops->shader_set_block_binding) {
        g_gpu_ops->shader_set_block_binding(shader->gpu_program, block_name, binding_point);
    }
}

// ============================================================================
// Material GPU operations
// ============================================================================

void tc_material_phase_apply_textures(tc_material_phase* phase) {
    if (!phase) return;

    for (size_t i = 0; i < phase->texture_count; i++) {
        tc_texture* tex = tc_texture_get(phase->textures[i].texture);
        if (tex) {
            tc_texture_bind_gpu(tex, (int)i);
        } else {
            tc_log(TC_LOG_WARN, "tc_material_phase_apply_textures: texture '%s' is invalid (handle %d:%d)",
                   phase->textures[i].name,
                   phase->textures[i].texture.index,
                   phase->textures[i].texture.generation);
        }
    }
}

void tc_material_phase_apply_uniforms(tc_material_phase* phase, tc_shader* shader) {
    if (!phase || !shader) return;

    for (size_t i = 0; i < phase->uniform_count; i++) {
        const tc_uniform_value* u = &phase->uniforms[i];
        switch (u->type) {
            case TC_UNIFORM_BOOL:
            case TC_UNIFORM_INT:
                tc_shader_set_int(shader, u->name, u->data.i);
                break;
            case TC_UNIFORM_FLOAT:
                tc_shader_set_float(shader, u->name, u->data.f);
                break;
            case TC_UNIFORM_VEC2:
                tc_shader_set_vec2(shader, u->name, u->data.v2[0], u->data.v2[1]);
                break;
            case TC_UNIFORM_VEC3:
                tc_shader_set_vec3(shader, u->name, u->data.v3[0], u->data.v3[1], u->data.v3[2]);
                break;
            case TC_UNIFORM_VEC4:
                tc_shader_set_vec4(shader, u->name, u->data.v4[0], u->data.v4[1], u->data.v4[2], u->data.v4[3]);
                break;
            case TC_UNIFORM_MAT4:
                tc_shader_set_mat4(shader, u->name, u->data.m4, true);
                break;
            case TC_UNIFORM_FLOAT_ARRAY:
                break;
            default:
                break;
        }
    }

    // Bind texture samplers
    for (size_t i = 0; i < phase->texture_count; i++) {
        tc_shader_set_int(shader, phase->textures[i].name, (int)i);
    }
}

bool tc_material_phase_apply_gpu(tc_material_phase* phase) {
    if (!phase) return false;

    tc_shader* shader = tc_shader_get(phase->shader);
    if (!shader) {
        tc_log(TC_LOG_ERROR, "tc_material_phase_apply_gpu: invalid shader handle");
        return false;
    }

    if (tc_shader_compile_gpu(shader) == 0) {
        tc_log(TC_LOG_ERROR, "tc_material_phase_apply_gpu: shader compile failed");
        return false;
    }
    tc_shader_use_gpu(shader);

    tc_material_phase_apply_textures(phase);
    tc_material_phase_apply_uniforms(phase, shader);

    return true;
}

void tc_material_phase_apply_with_mvp(
    tc_material_phase* phase,
    tc_shader* shader,
    const float* model,
    const float* view,
    const float* projection
) {
    if (!phase || !shader) return;

    if (shader->gpu_program != 0) {
        tc_shader_use_gpu(shader);
    }

    tc_shader_set_mat4(shader, "u_model", model, false);
    tc_shader_set_mat4(shader, "u_view", view, false);
    tc_shader_set_mat4(shader, "u_projection", projection, false);

    tc_material_phase_apply_textures(phase);
    tc_material_phase_apply_uniforms(phase, shader);
}
