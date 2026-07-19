#include <termin/runtime/runtime_package.hpp>

#include <cmath>
#include <cctype>
#include <cstdint>
#include <cstdio>
#include <filesystem>
#include <fstream>
#include <any>
#include <array>
#include <sstream>
#include <stdexcept>
#include <string>
#include <utility>
#include <vector>

#include <inspect/tc_kind_cpp.hpp>
#include <tcbase/tc_log.h>
#include <tcbase/trent/json.h>
#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>
#include <tgfx/tgfx_shader_handle.hpp>
#include <tgfx/tgfx_texture_handle.hpp>
#include <termin/bootstrap/bootstrap.hpp>
#include <termin/foliage/foliage_data_registry.hpp>
#include <termin/image/image_decode.hpp>

namespace termin::runtime {

struct RuntimePackageResourceKeepalive {
    std::vector<TcShader> shaders;
    std::vector<TcTexture> textures;
    std::vector<TcMaterial> materials;
    std::vector<TcMesh> meshes;
    std::vector<TcFoliageData> foliage_data;
};

namespace {

std::string read_text_file(const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary);
    if (!in) {
        throw std::runtime_error("failed to open file: " + path.string());
    }
    std::ostringstream out;
    out << in.rdbuf();
    if (!in.good() && !in.eof()) {
        throw std::runtime_error("failed to read file: " + path.string());
    }
    return out.str();
}

std::vector<std::uint8_t> read_binary_file(const std::filesystem::path& path) {
    std::ifstream in(path, std::ios::binary | std::ios::ate);
    if (!in) {
        throw std::runtime_error("failed to open file: " + path.string());
    }
    const std::streampos end = in.tellg();
    if (end < 0) {
        throw std::runtime_error("failed to determine file size: " + path.string());
    }
    std::vector<std::uint8_t> bytes(static_cast<std::size_t>(end));
    in.seekg(0, std::ios::beg);
    if (!bytes.empty()) {
        in.read(reinterpret_cast<char*>(bytes.data()), static_cast<std::streamsize>(bytes.size()));
    }
    if (!in) {
        throw std::runtime_error("failed to read file: " + path.string());
    }
    return bytes;
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

tc_shader_language shader_language_from_spec(const nos::trent& spec) {
    const std::string language = lowercase_copy(string_field(spec, "language", "glsl"));
    if (language == "slang") {
        return TC_SHADER_LANGUAGE_SLANG;
    }
    return TC_SHADER_LANGUAGE_GLSL;
}

struct RuntimeMaterialUboEntry {
    std::string name;
    std::string property_type;
    uint32_t offset = 0;
    uint32_t size = 0;
};

struct RuntimeMaterialUboLayout {
    std::vector<RuntimeMaterialUboEntry> entries;
    uint32_t block_size = 0;

    bool empty() const {
        return entries.empty();
    }
};

std::string trim_copy(const std::string& s) {
    size_t begin = 0;
    while (begin < s.size() && std::isspace(static_cast<unsigned char>(s[begin]))) {
        ++begin;
    }
    size_t end = s.size();
    while (end > begin && std::isspace(static_cast<unsigned char>(s[end - 1]))) {
        --end;
    }
    return s.substr(begin, end - begin);
}

std::string glsl_material_property_type(const std::string& glsl_type) {
    if (glsl_type == "float") {
        return "Float";
    }
    if (glsl_type == "int") {
        return "Int";
    }
    if (glsl_type == "bool") {
        return "Bool";
    }
    if (glsl_type == "vec2") {
        return "Vec2";
    }
    if (glsl_type == "vec3") {
        return "Vec3";
    }
    if (glsl_type == "vec4") {
        return "Vec4";
    }
    if (glsl_type == "mat4") {
        return "Mat4";
    }
    return "";
}

std::pair<uint32_t, uint32_t> runtime_std140_size_align(const std::string& property_type) {
    if (property_type == "Float" || property_type == "Int" || property_type == "Bool") {
        return {4u, 4u};
    }
    if (property_type == "Vec2") {
        return {8u, 8u};
    }
    if (property_type == "Vec3") {
        return {12u, 16u};
    }
    if (property_type == "Vec4") {
        return {16u, 16u};
    }
    if (property_type == "Mat4") {
        return {64u, 16u};
    }
    return {0u, 0u};
}

uint32_t runtime_round_up(uint32_t value, uint32_t align) {
    if (align == 0) {
        return value;
    }
    return (value + align - 1u) & ~(align - 1u);
}

RuntimeMaterialUboLayout compute_runtime_std140_layout(
    const std::vector<RuntimeMaterialUboEntry>& declarations
) {
    RuntimeMaterialUboLayout layout;
    uint32_t cursor = 0;
    for (const RuntimeMaterialUboEntry& decl : declarations) {
        auto [size, align] = runtime_std140_size_align(decl.property_type);
        if (size == 0) {
            continue;
        }
        cursor = runtime_round_up(cursor, align);
        RuntimeMaterialUboEntry entry = decl;
        entry.offset = cursor;
        entry.size = size;
        layout.entries.push_back(std::move(entry));
        cursor += size;
    }
    layout.block_size = runtime_round_up(cursor, 16u);
    return layout;
}

RuntimeMaterialUboLayout infer_material_ubo_layout_from_glsl(const std::string& source) {
    RuntimeMaterialUboLayout empty;
    const size_t uniform_pos = source.find("uniform MaterialParams");
    if (uniform_pos == std::string::npos) {
        return empty;
    }
    const size_t block_begin = source.find('{', uniform_pos);
    if (block_begin == std::string::npos) {
        return empty;
    }
    const size_t block_end = source.find('}', block_begin + 1);
    if (block_end == std::string::npos || block_end <= block_begin) {
        return empty;
    }

    std::vector<RuntimeMaterialUboEntry> declarations;
    std::istringstream lines(source.substr(block_begin + 1, block_end - block_begin - 1));
    std::string line;
    while (std::getline(lines, line)) {
        const size_t comment = line.find("//");
        if (comment != std::string::npos) {
            line.resize(comment);
        }
        line = trim_copy(line);
        if (line.empty() || line.back() != ';') {
            continue;
        }
        line.pop_back();
        line = trim_copy(line);
        std::istringstream decl(line);
        std::string glsl_type;
        std::string name;
        decl >> glsl_type >> name;
        if (glsl_type.empty() || name.empty()) {
            continue;
        }
        const size_t array_pos = name.find('[');
        if (array_pos != std::string::npos) {
            name.resize(array_pos);
        }
        std::string property_type = glsl_material_property_type(glsl_type);
        if (property_type.empty()) {
            continue;
        }
        RuntimeMaterialUboEntry entry;
        entry.name = std::move(name);
        entry.property_type = std::move(property_type);
        declarations.push_back(std::move(entry));
    }

    return compute_runtime_std140_layout(declarations);
}

void set_shader_material_ubo_layout_from_glsl(
    tc_shader* shader,
    const std::string& fragment_source
) {
    if (!shader) {
        return;
    }
    RuntimeMaterialUboLayout layout = infer_material_ubo_layout_from_glsl(fragment_source);
    if (layout.empty()) {
        return;
    }

    std::vector<tc_material_ubo_entry> entries;
    entries.reserve(layout.entries.size());
    for (const RuntimeMaterialUboEntry& src : layout.entries) {
        tc_material_ubo_entry dst{};
        std::snprintf(dst.name, sizeof(dst.name), "%s", src.name.c_str());
        std::snprintf(
            dst.property_type,
            sizeof(dst.property_type),
            "%s",
            src.property_type.c_str()
        );
        dst.offset = src.offset;
        dst.size = src.size;
        entries.push_back(dst);
    }
    tc_shader_set_material_ubo_layout(
        shader,
        entries.data(),
        static_cast<uint32_t>(entries.size()),
        layout.block_size
    );
    tc_log_info(
        "RuntimePackageLoader: inferred material UBO layout for shader '%s' entries=%zu size=%u",
        shader->name ? shader->name : shader->uuid,
        entries.size(),
        layout.block_size
    );
}

void set_shader_features_from_glsl(tc_shader* shader, const std::string& fragment_source) {
    if (!shader) {
        return;
    }
    if (fragment_source.find("uniform LightingBlock") != std::string::npos) {
        tc_shader_set_feature(shader, TC_SHADER_FEATURE_LIGHTING_UBO);
        tc_log_info(
            "RuntimePackageLoader: inferred lighting UBO feature for shader '%s'",
            shader->name ? shader->name : shader->uuid
        );
    }
}

bool is_contained_path(
    const std::filesystem::path& root,
    const std::filesystem::path& candidate
) {
    auto root_it = root.begin();
    auto candidate_it = candidate.begin();
    for (; root_it != root.end(); ++root_it, ++candidate_it) {
        if (candidate_it == candidate.end() || *root_it != *candidate_it) {
            return false;
        }
    }
    return true;
}

std::filesystem::path package_path(const std::filesystem::path& root, const std::string& rel) {
    if (rel.empty()) {
        throw std::runtime_error("runtime package path must not be empty");
    }
    // A package manifest uses portable '/' separators. Reject '\\' even on POSIX,
    // where it would otherwise be treated as part of a filename and make a package
    // behave differently after being moved to Windows.
    if (rel.find('\\') != std::string::npos) {
        throw std::runtime_error("runtime package path must not contain backslashes: " + rel);
    }

    const std::filesystem::path relative_path(rel);
    if (relative_path.is_absolute() || relative_path.has_root_name() || relative_path.has_root_directory()) {
        throw std::runtime_error("runtime package path must be relative: " + rel);
    }
    if (rel == "." || rel == "..") {
        throw std::runtime_error("runtime package path must not contain dot segments: " + rel);
    }
    for (const std::filesystem::path& component : relative_path) {
        if (component == "." || component == "..") {
            throw std::runtime_error("runtime package path must not contain dot segments: " + rel);
        }
    }

    std::error_code error;
    const std::filesystem::path candidate = std::filesystem::weakly_canonical(
        root / relative_path,
        error
    );
    if (error) {
        throw std::runtime_error(
            "failed to canonicalize runtime package path '" + rel + "': " + error.message()
        );
    }
    if (!is_contained_path(root, candidate)) {
        throw std::runtime_error("runtime package path escapes bundle root: " + rel);
    }
    return candidate;
}


std::vector<TcTexture>& runtime_builtin_texture_keepalive() {
    static std::vector<TcTexture> textures;
    return textures;
}

void ensure_runtime_builtin_textures() {
    auto& keepalive = runtime_builtin_texture_keepalive();
    if (!keepalive.empty()) {
        return;
    }

    // Match the editor's built-in texture UUIDs. They are content-hash UUIDs,
    // not the legacy "__white_1x1__" literal UUID used by TcTexture::white_1x1().
    const uint8_t white_pixel[4] = {255, 255, 255, 255};
    TcTexture white = TcTexture::from_data(TcTextureCreateInfo{
        TexturePixelDataView{white_pixel, 1, 1, 4},
        TextureTransformFlags{false, true, false},
        "__white_1x1__",
        "__white_1x1__",
        ""
    });
    if (white.is_valid()) {
        keepalive.push_back(std::move(white));
    } else {
        tc_log_error("RuntimePackageLoader: failed to create built-in white texture");
    }

    const uint8_t normal_pixel[4] = {128, 128, 255, 255};
    TcTexture normal = TcTexture::from_data(TcTextureCreateInfo{
        TexturePixelDataView{normal_pixel, 1, 1, 4},
        TextureTransformFlags{false, true, false},
        "__normal_1x1__",
        "__normal_1x1__",
        ""
    });
    if (normal.is_valid()) {
        keepalive.push_back(std::move(normal));
    } else {
        tc_log_error("RuntimePackageLoader: failed to create built-in normal texture");
    }
}

TcTexture runtime_builtin_texture(const std::string& name) {
    ensure_runtime_builtin_textures();
    const char* expected_name = nullptr;
    if (name == "white") {
        expected_name = "__white_1x1__";
    } else if (name == "normal") {
        expected_name = "__normal_1x1__";
    } else {
        return {};
    }

    for (const TcTexture& texture : runtime_builtin_texture_keepalive()) {
        if (texture.is_valid() && std::string(texture.name()) == expected_name) {
            return texture;
        }
    }
    return {};
}

TcTexture runtime_material_texture_from_spec(const nos::trent& spec, const std::string& material_uuid) {
    if (spec.is_string()) {
        const std::string uuid = spec.as_string();
        if (uuid.empty()) {
            return {};
        }
        TcTexture texture = TcTexture::from_uuid(uuid);
        if (!texture.is_valid()) {
            tc_log_error(
                "RuntimePackageLoader: material '%s' references missing texture asset '%s'",
                material_uuid.c_str(),
                uuid.c_str()
            );
        }
        return texture;
    }

    if (!spec.is_dict()) {
        tc_log_error(
            "RuntimePackageLoader: material '%s' texture spec must be an object or uuid string",
            material_uuid.c_str()
        );
        return {};
    }

    const std::string kind = string_field(spec, "kind");
    if (kind == "builtin") {
        const std::string name = string_field(spec, "name");
        TcTexture texture = runtime_builtin_texture(name);
        if (!texture.is_valid()) {
            tc_log_error(
                "RuntimePackageLoader: material '%s' references unknown builtin texture '%s'",
                material_uuid.c_str(),
                name.c_str()
            );
        }
        return texture;
    }

    if (kind == "asset") {
        const std::string uuid = string_field(spec, "uuid");
        if (uuid.empty()) {
            tc_log_error(
                "RuntimePackageLoader: material '%s' asset texture spec has no uuid",
                material_uuid.c_str()
            );
            return {};
        }
        TcTexture texture = TcTexture::from_uuid(uuid);
        if (!texture.is_valid()) {
            tc_log_error(
                "RuntimePackageLoader: material '%s' references missing texture asset '%s'",
                material_uuid.c_str(),
                uuid.c_str()
            );
        }
        return texture;
    }

    tc_log_error(
        "RuntimePackageLoader: material '%s' texture spec has unsupported kind '%s'",
        material_uuid.c_str(),
        kind.c_str()
    );
    return {};
}

void apply_material_uniforms(TcMaterial& material, const nos::trent* uniforms, const std::string& material_uuid) {
    if (!uniforms) {
        return;
    }
    if (!uniforms->is_dict()) {
        tc_log_error(
            "RuntimePackageLoader: material '%s' uniforms must be an object",
            material_uuid.c_str()
        );
        return;
    }

    for (const auto& item : uniforms->as_dict()) {
        const std::string& name = item.first;
        const nos::trent& value = item.second;
        if (name.empty()) {
            tc_log_error(
                "RuntimePackageLoader: material '%s' uniform name must not be empty",
                material_uuid.c_str()
            );
            continue;
        }
        if (value.is_bool()) {
            int v = value.as_bool() ? 1 : 0;
            material.set_uniform_int(name.c_str(), v);
            continue;
        }
        if (value.is_numer()) {
            material.set_uniform_float(name.c_str(), static_cast<float>(value.as_numer()));
            continue;
        }
        if (value.is_list()) {
            const auto& values = value.as_list();
            bool all_numbers = true;
            for (const nos::trent& element : values) {
                if (!element.is_numer()) {
                    all_numbers = false;
                    break;
                }
            }
            if (all_numbers && values.size() == 3) {
                material.set_uniform_vec3(
                    name.c_str(),
                    Vec3{
                        static_cast<float>(values[0].as_numer()),
                        static_cast<float>(values[1].as_numer()),
                        static_cast<float>(values[2].as_numer()),
                    }
                );
                continue;
            }
            if (all_numbers && values.size() == 4) {
                material.set_uniform_vec4(
                    name.c_str(),
                    Vec4{
                        static_cast<float>(values[0].as_numer()),
                        static_cast<float>(values[1].as_numer()),
                        static_cast<float>(values[2].as_numer()),
                        static_cast<float>(values[3].as_numer()),
                    }
                );
                continue;
            }
        }
        tc_log_error(
            "RuntimePackageLoader: material '%s' uniform '%s' has unsupported value",
            material_uuid.c_str(),
            name.c_str()
        );
    }
}

void apply_material_textures(TcMaterial& material, const nos::trent* textures, const std::string& material_uuid) {
    if (!textures) {
        return;
    }
    if (!textures->is_dict()) {
        tc_log_error(
            "RuntimePackageLoader: material '%s' textures must be an object",
            material_uuid.c_str()
        );
        return;
    }

    for (const auto& item : textures->as_dict()) {
        const std::string& name = item.first;
        if (name.empty()) {
            tc_log_error(
                "RuntimePackageLoader: material '%s' texture name must not be empty",
                material_uuid.c_str()
            );
            continue;
        }
        TcTexture texture = runtime_material_texture_from_spec(item.second, material_uuid);
        if (!texture.is_valid()) {
            continue;
        }
        material.set_texture(name.c_str(), texture);
    }
}

bool load_shader_resource(
    const std::filesystem::path& root,
    const std::filesystem::path& spec_path,
    const nos::trent& spec,
    RuntimePackageResourceKeepalive& keepalive,
    std::string& error
) {
    const std::string uuid = string_field(spec, "uuid");
    if (uuid.empty()) {
        error = "shader resource has no uuid";
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

    const std::string vertex_source = vertex_rel.empty()
        ? std::string()
        : read_text_file(package_path(root, vertex_rel));
    const std::string fragment_source = read_text_file(package_path(root, fragment_rel));
    const std::string geometry_rel = string_field(spec, "geometry_source_path");
    const std::string geometry_source = geometry_rel.empty()
        ? std::string()
        : read_text_file(package_path(root, geometry_rel));

    TcShader shader = TcShader::get_or_create(uuid);
    if (!shader.is_valid()) {
        error = "failed to create shader '" + uuid + "'";
        tc_log_error("RuntimePackageLoader: %s", error.c_str());
        return false;
    }

    const std::string name = string_field(spec, "name", uuid);
    const std::string source_path = spec_path.string();
    const std::string vertex_entry = string_field(spec, "vertex_entry");
    const std::string fragment_entry = string_field(spec, "fragment_entry");
    const std::string geometry_entry = string_field(spec, "geometry_entry");
    const tc_shader_language language = shader_language_from_spec(spec);
    shader.set_language(language);
    shader.set_artifact_policy(
        language == TC_SHADER_LANGUAGE_SLANG
            ? TC_SHADER_ARTIFACT_REQUIRED
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
    set_shader_features_from_glsl(raw, fragment_source);
    set_shader_material_ubo_layout_from_glsl(raw, fragment_source);
    keepalive.shaders.push_back(std::move(shader));
    return true;
}

bool load_material_resource(
    const nos::trent& spec,
    RuntimePackageResourceKeepalive& keepalive,
    std::string& error
) {
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

    apply_material_uniforms(material, dict_get(spec, "uniforms"), uuid);
    apply_material_textures(material, dict_get(spec, "textures"), uuid);

    keepalive.materials.push_back(std::move(material));
    return true;
}

bool required_bool_field(
    const nos::trent& object,
    const char* field_name,
    bool& value,
    std::string& error,
    const std::string& context
) {
    const nos::trent* field = dict_get(object, field_name);
    if (!field || !field->is_bool()) {
        error = context + " field '" + field_name + "' must be boolean";
        tc_log_error("RuntimePackageLoader: %s", error.c_str());
        return false;
    }
    value = field->as_bool();
    return true;
}

bool load_texture_resource(
    const std::filesystem::path& root,
    const nos::trent& entry,
    const std::filesystem::path& spec_path,
    const nos::trent& spec,
    RuntimePackageResourceKeepalive& keepalive,
    std::string& error
) {
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

    try {
        const std::filesystem::path source_path = package_path(root, source_rel_path);
        if (!std::filesystem::is_regular_file(source_path)) {
            error = "texture '" + uuid + "' source file not found: " + source_path.string();
            tc_log_error("RuntimePackageLoader: %s", error.c_str());
            return false;
        }
        const std::vector<std::uint8_t> encoded = read_binary_file(source_path);
        const image::DecodedImage decoded = image::decode_rgba8(encoded, source_path.string());
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
            source_path.string(),
            uuid,
        });
        if (!texture.is_valid()) {
            error = "failed to create texture '" + uuid + "' from " + spec_path.string();
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

bool parse_mesh_submeshes(
    const nos::trent* submesh_spec,
    size_t index_count,
    tc_draw_mode default_draw_mode,
    std::vector<tc_submesh>& submeshes,
    std::string& error,
    const std::string& uuid
) {
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
        submesh.draw_mode = static_cast<uint8_t>(
            parse_draw_mode(string_field(item, "draw_mode", default_draw_mode == TC_DRAW_LINES ? "lines" : "triangles")));
        const std::string name = string_field(item, "name");
        if (!name.empty()) {
            std::snprintf(submesh.name, sizeof(submesh.name), "%s", name.c_str());
        }
        if (submesh.index_count == 0 ||
            static_cast<size_t>(submesh.first_index) > index_count ||
            static_cast<size_t>(submesh.index_count) > index_count - static_cast<size_t>(submesh.first_index)) {
            error = "mesh '" + uuid + "' has invalid submesh range";
            tc_log_error("RuntimePackageLoader: %s", error.c_str());
            return false;
        }
        submeshes.push_back(submesh);
    }
    return true;
}

bool load_mesh_resource(
    const nos::trent& spec,
    RuntimePackageResourceKeepalive& keepalive,
    std::string& error
) {
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
    if (!layout_spec || !layout_spec->is_list() ||
        !vertex_spec || !vertex_spec->is_list() ||
        !index_spec || !index_spec->is_list()) {
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
        tc_vertex_layout_add(&layout, attr_name.c_str(), components, TC_ATTRIB_FLOAT32, static_cast<uint8_t>(location));
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
    create_info.data = TcMeshInterleavedDataView{
        vertices.data(),
        vertex_count,
        indices.data(),
        indices.size(),
        &layout};
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

bool load_foliage_data_resource(
    const std::filesystem::path& root,
    const nos::trent& entry,
    RuntimePackageResourceKeepalive& keepalive,
    std::string& error
) {
    const std::string uuid = string_field(entry, "uuid");
    const std::string rel_path = string_field(entry, "path");
    const std::string name = string_field(entry, "name", uuid);
    if (uuid.empty() || rel_path.empty()) {
        error = "foliage_data resource requires uuid and path";
        tc_log_error("RuntimePackageLoader: %s", error.c_str());
        return false;
    }

    const std::filesystem::path asset_path = package_path(root, rel_path);
    TcFoliageData foliage = TcFoliageData::declare(uuid, name, asset_path.string());
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

bool load_resource(
    const std::filesystem::path& root,
    const nos::trent& entry,
    RuntimePackageResourceKeepalive& keepalive,
    std::string& error
) {
    const std::string type = string_field(entry, "type");
    const std::string rel_path = string_field(entry, "path");
    if (type.empty() || rel_path.empty()) {
        error = "resource entry requires type and path";
        tc_log_error("RuntimePackageLoader: %s", error.c_str());
        return false;
    }

    if (type == "pipeline") {
        return true;
    }
    if (type == "foliage_data") {
        return load_foliage_data_resource(root, entry, keepalive, error);
    }

    const std::filesystem::path spec_path = package_path(root, rel_path);
    const nos::trent spec = nos::json::parse(read_text_file(spec_path));
    if (type == "shader") {
        return load_shader_resource(root, spec_path, spec, keepalive, error);
    }
    if (type == "material") {
        return load_material_resource(spec, keepalive, error);
    }
    if (type == "texture") {
        return load_texture_resource(root, entry, spec_path, spec, keepalive, error);
    }
    if (type == "mesh") {
        return load_mesh_resource(spec, keepalive, error);
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

TcSceneRef load_runtime_scene(const std::filesystem::path& root, const std::string& rel_path) {
    termin::bootstrap::bootstrap_runtime();

    const std::filesystem::path scene_path = package_path(root, rel_path);
    const std::string scene_json = read_text_file(scene_path);
    nos::trent scene_data;
    try {
        scene_data = nos::json::parse(scene_json);
    } catch (const std::exception& ex) {
        throw std::runtime_error(
            "failed to parse runtime entry scene '" + rel_path + "': " + ex.what()
        );
    }
    TcSceneRef scene = TcSceneRef::create("runtime-scene");
    if (!scene.valid()) {
        throw std::runtime_error("failed to create runtime scene");
    }
    scene.set_source_path(scene_path.string());
    scene.load_from_data(scene_data);
    return scene;
}

} // namespace

RuntimePackageLoadResult RuntimePackageLoader::load(const std::string& root_path) {
    RuntimePackageLoadResult result;
    try {
        std::error_code root_error;
        const std::filesystem::path root = std::filesystem::canonical(root_path, root_error);
        if (root_error || !std::filesystem::is_directory(root)) {
            result.message = "runtime package root is not a directory: " + root_path;
            tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
            return result;
        }
        const std::filesystem::path manifest_path = package_path(root, "manifest.json");
        if (!std::filesystem::is_regular_file(manifest_path)) {
            result.message = "manifest.json not found in " + root.string();
            tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
            return result;
        }

        const nos::trent manifest = nos::json::parse(read_text_file(manifest_path));
        const nos::trent* artifact_root_field = dict_get(manifest, "shader_artifact_root");
        std::filesystem::path shader_root = root;
        if (artifact_root_field) {
            if (!artifact_root_field->is_string() || artifact_root_field->as_string().empty()) {
                result.message = "shader_artifact_root must be a non-empty relative path when provided";
                tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
                return result;
            }
            shader_root = package_path(root, artifact_root_field->as_string());
        }
        result.shader_runtime.artifact_root = shader_root.string();
        result.shader_runtime.cache_root = (root / ".shader-cache").string();
        result.shader_runtime.dev_compile_enabled = false;

        const nos::trent* resources = dict_get(manifest, "resources");
        if (!resources || !resources->is_list()) {
            result.message = "manifest resources must be a list";
            tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
            return result;
        }
        auto keepalive = std::make_shared<RuntimePackageResourceKeepalive>();
        ensure_runtime_builtin_textures();
        constexpr std::array<const char*, 6> resource_order = {
            "shader", "mesh", "texture", "material", "pipeline", "foliage_data"
        };
        const auto& resource_list = resources->as_list();
        auto load_entry = [&](const nos::trent& resource) -> bool {
            std::string resource_error;
            if (load_resource(root, resource, *keepalive, resource_error)) {
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

        const std::string scene_path = string_field(manifest, "scene");
        if (scene_path.empty()) {
            result.message = "manifest scene path is missing";
            tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
            return result;
        }

        result.scene = load_runtime_scene(root, scene_path);
        result.ok = result.scene.valid();
        result.message = result.ok ? "ok" : "scene is invalid";
        if (result.ok) {
            result.resources = std::move(keepalive);
            tc_log_info(
                "RuntimePackageLoader: loaded package '%s' entities=%zu",
                root.string().c_str(),
                result.scene.entity_count()
            );
        }
    } catch (const std::exception& ex) {
        result.ok = false;
        result.message = ex.what();
        tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
    }
    return result;
}

RuntimePackageLoadResult load_runtime_package(
    const std::string& root_path
) {
    RuntimePackageLoader loader;
    return loader.load(root_path);
}

} // namespace termin::runtime
