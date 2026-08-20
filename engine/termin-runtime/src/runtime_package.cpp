#include <termin/runtime/runtime_package.hpp>

#include "runtime_package_manifest.hpp"
#include "runtime_shader_inference.hpp"

#include <any>
#include <array>
#include <cctype>
#include <cmath>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <filesystem>
#include <sstream>
#include <stdexcept>
#include <string>
#include <unordered_set>
#include <utility>
#include <vector>

#include <inspect/tc_kind_cpp.hpp>
#include <tcbase/tc_log.h>
#include <tcbase/trent/json.h>
#include <termin/bootstrap/bootstrap.hpp>
#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>
#include <tgfx/tgfx_shader_handle.hpp>
#include <tgfx/tgfx_shader_program_handle.hpp>
#include <tgfx/tgfx_texture_handle.hpp>
#ifndef TERMIN_RUNTIME_RENDER_ONLY
#include <termin/foliage/foliage_data_registry.hpp>
#include <termin/gui_native/ui_document_asset.hpp>
#endif
#include <termin/image/image_decode.hpp>
#include <termin/render/render_pipeline.hpp>
#ifndef TERMIN_RUNTIME_RENDER_ONLY
#include <termin/render/sprite_asset.hpp>
#endif
#include <termin/render/tc_pipeline_template.hpp>

extern "C" {
#include <core/tc_component.h>
#include <render/tc_pass.h>
}

namespace termin::runtime {

    struct RuntimePackageResourceKeepalive {
        std::shared_ptr<RuntimePackageReader> reader;
        std::vector<TcShader> shaders;
        std::vector<TcShaderProgram> shader_programs;
        std::vector<TcTexture> textures;
        std::vector<TcMaterial> materials;
        std::vector<TcMesh> meshes;
#ifndef TERMIN_RUNTIME_RENDER_ONLY
        std::vector<TcFoliageData> foliage_data;
#endif
#ifndef TERMIN_RUNTIME_RENDER_ONLY
        std::vector<TcSpriteAsset> sprites;
#endif
        std::vector<TcPipelineTemplate> pipeline_templates;
#ifndef TERMIN_RUNTIME_RENDER_ONLY
        std::vector<gui_native::TcUiDocumentAsset> ui_documents;
#endif
    };

    namespace {

        std::string read_text_file(const RuntimePackageReader& reader, const std::string& path) {
            const RuntimePackageBytes bytes = reader.read(path);
            return std::string(reinterpret_cast<const char*>(bytes.data), bytes.size);
        }

        RuntimePackageBytes read_binary_file(const RuntimePackageReader& reader, const std::string& path) {
            return reader.read(path);
        }

        const nos::trent* dict_get(const nos::trent& t, const char* key) {
            if (!t.is_dict()) {
                return nullptr;
            }
            return t._get(key);
        }

        std::string string_field(const nos::trent& t, const char* key, const std::string& def = "") {
            const nos::trent* v = dict_get(t, key);
            if (!v || !v->is_string()) {
                return def;
            }
            return v->as_string();
        }

        double number_field(const nos::trent& t, const char* key, double def = 0.0) {
            const nos::trent* v = dict_get(t, key);
            if (!v || !v->is_numer()) {
                return def;
            }
            return static_cast<double>(v->as_numer());
        }

        uint32_t uint32_field(const nos::trent& t, const char* key, uint32_t def = 0) {
            const nos::trent* v = dict_get(t, key);
            if (!v || !v->is_numer()) {
                return def;
            }
            const double value = static_cast<double>(v->as_numer());
            if (value <= 0.0) {
                return 0;
            }
            if (value >= static_cast<double>(UINT32_MAX)) {
                return UINT32_MAX;
            }
            return static_cast<uint32_t>(value);
        }

        std::string lowercase_copy(std::string s) {
            for (char& ch : s) {
                ch = static_cast<char>(std::tolower(static_cast<unsigned char>(ch)));
            }
            return s;
        }

        bool shader_language_from_spec(const nos::trent& spec, tc_shader_language& out, std::string& error) {
            const std::string language = lowercase_copy(string_field(spec, "language"));
            if (language.empty()) {
                error = "shader resource has no explicit language";
                return false;
            }
            if (language == "glsl") {
                out = TC_SHADER_LANGUAGE_GLSL;
                return true;
            }
            if (language == "slang") {
                out = TC_SHADER_LANGUAGE_SLANG;
                return true;
            }
            if (language == "hlsl") {
                out = TC_SHADER_LANGUAGE_HLSL;
                return true;
            }
            error = "shader resource has unsupported language '" + language + "'";
            return false;
        }

        void validate_scene_identity(const std::string& identity) {
            if (identity.empty() || identity.front() == '/' || identity.back() == '/' ||
                identity.find('\\') != std::string::npos || identity.find(':') != std::string::npos ||
                !lowercase_copy(identity).ends_with(".scene")) {
                throw std::runtime_error("runtime scene identity must be a project-relative .scene path: " + identity);
            }
            const std::filesystem::path path(identity);
            for (const std::filesystem::path& component : path) {
                if (component == "." || component == "..") {
                    throw std::runtime_error("runtime scene identity must not contain dot segments: " + identity);
                }
            }
        }

        std::vector<TcTexture>& runtime_builtin_texture_keepalive() {
            static std::vector<TcTexture> textures;
            return textures;
        }

        void ensure_runtime_builtin_textures() {
            auto& textures = runtime_builtin_texture_keepalive();
            if (textures.size() == 3 && textures[0].is_valid() && textures[1].is_valid() && textures[2].is_valid()) {
                return;
            }
            textures.clear();
            textures.push_back(TcTexture::white_1x1());
            textures.push_back(TcTexture::white_1x1_srgb());
            textures.push_back(TcTexture::normal_1x1());
            for (const TcTexture& texture : textures) {
                if (!texture.is_valid()) {
                    tc_log_error("RuntimePackageLoader: failed to create builtin texture");
                    textures.clear();
                    return;
                }
            }
        }

        TcTexture runtime_builtin_texture(const std::string& name, tc_texture_encoding expected_encoding) {
            ensure_runtime_builtin_textures();
            const auto& textures = runtime_builtin_texture_keepalive();
            if (textures.size() != 3)
                return {};
            if (name == "white") {
                return expected_encoding == TC_TEXTURE_ENCODING_SRGB ? textures[1] : textures[0];
            }
            if (name == "normal") {
                if (expected_encoding != TC_TEXTURE_ENCODING_LINEAR) {
                    tc_log_error("RuntimePackageLoader: builtin normal texture is only valid for Linear slots");
                    return {};
                }
                return textures[2];
            }
            return {};
        }

        TcTexture runtime_material_texture_from_spec(const nos::trent& spec,
                                                     const std::string& material_uuid,
                                                     tc_texture_encoding expected_encoding) {
            if (spec.is_string()) {
                const std::string uuid = spec.as_string();
                if (uuid.empty()) {
                    return {};
                }
                TcTexture texture = TcTexture::from_uuid(uuid);
                if (!texture.is_valid()) {
                    tc_log_error("RuntimePackageLoader: material '%s' references missing texture asset '%s'",
                                 material_uuid.c_str(),
                                 uuid.c_str());
                }
                return texture;
            }

            if (!spec.is_dict()) {
                tc_log_error("RuntimePackageLoader: material '%s' texture spec must be an object or uuid string",
                             material_uuid.c_str());
                return {};
            }

            const std::string kind = string_field(spec, "kind");
            if (kind == "builtin") {
                const std::string name = string_field(spec, "name");
                TcTexture texture = runtime_builtin_texture(name, expected_encoding);
                if (!texture.is_valid()) {
                    tc_log_error("RuntimePackageLoader: material '%s' references unknown builtin texture '%s'",
                                 material_uuid.c_str(),
                                 name.c_str());
                }
                return texture;
            }

            if (kind == "asset") {
                const std::string uuid = string_field(spec, "uuid");
                if (uuid.empty()) {
                    tc_log_error("RuntimePackageLoader: material '%s' asset texture spec has no uuid",
                                 material_uuid.c_str());
                    return {};
                }
                TcTexture texture = TcTexture::from_uuid(uuid);
                if (!texture.is_valid()) {
                    tc_log_error("RuntimePackageLoader: material '%s' references missing texture asset '%s'",
                                 material_uuid.c_str(),
                                 uuid.c_str());
                }
                return texture;
            }

            tc_log_error("RuntimePackageLoader: material '%s' texture spec has unsupported kind '%s'",
                         material_uuid.c_str(),
                         kind.c_str());
            return {};
        }

        bool set_material_uniform_checked(tc_material* material,
                                          const char* name,
                                          tc_uniform_type type,
                                          const void* value,
                                          const std::string& material_uuid,
                                          std::string& error) {
            if (!material || material->phase_count == 0) {
                error = "material '" + material_uuid + "' has no writable phases";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            if (!name || name[0] == '\0' || std::strlen(name) >= TC_UNIFORM_NAME_MAX) {
                error = "material '" + material_uuid + "' has an invalid uniform name";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            // Validate every phase first so a structural failure cannot leave
            // a multi-phase material only partially updated.
            for (size_t phase_index = 0; phase_index < material->phase_count; ++phase_index) {
                tc_material_phase* phase = &material->phases[phase_index];
                tc_uniform_value* existing = tc_material_phase_find_uniform(phase, name);
                if (existing && existing->type != static_cast<uint8_t>(type)) {
                    error = "material '" + material_uuid + "' uniform '" + name +
                            "' conflicts with an existing phase uniform kind";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                if (!existing && phase->uniform_count >= TC_MATERIAL_MAX_UNIFORMS) {
                    error = "material '" + material_uuid + "' phase uniform capacity is exhausted while setting '" +
                            name + "'";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
            }

            for (size_t phase_index = 0; phase_index < material->phase_count; ++phase_index) {
                if (!tc_material_phase_set_uniform(&material->phases[phase_index], name, type, value)) {
                    error = "material '" + material_uuid + "' failed to set uniform '" + name + "'";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
            }
            return true;
        }

        bool apply_material_uniforms(TcMaterial& material,
                                     const nos::trent* uniforms,
                                     const TcShaderProgram& program,
                                     const std::string& material_uuid,
                                     std::string& error) {
            if (!uniforms) {
                return true;
            }
            if (!uniforms->is_dict()) {
                error = "material '" + material_uuid + "' uniforms must be an object";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            tc_material* raw_material = material.get();

            for (const auto& item : uniforms->as_dict()) {
                const std::string& name = item.first;
                const nos::trent& value = item.second;
                if (name.empty()) {
                    error = "material '" + material_uuid + "' uniform name must not be empty";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                std::string declared_type;
                if (program.is_valid()) {
                    const tc_shader_program* raw_program = program.get();
                    for (uint32_t index = 0; index < raw_program->property_count; ++index) {
                        if (name == raw_program->properties[index].name) {
                            declared_type = raw_program->properties[index].property_type;
                            break;
                        }
                    }
                }
                const nos::trent* payload = &value;
                const std::string& semantic_type = declared_type;
                if (value.is_dict()) {
                    error = "material '" + material_uuid + "' uniform '" + name +
                            "' must be an array/scalar; its kind belongs to the shader schema";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                if (payload->is_bool()) {
                    if (!semantic_type.empty() && semantic_type != "Bool") {
                        error = "material '" + material_uuid + "' uniform '" + name +
                                "' is boolean but shader schema requires '" + semantic_type + "'";
                        tc_log_error("RuntimePackageLoader: %s", error.c_str());
                        return false;
                    }
                    int v = payload->as_bool() ? 1 : 0;
                    if (!set_material_uniform_checked(
                            raw_material, name.c_str(), TC_UNIFORM_BOOL, &v, material_uuid, error))
                        return false;
                    continue;
                }
                if (payload->is_numer()) {
                    if (!semantic_type.empty() && semantic_type != "Int" && semantic_type != "Float") {
                        error = "material '" + material_uuid + "' uniform '" + name +
                                "' is scalar but shader schema requires '" + semantic_type + "'";
                        tc_log_error("RuntimePackageLoader: %s", error.c_str());
                        return false;
                    }
                    if (semantic_type == "Int") {
                        int v = static_cast<int>(payload->as_numer());
                        if (!set_material_uniform_checked(
                                raw_material, name.c_str(), TC_UNIFORM_INT, &v, material_uuid, error))
                            return false;
                    } else {
                        float v = static_cast<float>(payload->as_numer());
                        if (!set_material_uniform_checked(
                                raw_material, name.c_str(), TC_UNIFORM_FLOAT, &v, material_uuid, error))
                            return false;
                    }
                    continue;
                }
                if (payload->is_list()) {
                    const auto& values = payload->as_list();
                    bool all_numbers = !values.empty();
                    for (const nos::trent& element : values) {
                        if (!element.is_numer()) {
                            all_numbers = false;
                            break;
                        }
                    }
                    tc_uniform_type uniform_type = TC_UNIFORM_NONE;
                    size_t expected_components = 0;
                    if (semantic_type == "Vec2") {
                        uniform_type = TC_UNIFORM_VEC2;
                        expected_components = 2;
                    } else if (semantic_type == "Vec3" || (semantic_type.empty() && values.size() == 3)) {
                        uniform_type = TC_UNIFORM_VEC3;
                        expected_components = 3;
                    } else if (semantic_type == "Vec4" || (semantic_type.empty() && values.size() == 4)) {
                        uniform_type = TC_UNIFORM_VEC4;
                        expected_components = 4;
                    } else if (semantic_type == "SrgbColor") {
                        uniform_type = TC_UNIFORM_SRGB_COLOR;
                        expected_components = 4;
                    } else if (semantic_type == "LinearColor") {
                        uniform_type = TC_UNIFORM_LINEAR_COLOR;
                        expected_components = 4;
                    } else if (semantic_type == "Mat4") {
                        uniform_type = TC_UNIFORM_MAT4;
                        expected_components = 16;
                    }
                    if (all_numbers && uniform_type != TC_UNIFORM_NONE && values.size() == expected_components) {
                        float components[16] = {};
                        for (size_t index = 0; index < values.size(); ++index)
                            components[index] = static_cast<float>(values[index].as_numer());
                        if (!set_material_uniform_checked(
                                raw_material, name.c_str(), uniform_type, components, material_uuid, error))
                            return false;
                        continue;
                    }
                }
                error = "material '" + material_uuid + "' uniform '" + name + "' has a value incompatible with" +
                        (semantic_type.empty() ? " supported runtime uniform types"
                                               : " shader schema '" + semantic_type + "'");
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            return true;
        }

        bool material_texture_slot_encoding(const TcMaterial& material,
                                            const std::string& name,
                                            tc_texture_encoding& encoding) {
            tc_material* raw = material.get();
            if (!raw)
                return false;
            for (size_t phase_index = 0; phase_index < raw->phase_count; ++phase_index) {
                tc_material_texture* slot = tc_material_phase_find_texture(&raw->phases[phase_index], name.c_str());
                if (slot && slot->has_expected_encoding) {
                    encoding = static_cast<tc_texture_encoding>(slot->expected_encoding);
                    return true;
                }
            }
            return false;
        }

        bool material_has_texture_slot(const TcMaterial& material, const std::string& name) {
            tc_material* raw = material.get();
            if (!raw)
                return false;
            for (size_t phase_index = 0; phase_index < raw->phase_count; ++phase_index) {
                if (tc_material_phase_find_texture(&raw->phases[phase_index], name.c_str())) {
                    return true;
                }
            }
            return false;
        }

        bool configure_material_texture_slots(TcMaterial& material,
                                              const TcShaderProgram& program,
                                              const std::string& material_uuid,
                                              std::string& error) {
            tc_material* raw_material = material.get();
            tc_shader_program* raw_program = program.get();
            if (!raw_material || !raw_program) {
                error = "material '" + material_uuid + "' has stale material or shader program";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            for (uint32_t property_index = 0; property_index < raw_program->property_count; ++property_index) {
                const tc_shader_program_property& property = raw_program->properties[property_index];
                const bool is_texture = std::strcmp(property.property_type, "Texture") == 0 ||
                                        std::strcmp(property.property_type, "Texture2D") == 0;
                if (!is_texture)
                    continue;
                for (size_t phase_index = 0; phase_index < raw_material->phase_count; ++phase_index) {
                    const bool declared =
                        property.has_expected_encoding
                            ? tc_material_phase_declare_texture(
                                  &raw_material->phases[phase_index],
                                  property.name,
                                  static_cast<tc_texture_encoding>(property.expected_encoding))
                            : tc_material_phase_declare_texture_slot(&raw_material->phases[phase_index], property.name);
                    if (!declared) {
                        error =
                            "material '" + material_uuid + "' failed to declare texture slot '" + property.name + "'";
                        tc_log_error("RuntimePackageLoader: %s", error.c_str());
                        return false;
                    }
                }
            }

            for (uint32_t property_index = 0; property_index < raw_program->property_count; ++property_index) {
                const tc_shader_program_property& property = raw_program->properties[property_index];
                const bool is_texture = std::strcmp(property.property_type, "Texture") == 0 ||
                                        std::strcmp(property.property_type, "Texture2D") == 0;
                if (!is_texture)
                    continue;
                const auto expected = property.has_expected_encoding
                                          ? static_cast<tc_texture_encoding>(property.expected_encoding)
                                          : TC_TEXTURE_ENCODING_LINEAR;
                const std::string default_name =
                    property.has_default && property.default_text[0] != '\0' ? property.default_text : "white";
                TcTexture texture = runtime_builtin_texture(default_name, expected);
                if (!texture.is_valid()) {
                    error = "material '" + material_uuid + "' texture slot '" + property.name +
                            "' has invalid builtin default '" + default_name + "'";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                if (material.set_texture(property.name, texture) == 0) {
                    error = "material '" + material_uuid + "' failed to bind default for texture slot '" +
                            property.name + "'";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
            }
            return true;
        }

        bool apply_material_textures(TcMaterial& material,
                                     const nos::trent* textures,
                                     const std::string& material_uuid,
                                     std::string& error) {
            if (!textures) {
                return true;
            }
            if (!textures->is_dict()) {
                tc_log_error("RuntimePackageLoader: material '%s' textures must be an object", material_uuid.c_str());
                error = "material '" + material_uuid + "' textures must be an object";
                return false;
            }

            for (const auto& item : textures->as_dict()) {
                const std::string& name = item.first;
                if (name.empty()) {
                    tc_log_error("RuntimePackageLoader: material '%s' texture name must not be empty",
                                 material_uuid.c_str());
                    error = "material '" + material_uuid + "' texture name must not be empty";
                    return false;
                }
                tc_texture_encoding expected_encoding = TC_TEXTURE_ENCODING_LINEAR;
                if (!material_has_texture_slot(material, name)) {
                    error = "material '" + material_uuid + "' texture slot '" + name + "' is not in shader schema";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                (void)material_texture_slot_encoding(material, name, expected_encoding);
                TcTexture texture = runtime_material_texture_from_spec(item.second, material_uuid, expected_encoding);
                if (!texture.is_valid()) {
                    error = "material '" + material_uuid + "' failed to resolve texture slot '" + name + "'";
                    return false;
                }
                if (material.set_texture(name.c_str(), texture) == 0) {
                    error = "material '" + material_uuid + "' failed to bind texture slot '" + name + "'";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
            }
            return true;
        }

        template <std::size_t N> void copy_shader_metadata_text(char (&destination)[N], const std::string& source) {
            std::snprintf(destination, N, "%s", source.c_str());
        }

        bool restore_shader_contract(const nos::trent& spec, tc_shader* shader, std::string& error) {
            const nos::trent* contract = dict_get(spec, "shader_contract");
            if (!contract) {
                return true;
            }
            if (!contract->is_dict()) {
                error = "shader_contract must be an object";
                return false;
            }

            const uint32_t schema_version =
                uint32_field(*contract, "schema_version", TC_SHADER_CONTRACT_SCHEMA_VERSION);
            if (schema_version != TC_SHADER_CONTRACT_SCHEMA_VERSION) {
                error = "shader_contract has an unsupported schema_version";
                return false;
            }

            const nos::trent* input_list = dict_get(*contract, "vertex_inputs");
            if (!input_list || !input_list->is_list()) {
                error = "shader_contract.vertex_inputs must be a list";
                return false;
            }

            std::vector<tc_shader_contract_vertex_input> vertex_inputs;
            vertex_inputs.reserve(input_list->as_list().size());
            std::unordered_set<std::string> semantics;
            for (const nos::trent& item : input_list->as_list()) {
                if (!item.is_dict()) {
                    error = "shader_contract vertex input must be an object";
                    return false;
                }
                const std::string semantic = string_field(item, "semantic");
                const uint32_t type = uint32_field(item, "type");
                if (semantic.empty() || semantic.size() >= TC_SHADER_RESOURCE_NAME_MAX ||
                    type == TC_SHADER_CONTRACT_VALUE_UNKNOWN || type > TC_SHADER_CONTRACT_VALUE_MATRIX4) {
                    error = "shader_contract vertex input is incomplete or invalid";
                    return false;
                }
                if (!semantics.insert(semantic).second) {
                    error = "shader_contract contains duplicate vertex input '" + semantic + "'";
                    return false;
                }
                tc_shader_contract_vertex_input input{};
                copy_shader_metadata_text(input.semantic, semantic);
                input.type = type;
                const nos::trent* required = dict_get(item, "required");
                if (required && !required->is_bool()) {
                    error = "shader_contract vertex input required flag must be boolean";
                    return false;
                }
                input.required = !required || required->as_bool() ? 1u : 0u;
                vertex_inputs.push_back(input);
            }

            const std::string debug_name = string_field(*contract, "debug_name");
            const std::string source_debug_name =
                string_field(*contract, "source_debug_name", "runtime package declaration");
            const tc_shader_contract_desc descriptor{
                schema_version,
                TC_SHADER_CONTRACT_SOURCE_DECLARED,
                vertex_inputs.data(),
                static_cast<uint32_t>(vertex_inputs.size()),
                nullptr,
                0u,
                debug_name.empty() ? nullptr : debug_name.c_str(),
                source_debug_name.c_str(),
            };
            if (!tc_shader_set_contract(shader, &descriptor)) {
                error = "failed to restore shader_contract metadata";
                return false;
            }
            return true;
        }

        bool restore_shader_surface_producer(const nos::trent& spec, tc_shader* shader, std::string& error) {
            const nos::trent* producer = dict_get(spec, "surface_producer");
            if (!producer) {
                return true;
            }
            if (!producer->is_dict()) {
                error = "surface_producer must be an object";
                return false;
            }

            const std::string contract_id = string_field(*producer, "contract_id");
            const uint32_t contract_version = uint32_field(*producer, "contract_version");
            const std::string surface_type_name = string_field(*producer, "surface_type_name");
            const std::string evaluator_entry = string_field(*producer, "evaluator_entry");
            const std::string evaluator_source = string_field(*producer, "evaluator_source");
            const std::string source_identity = string_field(*producer, "source_identity");
            if (contract_id.empty() || contract_version == 0 || surface_type_name.empty() || evaluator_entry.empty() ||
                evaluator_source.empty() || source_identity.empty()) {
                error = "surface_producer is missing required contract metadata";
                return false;
            }

            std::vector<tc_shader_fragment_input> fragment_inputs;
            if (const nos::trent* inputs = dict_get(*producer, "fragment_inputs")) {
                if (!inputs->is_list()) {
                    error = "surface_producer.fragment_inputs must be a list";
                    return false;
                }
                fragment_inputs.reserve(inputs->as_list().size());
                for (const nos::trent& item : inputs->as_list()) {
                    if (!item.is_dict()) {
                        error = "surface_producer fragment input must be an object";
                        return false;
                    }
                    const std::string semantic = string_field(item, "semantic");
                    const uint32_t type = uint32_field(item, "type");
                    if (semantic.empty() || type == 0) {
                        error = "surface_producer fragment input is incomplete";
                        return false;
                    }
                    tc_shader_fragment_input input{};
                    copy_shader_metadata_text(input.semantic, semantic);
                    input.type = type;
                    fragment_inputs.push_back(input);
                }
            }

            std::vector<tc_shader_resource_requirement> resources;
            std::vector<std::vector<tc_shader_resource_field>> resource_fields;
            if (const nos::trent* resource_list = dict_get(*producer, "resources")) {
                if (!resource_list->is_list()) {
                    error = "surface_producer.resources must be a list";
                    return false;
                }
                resources.reserve(resource_list->as_list().size());
                resource_fields.reserve(resource_list->as_list().size());
                for (const nos::trent& item : resource_list->as_list()) {
                    if (!item.is_dict()) {
                        error = "surface_producer resource must be an object";
                        return false;
                    }
                    const std::string name = string_field(item, "name");
                    const uint32_t kind = uint32_field(item, "kind");
                    const uint32_t scope = uint32_field(item, "scope");
                    const uint32_t stage_mask = uint32_field(item, "stage_mask");
                    if (name.empty() || kind == 0 || scope == 0 || stage_mask == 0) {
                        error = "surface_producer resource is incomplete";
                        return false;
                    }

                    resource_fields.emplace_back();
                    std::vector<tc_shader_resource_field>& fields = resource_fields.back();
                    if (const nos::trent* field_list = dict_get(item, "fields")) {
                        if (!field_list->is_list()) {
                            error = "surface_producer resource fields must be a list";
                            return false;
                        }
                        fields.reserve(field_list->as_list().size());
                        for (const nos::trent& field_item : field_list->as_list()) {
                            if (!field_item.is_dict()) {
                                error = "surface_producer resource field must be an object";
                                return false;
                            }
                            const std::string field_name = string_field(field_item, "name");
                            const std::string field_type = string_field(field_item, "type");
                            if (field_name.empty() || field_type.empty()) {
                                error = "surface_producer resource field is incomplete";
                                return false;
                            }
                            tc_shader_resource_field field{};
                            copy_shader_metadata_text(field.name, field_name);
                            copy_shader_metadata_text(field.type, field_type);
                            field.offset = uint32_field(field_item, "offset");
                            field.size = uint32_field(field_item, "size");
                            fields.push_back(field);
                        }
                    }

                    tc_shader_resource_requirement requirement{};
                    copy_shader_metadata_text(requirement.name, name);
                    requirement.kind = kind;
                    requirement.scope = scope;
                    requirement.stage_mask = stage_mask;
                    requirement.size = uint32_field(item, "size");
                    requirement.element_stride = uint32_field(item, "element_stride");
                    requirement.fields = fields.empty() ? nullptr : fields.data();
                    requirement.field_count = static_cast<uint32_t>(fields.size());
                    resources.push_back(requirement);
                }
            }

            const tc_shader_surface_producer_desc descriptor{
                uint32_field(*producer, "schema_version", TC_SHADER_SURFACE_PRODUCER_SCHEMA_VERSION),
                contract_id.c_str(),
                contract_version,
                surface_type_name.c_str(),
                evaluator_entry.c_str(),
                evaluator_source.c_str(),
                source_identity.c_str(),
                fragment_inputs.data(),
                static_cast<uint32_t>(fragment_inputs.size()),
                resources.data(),
                static_cast<uint32_t>(resources.size()),
            };
            if (!tc_shader_set_surface_producer(shader, &descriptor)) {
                error = "failed to restore surface_producer metadata";
                return false;
            }
            return true;
        }

        bool load_shader_resource(const RuntimePackageReader& reader,
                                  const std::string& spec_path,
                                  const nos::trent& spec,
                                  RuntimePackageResourceKeepalive& keepalive,
                                  std::string& error) {
            const std::string uuid = string_field(spec, "uuid");
            if (uuid.empty()) {
                error = "shader resource has no uuid";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            tc_shader_language language = TC_SHADER_LANGUAGE_UNSPECIFIED;
            if (!shader_language_from_spec(spec, language, error)) {
                error = "shader '" + uuid + "': " + error;
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            const std::string vertex_rel = string_field(spec, "vertex_source_path");
            const std::string fragment_rel = string_field(spec, "fragment_source_path");
            if (fragment_rel.empty()) {
                error = "shader '" + uuid + "' has no fragment_source_path";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            const std::string vertex_source = vertex_rel.empty() ? std::string() : read_text_file(reader, vertex_rel);
            const std::string fragment_source = read_text_file(reader, fragment_rel);
            const std::string geometry_rel = string_field(spec, "geometry_source_path");
            const std::string geometry_source =
                geometry_rel.empty() ? std::string() : read_text_file(reader, geometry_rel);

            TcShader shader = TcShader::get_or_create(uuid);
            if (!shader.is_valid()) {
                error = "failed to create shader '" + uuid + "'";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            const std::string name = string_field(spec, "name", uuid);
            const std::string source_path = reader.describe(spec_path);
            const std::string vertex_entry = string_field(spec, "vertex_entry");
            const std::string fragment_entry = string_field(spec, "fragment_entry");
            const std::string geometry_entry = string_field(spec, "geometry_entry");
            shader.set_language(language);
            shader.set_artifact_policy(language == TC_SHADER_LANGUAGE_SLANG ? TC_SHADER_ARTIFACT_REQUIRED
                                                                            : TC_SHADER_ARTIFACT_OPTIONAL);
            TcShaderSources sources;
            sources.vertex = vertex_source;
            sources.fragment = fragment_source;
            sources.geometry = geometry_source;
            sources.name = name;
            sources.source_path = source_path;
            sources.vertex_entry = vertex_entry;
            sources.fragment_entry = fragment_entry;
            sources.geometry_entry = geometry_entry;
            shader.set_sources(sources);
            tc_shader* raw = shader.get();
            if (!raw || !raw->fragment_source) {
                error = "shader '" + uuid + "' has no registered fragment source";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            shader.set_features(uint32_field(spec, "features", 0));
            detail::set_shader_features_from_glsl(raw, fragment_source);
            detail::set_shader_material_ubo_layout_from_glsl(raw, fragment_source);
            if (!restore_shader_contract(spec, raw, error)) {
                error = "shader '" + uuid + "': " + error;
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            if (!restore_shader_surface_producer(spec, raw, error)) {
                error = "shader '" + uuid + "': " + error;
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            keepalive.shaders.push_back(std::move(shader));
            return true;
        }

        bool optional_bool_field(const nos::trent& object, const char* name, bool default_value) {
            const nos::trent* value = dict_get(object, name);
            return value && value->is_bool() ? value->as_bool() : default_value;
        }

        bool is_supported_shader_program_property_type(const std::string& property_type) {
            return property_type == "Bool" || property_type == "Int" || property_type == "Float" ||
                   property_type == "Vec2" || property_type == "Vec3" || property_type == "Vec4" ||
                   property_type == "SrgbColor" || property_type == "LinearColor" || property_type == "Mat4" ||
                   property_type == "Texture" || property_type == "Texture2D";
        }

        bool shader_program_property_default(const nos::trent& property,
                                             const std::string& property_type,
                                             tc_uniform_value& value,
                                             std::string& text,
                                             std::string& error) {
            const nos::trent* input = dict_get(property, "default");
            if (!input) {
                return true;
            }
            const bool is_texture = property_type == "Texture" || property_type == "Texture2D";
            if (is_texture && !input->is_string()) {
                error = "shader program texture property default must be a string";
                return false;
            }
            if (property_type == "Bool" && !input->is_bool()) {
                error = "shader program Bool property default must be boolean";
                return false;
            }
            if ((property_type == "Float" || property_type == "Int") && !input->is_numer()) {
                error = "shader program scalar property default must be numeric";
                return false;
            }
            const size_t expected_components =
                property_type == "Vec2"                                                                       ? 2u
                : property_type == "Vec3"                                                                     ? 3u
                : (property_type == "Vec4" || property_type == "SrgbColor" || property_type == "LinearColor") ? 4u
                : property_type == "Mat4"                                                                     ? 16u
                                                                                                              : 0u;
            if (expected_components != 0u && (!input->is_list() || input->as_list().size() != expected_components)) {
                error = "shader program property '" + property_type + "' default requires exactly " +
                        std::to_string(expected_components) + " components";
                return false;
            }
            if (input->is_string()) {
                text = input->as_string();
                return true;
            }
            if (input->is_bool()) {
                value.type = TC_UNIFORM_BOOL;
                value.data.i = input->as_bool() ? 1 : 0;
                return true;
            }
            if (input->is_numer()) {
                if (property_type == "Int") {
                    value.type = TC_UNIFORM_INT;
                    value.data.i = static_cast<int32_t>(input->as_numer());
                } else {
                    value.type = TC_UNIFORM_FLOAT;
                    value.data.f = static_cast<float>(input->as_numer());
                }
                return true;
            }
            if (input->is_list()) {
                const auto& elements = input->as_list();
                if (elements.size() != expected_components) {
                    error = "shader program property '" + property_type + "' default requires exactly " +
                            std::to_string(expected_components) + " components";
                    return false;
                }
                float components[16] = {};
                for (size_t index = 0; index < elements.size(); ++index) {
                    if (!elements[index].is_numer()) {
                        error = "shader program property vector default contains a non-number";
                        return false;
                    }
                    components[index] = static_cast<float>(elements[index].as_numer());
                }
                value.type = property_type == "Mat4" ? TC_UNIFORM_MAT4
                             : elements.size() == 2
                                 ? TC_UNIFORM_VEC2
                                 : (elements.size() == 3 ? TC_UNIFORM_VEC3
                                                         : (property_type == "SrgbColor"     ? TC_UNIFORM_SRGB_COLOR
                                                            : property_type == "LinearColor" ? TC_UNIFORM_LINEAR_COLOR
                                                                                             : TC_UNIFORM_VEC4));
                if (property_type == "SrgbColor") {
                    value.data.srgb_color = tc_srgb_color{components[0], components[1], components[2], components[3]};
                } else if (property_type == "LinearColor") {
                    value.data.linear_color =
                        tc_linear_color{components[0], components[1], components[2], components[3]};
                } else if (property_type == "Mat4") {
                    std::memcpy(value.data.m4, components, sizeof(components));
                } else {
                    std::memcpy(value.data.v4, components, elements.size() * sizeof(float));
                }
                return true;
            }
            error = "shader program property default has unsupported JSON type";
            return false;
        }

        bool load_shader_program_resource(const nos::trent& entry,
                                          const nos::trent& spec,
                                          RuntimePackageResourceKeepalive& keepalive,
                                          std::string& error) {
            if (uint32_field(spec, "schema_version", 0) != 1) {
                error = "shader program resource requires schema_version 1";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            const std::string uuid = string_field(spec, "uuid");
            if (uuid.empty() || uuid != string_field(entry, "uuid")) {
                error = "shader program resource manifest UUID does not match its payload";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            const std::string name = string_field(spec, "name");
            const std::string language = string_field(spec, "language");
            const nos::trent* property_list = dict_get(spec, "properties");
            const nos::trent* phase_list = dict_get(spec, "phases");
            if (name.empty() || language.empty() || !property_list || !property_list->is_list() || !phase_list ||
                !phase_list->is_list() || phase_list->as_list().empty()) {
                error = "shader program resource requires name, language, properties and phases";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            const size_t property_count = property_list->as_list().size();
            std::vector<std::string> property_names;
            std::vector<std::string> property_types;
            std::vector<std::string> property_labels;
            std::vector<std::string> property_default_texts(property_count);
            std::vector<tc_uniform_value> property_defaults(property_count);
            std::vector<tc_shader_program_property_desc> properties;
            property_names.reserve(property_count);
            property_types.reserve(property_count);
            property_labels.reserve(property_count);
            properties.reserve(property_count);
            for (size_t index = 0; index < property_count; ++index) {
                const nos::trent& item = property_list->as_list()[index];
                if (!item.is_dict()) {
                    error = "shader program property must be an object";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                property_names.push_back(string_field(item, "name"));
                property_types.push_back(string_field(item, "property_type"));
                property_labels.push_back(string_field(item, "label"));
                if (property_names.back().empty() || property_types.back().empty()) {
                    error = "shader program property requires name and property_type";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                if (property_types.back() == "Color") {
                    error = "shader program property '" + property_names.back() +
                            "' uses legacy property_type 'Color'; use 'SrgbColor' or 'LinearColor'";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                if (!is_supported_shader_program_property_type(property_types.back())) {
                    error = "shader program property '" + property_names.back() + "' has unsupported property_type '" +
                            property_types.back() + "'";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                tc_uniform_value& default_value = property_defaults[index];
                std::memset(&default_value, 0, sizeof(default_value));
                if (!shader_program_property_default(
                        item, property_types.back(), default_value, property_default_texts[index], error)) {
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                tc_shader_program_property_desc desc{};
                desc.name = property_names.back().c_str();
                desc.property_type = property_types.back().c_str();
                desc.label = property_labels.back().empty() ? nullptr : property_labels.back().c_str();
                const nos::trent* expected_encoding = dict_get(item, "expected_encoding");
                const bool is_texture = property_types.back() == "Texture" || property_types.back() == "Texture2D";
                if (is_texture && expected_encoding) {
                    if (!expected_encoding->is_string()) {
                        error = "shader program property expected_encoding must be 'srgb' or 'linear'";
                        tc_log_error("RuntimePackageLoader: %s", error.c_str());
                        return false;
                    }
                    const std::string encoding = expected_encoding->as_string();
                    if (encoding == "srgb") {
                        desc.expected_encoding = TC_TEXTURE_ENCODING_SRGB;
                    } else if (encoding == "linear") {
                        desc.expected_encoding = TC_TEXTURE_ENCODING_LINEAR;
                    } else {
                        error = "shader program property expected_encoding must be 'srgb' or 'linear'";
                        tc_log_error("RuntimePackageLoader: %s", error.c_str());
                        return false;
                    }
                    desc.has_expected_encoding = 1;
                } else if (expected_encoding) {
                    error = "shader program non-texture property must not have expected_encoding";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                desc.default_value = default_value.type == TC_UNIFORM_NONE ? nullptr : &default_value;
                desc.default_text =
                    property_default_texts[index].empty() ? nullptr : property_default_texts[index].c_str();
                const nos::trent* range_min = dict_get(item, "range_min");
                const nos::trent* range_max = dict_get(item, "range_max");
                if (range_min && range_min->is_numer()) {
                    desc.range_min = range_min->as_numer();
                    desc.has_range_min = 1;
                }
                if (range_max && range_max->is_numer()) {
                    desc.range_max = range_max->as_numer();
                    desc.has_range_max = 1;
                }
                properties.push_back(desc);
            }

            const size_t phase_count = phase_list->as_list().size();
            std::vector<std::string> phase_marks;
            std::vector<std::string> phase_shader_uuids;
            std::vector<tc_shader_program_phase_desc> phases;
            phase_marks.reserve(phase_count);
            phase_shader_uuids.reserve(phase_count);
            phases.reserve(phase_count);
            for (const nos::trent& item : phase_list->as_list()) {
                if (!item.is_dict()) {
                    error = "shader program phase must be an object";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                phase_marks.push_back(string_field(item, "phase_mark"));
                const std::string shader_uuid = string_field(item, "shader");
                char expected_uuid[TC_UUID_SIZE];
                tc_shader_program_make_phase_uuid(
                    expected_uuid, sizeof(expected_uuid), uuid.c_str(), phase_marks.back().c_str());
                if (phase_marks.back().empty() || shader_uuid != expected_uuid ||
                    !TcShader::from_uuid(shader_uuid).is_valid()) {
                    error = "shader program phase has missing or inconsistent phase shader identity";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                const nos::trent* state = dict_get(item, "state");
                if (!state || !state->is_dict()) {
                    error = "shader program phase requires render state";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                tc_render_state render_state{};
                render_state.polygon_mode = static_cast<uint8_t>(uint32_field(*state, "polygon_mode", 0));
                render_state.cull = optional_bool_field(*state, "cull", true);
                render_state.depth_test = optional_bool_field(*state, "depth_test", true);
                render_state.depth_write = optional_bool_field(*state, "depth_write", true);
                render_state.blend = optional_bool_field(*state, "blend", false);
                render_state.blend_src = static_cast<uint8_t>(uint32_field(*state, "blend_src", 0));
                render_state.blend_dst = static_cast<uint8_t>(uint32_field(*state, "blend_dst", 0));
                render_state.depth_func = static_cast<uint8_t>(uint32_field(*state, "depth_func", 0));
                tc_shader_program_phase_desc desc{};
                desc.phase_mark = phase_marks.back().c_str();
                desc.priority = static_cast<int32_t>(number_field(item, "priority", 0));
                desc.state = render_state;
                phases.push_back(desc);
                phase_shader_uuids.push_back(shader_uuid);
            }

            TcShaderProgram program = TcShaderProgram::declare(uuid, name);
            tc_shader_program_payload_desc payload{};
            const std::string source_path = string_field(spec, "source_path");
            payload.name = name.c_str();
            payload.source_path = source_path.c_str();
            payload.language = language.c_str();
            payload.features = uint32_field(spec, "features", 0);
            payload.properties = properties.data();
            payload.property_count = static_cast<uint32_t>(properties.size());
            payload.phases = phases.data();
            payload.phase_count = static_cast<uint32_t>(phases.size());
            if (!program.is_valid() || !tc_shader_program_set_payload(program.get(), &payload)) {
                error = "failed to publish shader program '" + uuid + "'";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            const std::vector<std::pair<std::string, std::string>> shader_property_types = [&]() {
                std::vector<std::pair<std::string, std::string>> result;
                result.reserve(property_count);
                for (size_t index = 0; index < property_count; ++index) {
                    result.emplace_back(property_names[index], property_types[index]);
                }
                return result;
            }();
            for (const std::string& phase_shader_uuid : phase_shader_uuids) {
                TcShader phase_shader = TcShader::from_uuid(phase_shader_uuid);
                if (phase_shader.is_valid()) {
                    if (!detail::set_shader_material_ubo_property_types(
                            phase_shader.get(), shader_property_types, error)) {
                        error = "shader program '" + uuid + "': " + error;
                        tc_log_error("RuntimePackageLoader: %s", error.c_str());
                        return false;
                    }
                }
            }
            keepalive.shader_programs.push_back(std::move(program));
            return true;
        }

        bool
        load_material_resource(const nos::trent& spec, RuntimePackageResourceKeepalive& keepalive, std::string& error) {
            const std::string uuid = string_field(spec, "uuid");
            const std::string name = string_field(spec, "name", uuid);
            if (uuid.empty() || name.empty()) {
                error = "material resource requires uuid and name";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            TcMaterial material = TcMaterial::get_or_create(uuid, name);
            if (!material.is_valid()) {
                error = "failed to create material '" + uuid + "'";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            const std::string program_uuid = string_field(spec, "shader_program");
            TcShaderProgram program;
            if (!program_uuid.empty()) {
                program = TcShaderProgram::find(program_uuid);
                if (!program.is_valid()) {
                    error = "material '" + uuid + "' references missing shader program '" + program_uuid + "'";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                material.set_shader_program_dependency(program_uuid.c_str(), program.version());
            }

            material.clear_phases();
            const nos::trent* phases = dict_get(spec, "phases");
            if (!phases || !phases->is_list()) {
                error = "material '" + uuid + "' has no phases list";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            for (const nos::trent& phase_spec : phases->as_list()) {
                const std::string shader_uuid = string_field(phase_spec, "shader");
                if (shader_uuid.empty()) {
                    error = "material '" + uuid + "' phase has no shader";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                TcShader shader = TcShader::from_uuid(shader_uuid);
                if (!shader.is_valid()) {
                    error = "material '" + uuid + "' references missing shader '" + shader_uuid + "'";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                const std::string mark = string_field(phase_spec, "mark", "opaque");
                const int priority = static_cast<int>(number_field(phase_spec, "priority", 0.0));
                if (!material.add_phase(shader, mark.c_str(), priority)) {
                    error = "failed to add phase '" + mark + "' to material '" + uuid + "'";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
            }

            if (program.is_valid() && !configure_material_texture_slots(material, program, uuid, error)) {
                return false;
            }
            if (!apply_material_uniforms(material, dict_get(spec, "uniforms"), program, uuid, error)) {
                return false;
            }
            if (!apply_material_textures(material, dict_get(spec, "textures"), uuid, error)) {
                return false;
            }

            keepalive.materials.push_back(std::move(material));
            return true;
        }

        bool required_bool_field(const nos::trent& object,
                                 const char* field_name,
                                 bool& value,
                                 std::string& error,
                                 const std::string& context) {
            const nos::trent* field = dict_get(object, field_name);
            if (!field || !field->is_bool()) {
                error = context + " field '" + field_name + "' must be boolean";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            value = field->as_bool();
            return true;
        }

        bool required_string_field(const nos::trent& object,
                                   const char* field_name,
                                   std::string& value,
                                   std::string& error,
                                   const std::string& context) {
            const nos::trent* field = dict_get(object, field_name);
            if (!field || !field->is_string()) {
                error = context + " field '" + field_name + "' must be a string";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            value = field->as_string();
            return true;
        }

        bool load_texture_resource(const RuntimePackageReader& reader,
                                   const nos::trent& entry,
                                   const std::string& spec_path,
                                   const nos::trent& spec,
                                   RuntimePackageResourceKeepalive& keepalive,
                                   std::string& error) {
            if (!spec.is_dict()) {
                error = "texture spec must be an object";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            const std::string uuid = string_field(spec, "uuid");
            const std::string name = string_field(spec, "name");
            const std::string source_rel_path = string_field(spec, "source_path");
            if (uuid.empty() || name.empty() || source_rel_path.empty()) {
                error = "texture resource requires uuid, name and source_path";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            const std::string manifest_uuid = string_field(entry, "uuid");
            if (manifest_uuid.empty() || manifest_uuid != uuid) {
                error = "texture resource manifest uuid does not match spec uuid '" + uuid + "'";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            const nos::trent* import_settings = dict_get(spec, "import_settings");
            if (!import_settings || !import_settings->is_dict()) {
                error = "texture '" + uuid + "' import_settings must be an object";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            TextureTransformFlags transform;
            const std::string settings_context = "texture '" + uuid + "' import_settings";
            if (!required_bool_field(*import_settings, "flip_x", transform.flip_x, error, settings_context) ||
                !required_bool_field(*import_settings, "flip_y", transform.flip_y, error, settings_context) ||
                !required_bool_field(*import_settings, "transpose", transform.transpose, error, settings_context)) {
                return false;
            }
            std::string encoding_name;
            if (!required_string_field(*import_settings, "encoding", encoding_name, error, settings_context)) {
                return false;
            }
            tgfx::TextureEncoding encoding;
            if (encoding_name == "srgb") {
                encoding = tgfx::TextureEncoding::SRGB;
            } else if (encoding_name == "linear") {
                encoding = tgfx::TextureEncoding::Linear;
            } else {
                error = settings_context + " field 'encoding' must be 'srgb' or 'linear'";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            try {
                if (!reader.contains(source_rel_path)) {
                    error = "texture '" + uuid + "' source file not found: " + reader.describe(source_rel_path);
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                const RuntimePackageBytes encoded = read_binary_file(reader, source_rel_path);
                const std::string source_path = reader.describe(source_rel_path);
                const image::DecodedImage decoded = image::decode_rgba8(encoded.view(), source_path);
                if (decoded.width <= 0 || decoded.height <= 0 || decoded.channels != 4) {
                    error = "texture '" + uuid + "' decoder returned an invalid RGBA8 image";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }

                TcTexture texture = TcTexture::from_data(TcTextureCreateInfo{
                    TexturePixelDataView{
                        decoded.pixels.data(),
                        static_cast<std::uint32_t>(decoded.width),
                        static_cast<std::uint32_t>(decoded.height),
                        static_cast<std::uint8_t>(decoded.channels),
                    },
                    transform,
                    name,
                    source_path,
                    uuid,
                    encoding,
                });
                if (!texture.is_valid()) {
                    error = "failed to create texture '" + uuid + "' from " + reader.describe(spec_path);
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                keepalive.textures.push_back(std::move(texture));
                return true;
            } catch (const std::exception& ex) {
                error = "failed to load texture '" + uuid + "': " + ex.what();
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
        }

        tc_draw_mode parse_draw_mode(const std::string& value) {
            if (value == "lines") {
                return TC_DRAW_LINES;
            }
            return TC_DRAW_TRIANGLES;
        }

        bool parse_mesh_submeshes(const nos::trent* submesh_spec,
                                  size_t index_count,
                                  tc_draw_mode default_draw_mode,
                                  std::vector<tc_submesh>& submeshes,
                                  std::string& error,
                                  const std::string& uuid) {
            if (!submesh_spec) {
                return true;
            }
            if (!submesh_spec->is_list()) {
                error = "mesh '" + uuid + "' submeshes must be a list";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            for (const nos::trent& item : submesh_spec->as_list()) {
                if (!item.is_dict()) {
                    error = "mesh '" + uuid + "' has invalid submesh entry";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                tc_submesh submesh{};
                submesh.first_index = static_cast<uint32_t>(number_field(item, "first_index", 0.0));
                submesh.index_count = static_cast<uint32_t>(number_field(item, "index_count", 0.0));
                submesh.vertex_offset = static_cast<int32_t>(number_field(item, "vertex_offset", 0.0));
                submesh.material_slot = static_cast<uint32_t>(number_field(item, "material_slot", 0.0));
                submesh.draw_mode = static_cast<uint8_t>(parse_draw_mode(
                    string_field(item, "draw_mode", default_draw_mode == TC_DRAW_LINES ? "lines" : "triangles")));
                const std::string name = string_field(item, "name");
                if (!name.empty()) {
                    std::snprintf(submesh.name, sizeof(submesh.name), "%s", name.c_str());
                }
                if (submesh.index_count == 0 || static_cast<size_t>(submesh.first_index) > index_count ||
                    static_cast<size_t>(submesh.index_count) > index_count - static_cast<size_t>(submesh.first_index)) {
                    error = "mesh '" + uuid + "' has invalid submesh range";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                submeshes.push_back(submesh);
            }
            return true;
        }

        bool
        load_mesh_resource(const nos::trent& spec, RuntimePackageResourceKeepalive& keepalive, std::string& error) {
            const std::string uuid = string_field(spec, "uuid");
            const std::string name = string_field(spec, "name", uuid);
            if (uuid.empty() || name.empty()) {
                error = "mesh resource requires uuid and name";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            const nos::trent* layout_spec = dict_get(spec, "layout");
            const nos::trent* vertex_spec = dict_get(spec, "vertices");
            const nos::trent* index_spec = dict_get(spec, "indices");
            if (!layout_spec || !layout_spec->is_list() || !vertex_spec || !vertex_spec->is_list() || !index_spec ||
                !index_spec->is_list()) {
                error = "mesh '" + uuid + "' requires layout, vertices and indices";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            tc_vertex_layout layout;
            tc_vertex_layout_init(&layout);
            size_t floats_per_vertex = 0;
            for (const nos::trent& attrib : layout_spec->as_list()) {
                const std::string attr_name = string_field(attrib, "name");
                const std::string attr_type = string_field(attrib, "type", "float32");
                const int components = static_cast<int>(number_field(attrib, "components", 0.0));
                const int location = static_cast<int>(number_field(attrib, "location", 0.0));
                if (attr_name.empty() || attr_type != "float32" || components <= 0) {
                    error = "mesh '" + uuid + "' has unsupported vertex layout";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                tc_vertex_layout_add(
                    &layout, attr_name.c_str(), components, TC_ATTRIB_FLOAT32, static_cast<uint8_t>(location));
                floats_per_vertex += static_cast<size_t>(components);
            }
            if (floats_per_vertex == 0) {
                error = "mesh '" + uuid + "' has empty vertex layout";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            std::vector<float> vertices;
            vertices.reserve(vertex_spec->as_list().size());
            for (const nos::trent& v : vertex_spec->as_list()) {
                if (!v.is_numer()) {
                    error = "mesh '" + uuid + "' has non-numeric vertex data";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                vertices.push_back(static_cast<float>(v.as_numer()));
            }
            if (vertices.size() % floats_per_vertex != 0) {
                error = "mesh '" + uuid + "' vertex data does not match layout";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            std::vector<uint32_t> indices;
            indices.reserve(index_spec->as_list().size());
            for (const nos::trent& idx : index_spec->as_list()) {
                if (!idx.is_numer() || idx.as_numer() < 0) {
                    error = "mesh '" + uuid + "' has invalid index data";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                indices.push_back(static_cast<uint32_t>(idx.as_numer()));
            }
            if (indices.empty()) {
                error = "mesh '" + uuid + "' has no indices";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            const size_t vertex_count = vertices.size() / floats_per_vertex;
            tc_draw_mode draw_mode = parse_draw_mode(string_field(spec, "draw_mode", "triangles"));
            std::vector<tc_submesh> submeshes;
            if (!parse_mesh_submeshes(dict_get(spec, "submeshes"), indices.size(), draw_mode, submeshes, error, uuid)) {
                return false;
            }

            TcMeshCreateInfo create_info;
            create_info.data =
                TcMeshInterleavedDataView{vertices.data(), vertex_count, indices.data(), indices.size(), &layout};
            if (!submeshes.empty()) {
                create_info.submeshes = submeshes.data();
                create_info.submesh_count = submeshes.size();
            }
            create_info.name = name;
            create_info.uuid_hint = uuid;
            create_info.draw_mode = draw_mode;
            TcMesh mesh = TcMesh::from_interleaved(create_info);
            if (!mesh.is_valid()) {
                error = "failed to create mesh '" + uuid + "'";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            keepalive.meshes.push_back(std::move(mesh));
            return true;
        }

#ifndef TERMIN_RUNTIME_RENDER_ONLY
        bool load_foliage_data_resource(const RuntimePackageReader& reader,
                                        const nos::trent& entry,
                                        RuntimePackageResourceKeepalive& keepalive,
                                        std::string& error) {
            const std::string uuid = string_field(entry, "uuid");
            const std::string rel_path = string_field(entry, "path");
            const std::string name = string_field(entry, "name", uuid);
            if (uuid.empty() || rel_path.empty()) {
                error = "foliage_data resource requires uuid and path";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            const std::string asset_path = reader.materialized_path(rel_path);
            if (asset_path.empty()) {
                error = "foliage_data resource requires a materialized package provider";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            TcFoliageData foliage = TcFoliageData::declare(uuid, name, asset_path);
            if (!foliage.is_valid()) {
                error = "failed to declare foliage asset '" + uuid + "'";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            if (!foliage.ensure_loaded()) {
                error = "failed to load foliage asset '" + uuid + "'";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            keepalive.foliage_data.push_back(std::move(foliage));
            return true;
        }
#endif

#ifndef TERMIN_RUNTIME_RENDER_ONLY
        bool load_sprite_asset_resource(const nos::trent& entry,
                                        const nos::trent& spec,
                                        RuntimePackageResourceKeepalive& keepalive,
                                        std::string& error) {
            const std::string uuid = string_field(spec, "uuid", string_field(entry, "uuid"));
            const std::string name = string_field(spec, "name", string_field(entry, "name", uuid));
            const nos::trent* texture = dict_get(spec, "texture");
            std::string texture_uuid;
            if (texture && texture->is_string()) {
                texture_uuid = texture->as_string();
            } else if (texture && texture->is_dict()) {
                texture_uuid = string_field(*texture, "uuid");
            }
            const nos::trent* region_value = dict_get(spec, "region");
            const nos::trent* source_size_value = dict_get(spec, "source_size");
            if (uuid.empty() || texture_uuid.empty() || !region_value || !region_value->is_list() ||
                !source_size_value || !source_size_value->is_list() || region_value->as_list().size() != 4 ||
                source_size_value->as_list().size() != 2) {
                error = "sprite_asset requires uuid, texture, region[4], and source_size[2]";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            const auto& region_list = region_value->as_list();
            const auto& size_list = source_size_value->as_list();
            for (const nos::trent& value : region_list) {
                if (!value.is_numer()) {
                    error = "sprite_asset region values must be numbers";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
            }
            for (const nos::trent& value : size_list) {
                if (!value.is_numer()) {
                    error = "sprite_asset source_size values must be numbers";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
            }
            float pivot_x = 0.5f;
            float pivot_y = 0.5f;
            const nos::trent* pivot = dict_get(spec, "pivot");
            if (pivot && pivot->is_list() && pivot->as_list().size() == 2 && pivot->as_list()[0].is_numer() &&
                pivot->as_list()[1].is_numer()) {
                pivot_x = static_cast<float>(pivot->as_list()[0].as_numer());
                pivot_y = static_cast<float>(pivot->as_list()[1].as_numer());
            }
            const std::string sampling_name = lowercase_copy(string_field(spec, "sampling", "linear"));
            if (sampling_name != "linear" && sampling_name != "nearest") {
                error = "sprite_asset sampling must be 'linear' or 'nearest'";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            if (!TcTexture::from_uuid(texture_uuid).is_valid()) {
                error = "sprite_asset '" + uuid + "' references missing texture '" + texture_uuid + "'";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            TcSpriteAsset sprite = TcSpriteAsset::declare(uuid, name);
            if (!sprite.update(texture_uuid,
                               SpriteRegion{
                                   static_cast<int32_t>(region_list[0].as_numer()),
                                   static_cast<int32_t>(region_list[1].as_numer()),
                                   static_cast<int32_t>(region_list[2].as_numer()),
                                   static_cast<int32_t>(region_list[3].as_numer()),
                               },
                               static_cast<int32_t>(size_list[0].as_numer()),
                               static_cast<int32_t>(size_list[1].as_numer()),
                               pivot_x,
                               pivot_y,
                               static_cast<float>(number_field(spec, "pixels_per_unit", 100.0)),
                               sampling_name == "nearest" ? SpriteSampling::Nearest : SpriteSampling::Linear)) {
                error = "failed to initialize sprite_asset '" + uuid + "'";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            keepalive.sprites.push_back(std::move(sprite));
            return true;
        }
#endif

        bool load_pipeline_resource(const RuntimePackageReader& reader,
                                    const nos::trent& entry,
                                    RuntimePackageResourceKeepalive& keepalive,
                                    std::string& error) {
            const std::string uuid = string_field(entry, "uuid");
            const std::string rel_path = string_field(entry, "path");
            if (uuid.empty() || rel_path.empty()) {
                error = "pipeline resource requires uuid and path";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            const RuntimePackageBytes payload = read_binary_file(reader, rel_path);
            if (payload.size == 0) {
                error = "pipeline template descriptor is empty for '" + uuid + "'";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            const tc_pipeline_template_handle handle =
                tc_pipeline_template_deserialize(uuid.c_str(), payload.data, payload.size);
            if (tc_pipeline_template_handle_is_invalid(handle)) {
                error = "failed to deserialize pipeline template '" + uuid + "'";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            TcPipelineTemplate pipeline_template(handle);
            const tc_pipeline_template* definition = pipeline_template.get();
            for (uint32_t index = 0; definition && index < definition->pass_count; ++index) {
                const char* type_name = definition->passes[index].type_name;
                if (!type_name || !tc_pass_registry_has(type_name)) {
                    error = "pipeline template '" + uuid + "' uses unsupported pass contract '" +
                            (type_name ? type_name : "<missing>") + "'";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
            }
            try {
                RenderPipeline validation_instance(pipeline_template);
                validation_instance.destroy();
            } catch (const std::exception& ex) {
                error = "pipeline template '" + uuid + "' cannot be instantiated: " + ex.what();
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }
            keepalive.pipeline_templates.push_back(std::move(pipeline_template));
            return true;
        }

        bool load_resource(const RuntimePackageReader& reader,
                           const nos::trent& entry,
                           RuntimePackageResourceKeepalive& keepalive,
                           std::string& error) {
            const std::string type = string_field(entry, "type");
            const std::string rel_path = string_field(entry, "path");
            if (type.empty() || rel_path.empty()) {
                error = "resource entry requires type and path";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
            }

            if (type == "pipeline") {
                return load_pipeline_resource(reader, entry, keepalive, error);
            }
            if (type == "foliage_data") {
#ifdef TERMIN_RUNTIME_RENDER_ONLY
                error = "render runtime profile does not support foliage_data resources";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
#else
                return load_foliage_data_resource(reader, entry, keepalive, error);
#endif
            }

            const std::string spec_path = rel_path;
            const std::string spec_text = read_text_file(reader, spec_path);
            const nos::trent spec = nos::json::parse(spec_text);
            if (type == "shader") {
                return load_shader_resource(reader, spec_path, spec, keepalive, error);
            }
            if (type == "shader_program") {
                return load_shader_program_resource(entry, spec, keepalive, error);
            }
            if (type == "material") {
                return load_material_resource(spec, keepalive, error);
            }
            if (type == "texture") {
                return load_texture_resource(reader, entry, spec_path, spec, keepalive, error);
            }
            if (type == "mesh") {
                return load_mesh_resource(spec, keepalive, error);
            }
            if (type == "sprite_asset") {
#ifdef TERMIN_RUNTIME_RENDER_ONLY
                error = "render runtime profile does not support sprite_asset resources";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
#else
                return load_sprite_asset_resource(entry, spec, keepalive, error);
#endif
            }
            if (type == "ui_document") {
#ifdef TERMIN_RUNTIME_RENDER_ONLY
                error = "render runtime profile does not support ui_document resources";
                tc_log_error("RuntimePackageLoader: %s", error.c_str());
                return false;
#else
                const std::string uuid = string_field(entry, "uuid");
                if (uuid.empty()) {
                    error = "ui_document resource requires a UUID";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                gui_native::TcUiDocumentAsset asset =
                    gui_native::TcUiDocumentAsset::declare_compiled_json(spec_text, uuid);
                if (!asset.valid()) {
                    error = "failed to register native UI document '" + uuid + "'";
                    tc_log_error("RuntimePackageLoader: %s", error.c_str());
                    return false;
                }
                keepalive.ui_documents.push_back(asset);
                return true;
#endif
            }

            error = "unsupported resource type '" + type + "'";
            tc_log_error("RuntimePackageLoader: %s", error.c_str());
            return false;
        }

        std::string resource_label(const nos::trent& entry) {
            const std::string type = string_field(entry, "type", "<missing-type>");
            const std::string path = string_field(entry, "path", "<missing-path>");
            return type + ":" + path;
        }

        void validate_minimal_entity_types(const nos::trent& entity, const std::string& scene_path) {
            const nos::trent* components = dict_get(entity, "components");
            if (components && components->is_list()) {
                for (const nos::trent& component : components->as_list()) {
                    const std::string type = string_field(component, "type");
                    if (!type.empty() && !tc_component_registry_has(type.c_str())) {
                        throw std::runtime_error("minimal runtime profile does not register component type '" + type +
                                                 "' required by packaged scene '" + scene_path + "'");
                    }
                }
            }
            const nos::trent* children = dict_get(entity, "children");
            if (children && children->is_list()) {
                for (const nos::trent& child : children->as_list()) {
                    validate_minimal_entity_types(child, scene_path);
                }
            }
        }

        void validate_minimal_scene(const nos::trent& scene, const std::string& scene_path) {
            const nos::trent* extensions = dict_get(scene, "extensions");
            if (extensions && extensions->is_dict() && !extensions->as_dict().empty()) {
                throw std::runtime_error("minimal runtime profile does not register scene extensions required by '" +
                                         scene_path + "'");
            }
            const nos::trent* entities = dict_get(scene, "entities");
            if (!entities || !entities->is_list()) {
                return;
            }
            for (const nos::trent& entity : entities->as_list()) {
                validate_minimal_entity_types(entity, scene_path);
            }
        }

        TcSceneRef load_runtime_scene(const RuntimePackageReader& reader,
                                      const std::string& rel_path,
                                      const RuntimePackageLoadOptions& options) {
            const std::string scene_json = read_text_file(reader, rel_path);
            nos::trent scene_data;
            try {
                scene_data = nos::json::parse(scene_json);
            } catch (const std::exception& ex) {
                throw std::runtime_error("failed to parse packaged runtime scene '" + rel_path + "': " + ex.what());
            }
            if (options.bootstrap_profile == bootstrap::RuntimeBootstrapProfile::Minimal) {
                validate_minimal_scene(scene_data, rel_path);
            }
            TcSceneRef scene = TcSceneRef::create("runtime-scene");
            if (!scene.valid()) {
                throw std::runtime_error("failed to create runtime scene");
            }
            try {
                for (tc_scene_ext_type_id type_id : options.scene_extensions) {
                    if (tc_scene_ext_has(scene.handle(), type_id)) {
                        continue;
                    }
                    if (!tc_scene_ext_attach(scene.handle(), type_id)) {
                        const char* debug_name = tc_scene_ext_type_debug_name(type_id);
                        throw std::runtime_error("failed to attach required scene extension '" +
                                                 std::string(debug_name ? debug_name : "<unregistered>") + "' (" +
                                                 std::to_string(type_id) + ") to packaged scene '" + rel_path + "'");
                    }
                }
                scene.set_source_path(reader.describe(rel_path));
                scene.load_from_data(scene_data);
            } catch (...) {
                scene.destroy();
                throw;
            }
            return scene;
        }

    } // namespace

    TcSceneRef RuntimePackageLoadResult::find_scene(const std::string& identity) const {
        for (const RuntimePackageScene& packaged_scene : scenes) {
            if (packaged_scene.identity == identity) {
                return packaged_scene.scene;
            }
        }
        return TcSceneRef();
    }

    void RuntimePackageLoadResult::destroy() {
        for (RuntimePackageScene& packaged_scene : scenes) {
            if (packaged_scene.scene.valid()) {
                packaged_scene.scene.destroy();
            }
        }
        scenes.clear();
        scene = TcSceneRef();
        world_controller.reset();
        resources.reset();
        ok = false;
    }

    RuntimePackageLoadResult RuntimePackageLoader::load(std::shared_ptr<RuntimePackageReader> reader,
                                                        const RuntimePackageLoadOptions& options) {
        RuntimePackageLoadResult result;
        try {
            if (!reader)
                throw std::runtime_error("runtime package reader is null");
            termin::bootstrap::bootstrap_runtime(options.bootstrap_profile);
            if (!reader->contains("manifest.json")) {
                result.message = "manifest.json not found in " + reader->describe("manifest.json");
                tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
                return result;
            }

            const nos::trent manifest = nos::json::parse(read_text_file(*reader, "manifest.json"));
            if (number_field(manifest, "version", 0.0) !=
                static_cast<double>(RUNTIME_PACKAGE_SCHEMA_VERSION)) {
                result.message = "runtime package manifest requires version " +
                                 std::to_string(RUNTIME_PACKAGE_SCHEMA_VERSION);
                tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
                return result;
            }
            result.world_controller = detail::parse_world_controller_selection(manifest);
            const nos::trent* artifact_root_field = dict_get(manifest, "shader_artifact_root");
            std::string shader_root;
            if (artifact_root_field) {
                if (!artifact_root_field->is_string() || artifact_root_field->as_string().empty()) {
                    result.message = "shader_artifact_root must be a non-empty relative path when provided";
                    tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
                    return result;
                }
                shader_root = artifact_root_field->as_string();
                reader->describe(shader_root + "/.path-check");
            }
            const std::string materialized_manifest = reader->materialized_path("manifest.json");
            if (!materialized_manifest.empty()) {
                std::filesystem::path materialized_root = std::filesystem::path(materialized_manifest).parent_path();
                if (!shader_root.empty())
                    materialized_root /= shader_root;
                result.shader_runtime.artifact_root = materialized_root.string();
                result.shader_runtime.cache_root =
                    (std::filesystem::path(materialized_manifest).parent_path() / ".shader-cache").string();
            } else {
                result.shader_runtime.artifact_root = shader_root;
                result.shader_runtime.resource_provider = reader;
            }
            const nos::trent* builtin_contract = dict_get(manifest, "builtin_shader_contract");
            if (builtin_contract) {
                if (!builtin_contract->is_dict()) {
                    result.message = "builtin_shader_contract must be an object when provided";
                    tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
                    return result;
                }
                if (number_field(*builtin_contract, "version", 0.0) != 1.0) {
                    result.message = "builtin_shader_contract requires version 1";
                    tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
                    return result;
                }
                const std::string catalog_path = string_field(*builtin_contract, "catalog");
                if (catalog_path.empty()) {
                    result.message = "builtin_shader_contract.catalog must be a non-empty relative path";
                    tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
                    return result;
                }
                const nos::trent* builtin_shaders = dict_get(*builtin_contract, "shaders");
                if (!builtin_shaders || !builtin_shaders->is_list() || builtin_shaders->as_list().empty()) {
                    result.message = "builtin_shader_contract.shaders must be a non-empty list";
                    tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
                    return result;
                }
                if (!reader->contains(catalog_path)) {
                    result.message = "builtin shader catalog not found: " + reader->describe(catalog_path);
                    tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
                    return result;
                }
                const std::string materialized_catalog = reader->materialized_path(catalog_path);
                result.shader_runtime.builtin_shader_root =
                    materialized_catalog.empty() ? std::filesystem::path(catalog_path).parent_path().generic_string()
                                                 : std::filesystem::path(materialized_catalog).parent_path().string();
            }
            result.shader_runtime.dev_compile_enabled = false;

            const nos::trent* resources = dict_get(manifest, "resources");
            if (!resources || !resources->is_list()) {
                result.message = "manifest resources must be a list";
                tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
                return result;
            }
            if (options.bootstrap_profile == bootstrap::RuntimeBootstrapProfile::Minimal &&
                !resources->as_list().empty()) {
                const std::string type = string_field(resources->as_list().front(), "type", "<missing>");
                result.message = "minimal runtime profile does not register resource type '" + type + "'";
                tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
                return result;
            }
            auto keepalive = std::make_shared<RuntimePackageResourceKeepalive>();
            keepalive->reader = reader;
            if (options.bootstrap_profile != bootstrap::RuntimeBootstrapProfile::Minimal) {
                ensure_runtime_builtin_textures();
            }
            constexpr std::array<const char*, 9> resource_order = {"shader",
                                                                   "shader_program",
                                                                   "mesh",
                                                                   "texture",
                                                                   "sprite_asset",
                                                                   "material",
                                                                   "pipeline",
                                                                   "foliage_data",
                                                                   "ui_document"};
            const auto& resource_list = resources->as_list();
            auto load_entry = [&](const nos::trent& resource) -> bool {
                std::string resource_error;
                if (load_resource(*reader, resource, *keepalive, resource_error)) {
                    return true;
                }
                result.message = "failed to load resource " + resource_label(resource);
                if (!resource_error.empty()) {
                    result.message += ": " + resource_error;
                }
                tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
                return false;
            };
            for (const char* ordered_type : resource_order) {
                for (const nos::trent& resource : resource_list) {
                    if (string_field(resource, "type") == ordered_type && !load_entry(resource)) {
                        return result;
                    }
                }
            }
            for (const nos::trent& resource : resource_list) {
                const std::string type = string_field(resource, "type");
                bool is_known = false;
                for (const char* ordered_type : resource_order) {
                    if (type == ordered_type) {
                        is_known = true;
                        break;
                    }
                }
                if (!is_known && !load_entry(resource)) {
                    return result;
                }
            }

            result.entry_scene_identity = string_field(manifest, "entry_scene");
            if (result.entry_scene_identity.empty()) {
                result.message = "manifest entry_scene identity is missing";
                tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
                return result;
            }
            const nos::trent* scenes = dict_get(manifest, "scenes");
            if (!scenes || !scenes->is_list() || scenes->as_list().empty()) {
                result.message = "manifest scenes must be a non-empty list";
                tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
                return result;
            }
            std::unordered_set<std::string> scene_identities;
            std::unordered_set<std::string> scene_paths;
            for (const nos::trent& entry : scenes->as_list()) {
                const std::string identity = string_field(entry, "identity");
                const std::string scene_path = string_field(entry, "path");
                if (identity.empty() || scene_path.empty()) {
                    throw std::runtime_error("runtime scene entries require non-empty identity and path");
                }
                validate_scene_identity(identity);
                if (!scene_identities.insert(identity).second) {
                    throw std::runtime_error("duplicate runtime scene identity '" + identity + "'");
                }
                if (!scene_paths.insert(scene_path).second) {
                    throw std::runtime_error("duplicate runtime scene path '" + scene_path + "'");
                }
                result.scenes.push_back(RuntimePackageScene{
                    identity,
                    scene_path,
                    load_runtime_scene(*reader, scene_path, options),
                });
            }
            result.scene = result.find_scene(result.entry_scene_identity);
            if (!result.scene.valid()) {
                throw std::runtime_error("entry scene '" + result.entry_scene_identity +
                                         "' is absent from manifest scenes");
            }
            result.ok = result.scene.valid();
            result.message = result.ok ? "ok" : "scene is invalid";
            if (result.ok) {
                result.resources = std::move(keepalive);
                tc_log_info("RuntimePackageLoader: loaded package '%s' entities=%zu",
                            reader->describe("manifest.json").c_str(),
                            result.scene.entity_count());
            }
        } catch (const std::exception& ex) {
            result.destroy();
            result.message = ex.what();
            tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
        }
        return result;
    }

    RuntimePackageLoadResult RuntimePackageLoader::load(const std::string& root_path,
                                                        const RuntimePackageLoadOptions& options) {
        RuntimePackageLoadResult result;
        try {
            return load(open_runtime_package_directory(root_path), options);
        } catch (const std::exception& ex) {
            result.message = ex.what();
            tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
            return result;
        }
    }

    RuntimePackageLoadResult load_runtime_package(const std::string& root_path,
                                                  const RuntimePackageLoadOptions& options) {
        RuntimePackageLoader loader;
        return loader.load(root_path, options);
    }

} // namespace termin::runtime
