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

// Thread-local context key for per-context VAO management
// Not static: also accessed from tc_gpu_context.c via extern
_Thread_local uintptr_t g_current_context_key = 0;

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

void tc_gpu_set_context_key(uintptr_t key) {
    g_current_context_key = key;
}

uintptr_t tc_gpu_get_context_key(void) {
    return g_current_context_key;
}

// ============================================================================
// Texture GPU operations
// ============================================================================

bool tc_texture_needs_upload(const tc_texture* tex) {
    if (!tex) return false;
    tc_gpu_context* ctx = tc_gpu_get_context();
    if (ctx) {
        tc_gpu_slot* slot = tc_gpu_context_texture_slot(ctx, tex->header.pool_index);
        if (slot) {
            return slot->gl_id == 0 || slot->version != (int32_t)tex->header.version;
        }
    }
    return tex->gpu_id == 0 || tex->gpu_version != (int32_t)tex->header.version;
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
    tc_gpu_slot* slot = NULL;
    uint32_t current_id = tex->gpu_id;
    int32_t current_version = tex->gpu_version;

    if (ctx) {
        slot = tc_gpu_context_texture_slot(ctx, tex->header.pool_index);
        if (slot) {
            current_id = slot->gl_id;
            current_version = slot->version;
        }
    }

    // Already up to date?
    if (current_id != 0 && current_version == (int32_t)tex->header.version) {
        tex->gpu_id = current_id;
        tex->gpu_version = current_version;
        return true;
    }

    // Delete old GPU texture if exists
    if (current_id != 0 && g_gpu_ops->texture_delete) {
        g_gpu_ops->texture_delete(current_id);
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
    if (slot) {
        slot->gl_id = gpu_id;
        slot->version = (int32_t)tex->header.version;
    }

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
    tc_gpu_slot* slot = NULL;
    uint32_t id_to_delete = tex->gpu_id;

    if (ctx) {
        slot = tc_gpu_context_texture_slot(ctx, tex->header.pool_index);
        if (slot) {
            id_to_delete = slot->gl_id;
        }
    }

    if (id_to_delete != 0 && g_gpu_ops && g_gpu_ops->texture_delete) {
        g_gpu_ops->texture_delete(id_to_delete);
    }

    if (slot) {
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

    tc_gpu_context* ctx = tc_gpu_get_context();
    tc_gpu_slot* slot = NULL;
    uint32_t current_program = shader->gpu_program;
    int32_t current_version = shader->gpu_version;

    if (ctx) {
        slot = tc_gpu_context_shader_slot(ctx, shader->pool_index);
        if (slot) {
            current_program = slot->gl_id;
            current_version = slot->version;
        }
    }

    // Already compiled and up to date?
    if (current_program != 0 && current_version == (int32_t)shader->version) {
        shader->gpu_program = current_program;
        shader->gpu_version = current_version;
        return current_program;
    }

    if (!g_gpu_ops || !g_gpu_ops->shader_compile) {
        tc_log(TC_LOG_ERROR, "tc_shader_compile_gpu: GPU ops not set");
        return 0;
    }

    // Check if sources are available
    if (!shader->vertex_source || !shader->fragment_source) {
        tc_log(TC_LOG_ERROR, "tc_shader_compile_gpu: missing sources for '%s' (vertex=%p, fragment=%p)",
               shader->name ? shader->name : shader->uuid,
               (void*)shader->vertex_source, (void*)shader->fragment_source);
        return 0;
    }

    // Delete old program if exists
    if (current_program != 0 && g_gpu_ops->shader_delete) {
        g_gpu_ops->shader_delete(current_program);
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
    if (slot) {
        slot->gl_id = program;
        slot->version = (int32_t)shader->version;
    }

    // Write-through cache
    shader->gpu_program = program;
    shader->gpu_version = (int32_t)shader->version;
    return program;
}

void tc_shader_use_gpu(tc_shader* shader) {
    if (!shader) {
        return;
    }

    // Compile if needed (this also updates write-through cache)
    tc_gpu_context* ctx = tc_gpu_get_context();
    uint32_t program = shader->gpu_program;

    if (ctx) {
        tc_gpu_slot* slot = tc_gpu_context_shader_slot(ctx, shader->pool_index);
        if (slot) {
            program = slot->gl_id;
        }
    }

    if (program == 0 || shader->gpu_version != (int32_t)shader->version) {
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
    tc_gpu_slot* slot = NULL;
    uint32_t id_to_delete = shader->gpu_program;

    if (ctx) {
        slot = tc_gpu_context_shader_slot(ctx, shader->pool_index);
        if (slot) {
            id_to_delete = slot->gl_id;
        }
    }

    if (id_to_delete != 0 && g_gpu_ops && g_gpu_ops->shader_delete) {
        g_gpu_ops->shader_delete(id_to_delete);
    }

    if (slot) {
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
    tc_gpu_mesh_slot* slot = NULL;

    if (ctx) {
        slot = tc_gpu_context_mesh_slot(ctx, mesh->header.pool_index);
    }

    // Determine current VBO/EBO state from slot or legacy fields
    uint32_t current_vbo = slot ? slot->vbo : mesh->gpu_vbo;
    int32_t current_version = slot ? slot->version : mesh->gpu_version;

    bool data_current = (current_vbo != 0 &&
                         current_version == (int32_t)mesh->header.version);

    if (data_current) {
        // VBO/EBO data is up to date. Check if VAO exists for current context.
        uint32_t vao = slot ? slot->vao : 0;

        // Fallback to legacy VAO lookup if no GPUContext
        if (!slot) {
            vao = tc_mesh_get_vao(mesh, g_current_context_key);
        }

        if (vao != 0) {
            mesh->gpu_vao = vao;
            return vao;
        }

        // Create VAO for this context (reuse shared VBO/EBO)
        // Write-through needed for mesh_create_vao which reads mesh->gpu_vbo/ebo
        mesh->gpu_vbo = current_vbo;
        mesh->gpu_ebo = slot ? slot->ebo : mesh->gpu_ebo;

        vao = 0;
        if (g_gpu_ops->mesh_create_vao) {
            vao = g_gpu_ops->mesh_create_vao(mesh);
        }
        if (vao == 0) {
            tc_log(TC_LOG_ERROR, "tc_mesh_upload_gpu: mesh_create_vao failed for '%s'",
                   mesh->header.name ? mesh->header.name : mesh->header.uuid);
            return 0;
        }

        if (slot) {
            slot->vao = vao;
        } else {
            tc_mesh_set_vao(mesh, g_current_context_key, vao);
        }
        mesh->gpu_vao = vao;
        return vao;
    }

    // VBO/EBO data needs upload (first time or version changed).
    // Delete existing VAO for this context.
    if (slot) {
        if (slot->vao != 0 && g_gpu_ops->mesh_delete) {
            g_gpu_ops->mesh_delete(slot->vao);
            slot->vao = 0;
        }
        // Delete old VBO/EBO if this context owns shared resources
        if (ctx->owns_shared_resources) {
            if (slot->vbo != 0 && g_gpu_ops->buffer_delete) {
                g_gpu_ops->buffer_delete(slot->vbo);
            }
            if (slot->ebo != 0 && g_gpu_ops->buffer_delete) {
                g_gpu_ops->buffer_delete(slot->ebo);
            }
        }
        slot->vbo = 0;
        slot->ebo = 0;
    } else {
        // Legacy path: delete all per-context VAOs
        if (g_gpu_ops->mesh_delete) {
            for (uint32_t i = 0; i < mesh->gpu_vao_count; i++) {
                if (mesh->gpu_vaos[i] != 0) {
                    g_gpu_ops->mesh_delete(mesh->gpu_vaos[i]);
                }
            }
        }
        mesh->gpu_vao_count = 0;
    }

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

    // Store in context slot
    if (slot) {
        slot->vao = vao;
        slot->vbo = mesh->gpu_vbo;  // mesh_upload sets these
        slot->ebo = mesh->gpu_ebo;
        slot->version = (int32_t)mesh->header.version;
    } else {
        tc_mesh_set_vao(mesh, g_current_context_key, vao);
    }

    mesh->gpu_vao = vao;
    mesh->gpu_version = (int32_t)mesh->header.version;
    return vao;
}

void tc_mesh_draw_gpu(tc_mesh* mesh) {
    if (!mesh) {
        return;
    }

    tc_gpu_context* ctx = tc_gpu_get_context();
    tc_gpu_mesh_slot* slot = NULL;

    if (ctx) {
        slot = tc_gpu_context_mesh_slot(ctx, mesh->header.pool_index);
    }

    // Check if VBO/EBO data is current
    uint32_t current_vbo = slot ? slot->vbo : mesh->gpu_vbo;
    int32_t current_version = slot ? slot->version : mesh->gpu_version;

    bool data_stale = (current_vbo == 0 ||
                       current_version != (int32_t)mesh->header.version);

    if (data_stale) {
        if (tc_mesh_upload_gpu(mesh) == 0) {
            return;
        }
    } else {
        // Data is current, ensure VAO exists for this context
        uint32_t vao = slot ? slot->vao : 0;
        if (!slot) {
            vao = tc_mesh_get_vao(mesh, g_current_context_key);
        }
        if (vao == 0) {
            if (tc_mesh_upload_gpu(mesh) == 0) {
                return;
            }
        } else {
            mesh->gpu_vao = vao;
        }
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
    tc_gpu_mesh_slot* slot = NULL;

    if (ctx) {
        slot = tc_gpu_context_mesh_slot(ctx, mesh->header.pool_index);
    }

    if (slot) {
        // Delete VAO (per-context)
        if (slot->vao != 0 && g_gpu_ops && g_gpu_ops->mesh_delete) {
            g_gpu_ops->mesh_delete(slot->vao);
        }
        // Delete VBO/EBO only if this context owns shared resources
        if (ctx->owns_shared_resources && g_gpu_ops) {
            if (slot->vbo != 0 && g_gpu_ops->buffer_delete) {
                g_gpu_ops->buffer_delete(slot->vbo);
            }
            if (slot->ebo != 0 && g_gpu_ops->buffer_delete) {
                g_gpu_ops->buffer_delete(slot->ebo);
            }
        }
        slot->vao = 0;
        slot->vbo = 0;
        slot->ebo = 0;
        slot->version = -1;
    } else {
        // Legacy path: delete all per-context VAOs
        if (g_gpu_ops && g_gpu_ops->mesh_delete) {
            for (uint32_t i = 0; i < mesh->gpu_vao_count; i++) {
                if (mesh->gpu_vaos[i] != 0) {
                    g_gpu_ops->mesh_delete(mesh->gpu_vaos[i]);
                }
            }
        }
        mesh->gpu_vao_count = 0;
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
            // Texture handle is stale or invalid - log warning
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
                // Arrays handled separately if needed
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

    // Get shader
    tc_shader* shader = tc_shader_get(phase->shader);
    if (!shader) {
        tc_log(TC_LOG_ERROR, "tc_material_phase_apply_gpu: invalid shader handle");
        return false;
    }

    // Compile and use shader
    if (tc_shader_compile_gpu(shader) == 0) {
        tc_log(TC_LOG_ERROR, "tc_material_phase_apply_gpu: shader compile failed");
        return false;
    }
    tc_shader_use_gpu(shader);

    // Apply textures
    tc_material_phase_apply_textures(phase);

    // Apply uniforms
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

    // Ensure shader is active (defensive - caller should have called use() already)
    if (shader->gpu_program != 0) {
        tc_shader_use_gpu(shader);
    }

    // Set MVP matrices
    tc_shader_set_mat4(shader, "u_model", model, false);
    tc_shader_set_mat4(shader, "u_view", view, false);
    tc_shader_set_mat4(shader, "u_projection", projection, false);

    // Apply textures
    tc_material_phase_apply_textures(phase);

    // Apply uniforms
    tc_material_phase_apply_uniforms(phase, shader);
}
