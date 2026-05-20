#include <termin/runtime/runtime_package.hpp>

#include <cmath>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <stdexcept>
#include <string>
#include <vector>

#include <tcbase/tc_log.h>
#include <tcbase/trent/json.h>
#include <tgfx/tgfx_material_handle.hpp>
#include <tgfx/tgfx_mesh_handle.hpp>
#include <tgfx/tgfx_shader_handle.hpp>
#include <tgfx2/tc_shader_bridge.hpp>
#include <termin/camera/camera_component.hpp>
#include <termin/entity/entity.hpp>
#include <termin/lighting/light_component.hpp>
#include <termin/render/mesh_renderer.hpp>

namespace termin::runtime {
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

std::filesystem::path package_path(const std::filesystem::path& root, const std::string& rel) {
    std::filesystem::path p(rel);
    if (p.is_absolute()) {
        throw std::runtime_error("runtime package paths must be relative: " + rel);
    }
    return root / p;
}

bool list3(const nos::trent& t, double out[3]) {
    if (!t.is_list() || t.as_list().size() < 3) {
        return false;
    }
    const auto& list = t.as_list();
    for (int i = 0; i < 3; ++i) {
        if (!list[static_cast<size_t>(i)].is_numer()) {
            return false;
        }
        out[i] = static_cast<double>(list[static_cast<size_t>(i)].as_numer());
    }
    return true;
}

bool list4(const nos::trent& t, double out[4]) {
    if (!t.is_list() || t.as_list().size() < 4) {
        return false;
    }
    const auto& list = t.as_list();
    for (int i = 0; i < 4; ++i) {
        if (!list[static_cast<size_t>(i)].is_numer()) {
            return false;
        }
        out[i] = static_cast<double>(list[static_cast<size_t>(i)].as_numer());
    }
    return true;
}

void apply_transform(Entity& entity, const nos::trent& spec) {
    if (const nos::trent* pos = dict_get(spec, "position")) {
        double xyz[3];
        if (list3(*pos, xyz)) {
            entity.set_local_position(xyz);
        }
    }
    if (const nos::trent* rot = dict_get(spec, "rotation")) {
        double xyzw[4];
        if (list4(*rot, xyzw)) {
            entity.set_local_rotation(xyzw);
        }
    }
    if (const nos::trent* scale = dict_get(spec, "scale")) {
        double xyz[3];
        if (list3(*scale, xyz)) {
            entity.set_local_scale(xyz);
        }
    }
}

std::string resource_ref_uuid(const nos::trent& value) {
    if (value.is_string()) {
        return value.as_string();
    }
    if (value.is_dict()) {
        if (const nos::trent* uuid = value._get("uuid")) {
            if (uuid->is_string()) {
                return uuid->as_string();
            }
        }
    }
    return "";
}

bool load_shader_resource(const std::filesystem::path& root, const nos::trent& spec) {
    const std::string uuid = string_field(spec, "uuid");
    if (uuid.empty()) {
        tc_log_error("RuntimePackageLoader: shader resource has no uuid");
        return false;
    }

    const std::string vertex_rel = string_field(spec, "vertex_source_path");
    const std::string fragment_rel = string_field(spec, "fragment_source_path");
    if (fragment_rel.empty()) {
        tc_log_error("RuntimePackageLoader: shader '%s' has no fragment_source_path", uuid.c_str());
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
        tc_log_error("RuntimePackageLoader: failed to create shader '%s'", uuid.c_str());
        return false;
    }

    const std::string name = string_field(spec, "name", uuid);
    const std::string source_path = string_field(spec, "source_path", "runtime-package");
    shader.set_sources(vertex_source, fragment_source, geometry_source, name, source_path);
    tc_shader* raw = shader.get();
    if (!raw || !raw->fragment_source) {
        tc_log_error("RuntimePackageLoader: shader '%s' has no registered fragment source", uuid.c_str());
        return false;
    }
    return true;
}

bool load_material_resource(const nos::trent& spec) {
    const std::string uuid = string_field(spec, "uuid");
    const std::string name = string_field(spec, "name", uuid);
    if (uuid.empty() || name.empty()) {
        tc_log_error("RuntimePackageLoader: material resource requires uuid and name");
        return false;
    }

    TcMaterial material = TcMaterial::get_or_create(uuid, name);
    if (!material.is_valid()) {
        tc_log_error("RuntimePackageLoader: failed to create material '%s'", uuid.c_str());
        return false;
    }

    material.clear_phases();
    const nos::trent* phases = dict_get(spec, "phases");
    if (!phases || !phases->is_list()) {
        tc_log_error("RuntimePackageLoader: material '%s' has no phases list", uuid.c_str());
        return false;
    }

    for (const nos::trent& phase_spec : phases->as_list()) {
        const std::string shader_uuid = string_field(phase_spec, "shader");
        if (shader_uuid.empty()) {
            tc_log_error("RuntimePackageLoader: material '%s' phase has no shader", uuid.c_str());
            return false;
        }
        TcShader shader = TcShader::from_uuid(shader_uuid);
        if (!shader.is_valid()) {
            tc_log_error(
                "RuntimePackageLoader: material '%s' references missing shader '%s'",
                uuid.c_str(),
                shader_uuid.c_str()
            );
            return false;
        }
        const std::string mark = string_field(phase_spec, "mark", "opaque");
        const int priority = static_cast<int>(number_field(phase_spec, "priority", 0.0));
        if (!material.add_phase(shader, mark.c_str(), priority)) {
            tc_log_error("RuntimePackageLoader: failed to add phase to material '%s'", uuid.c_str());
            return false;
        }
    }
    return true;
}

tc_draw_mode parse_draw_mode(const std::string& value) {
    if (value == "lines") {
        return TC_DRAW_LINES;
    }
    return TC_DRAW_TRIANGLES;
}

bool load_mesh_resource(const nos::trent& spec) {
    const std::string uuid = string_field(spec, "uuid");
    const std::string name = string_field(spec, "name", uuid);
    if (uuid.empty() || name.empty()) {
        tc_log_error("RuntimePackageLoader: mesh resource requires uuid and name");
        return false;
    }

    const nos::trent* layout_spec = dict_get(spec, "layout");
    const nos::trent* vertex_spec = dict_get(spec, "vertices");
    const nos::trent* index_spec = dict_get(spec, "indices");
    if (!layout_spec || !layout_spec->is_list() ||
        !vertex_spec || !vertex_spec->is_list() ||
        !index_spec || !index_spec->is_list()) {
        tc_log_error("RuntimePackageLoader: mesh '%s' requires layout, vertices and indices", uuid.c_str());
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
            tc_log_error("RuntimePackageLoader: mesh '%s' has unsupported vertex layout", uuid.c_str());
            return false;
        }
        tc_vertex_layout_add(&layout, attr_name.c_str(), components, TC_ATTRIB_FLOAT32, static_cast<uint8_t>(location));
        floats_per_vertex += static_cast<size_t>(components);
    }
    if (floats_per_vertex == 0) {
        tc_log_error("RuntimePackageLoader: mesh '%s' has empty vertex layout", uuid.c_str());
        return false;
    }

    std::vector<float> vertices;
    vertices.reserve(vertex_spec->as_list().size());
    for (const nos::trent& v : vertex_spec->as_list()) {
        if (!v.is_numer()) {
            tc_log_error("RuntimePackageLoader: mesh '%s' has non-numeric vertex data", uuid.c_str());
            return false;
        }
        vertices.push_back(static_cast<float>(v.as_numer()));
    }
    if (vertices.size() % floats_per_vertex != 0) {
        tc_log_error("RuntimePackageLoader: mesh '%s' vertex data does not match layout", uuid.c_str());
        return false;
    }

    std::vector<uint32_t> indices;
    indices.reserve(index_spec->as_list().size());
    for (const nos::trent& idx : index_spec->as_list()) {
        if (!idx.is_numer() || idx.as_numer() < 0) {
            tc_log_error("RuntimePackageLoader: mesh '%s' has invalid index data", uuid.c_str());
            return false;
        }
        indices.push_back(static_cast<uint32_t>(idx.as_numer()));
    }
    if (indices.empty()) {
        tc_log_error("RuntimePackageLoader: mesh '%s' has no indices", uuid.c_str());
        return false;
    }

    const size_t vertex_count = vertices.size() / floats_per_vertex;
    TcMesh mesh = TcMesh::from_interleaved(
        vertices.data(),
        vertex_count,
        indices.data(),
        indices.size(),
        layout,
        name,
        uuid,
        parse_draw_mode(string_field(spec, "draw_mode", "triangles"))
    );
    if (!mesh.is_valid()) {
        tc_log_error("RuntimePackageLoader: failed to create mesh '%s'", uuid.c_str());
        return false;
    }
    return true;
}

bool load_resource(const std::filesystem::path& root, const nos::trent& entry) {
    const std::string type = string_field(entry, "type");
    const std::string rel_path = string_field(entry, "path");
    if (type.empty() || rel_path.empty()) {
        tc_log_error("RuntimePackageLoader: resource entry requires type and path");
        return false;
    }

    const nos::trent spec = nos::json::parse(read_text_file(package_path(root, rel_path)));
    if (type == "shader") {
        return load_shader_resource(root, spec);
    }
    if (type == "material") {
        return load_material_resource(spec);
    }
    if (type == "mesh") {
        return load_mesh_resource(spec);
    }

    tc_log_error("RuntimePackageLoader: unsupported resource type '%s'", type.c_str());
    return false;
}

CameraComponent* add_camera_component(Entity& entity, const nos::trent& data) {
    auto* camera = new CameraComponent();
    camera->near_clip = number_field(data, "near_clip", camera->near_clip);
    camera->far_clip = number_field(data, "far_clip", camera->far_clip);
    if (const nos::trent* fov = dict_get(data, "fov_y_degrees")) {
        if (fov->is_numer()) {
            camera->set_fov_y_degrees(static_cast<double>(fov->as_numer()));
            camera->set_fov_mode_str("FixVertical");
        }
    }
    camera->aspect = number_field(data, "aspect", camera->aspect);
    entity.add_component(camera);
    return camera;
}

bool add_mesh_component(Entity& entity, const nos::trent& data) {
    const std::string mesh_uuid = resource_ref_uuid(data);
    TcMesh mesh = TcMesh::from_uuid(mesh_uuid);
    if (!mesh.is_valid()) {
        tc_log_error("RuntimePackageLoader: MeshComponent references missing mesh '%s'", mesh_uuid.c_str());
        return false;
    }
    auto* component = new MeshComponent();
    component->set_mesh(mesh);
    entity.add_component(component);
    return true;
}

bool add_mesh_renderer(Entity& entity, const nos::trent& data) {
    auto* renderer = new MeshRenderer();
    if (const nos::trent* mesh_value = dict_get(data, "mesh")) {
        const std::string mesh_uuid = resource_ref_uuid(*mesh_value);
        TcMesh mesh = TcMesh::from_uuid(mesh_uuid);
        if (!mesh.is_valid()) {
            tc_log_error("RuntimePackageLoader: MeshRenderer references missing mesh '%s'", mesh_uuid.c_str());
            delete renderer;
            return false;
        }
        renderer->set_mesh(mesh);
    }
    if (const nos::trent* material_value = dict_get(data, "material")) {
        const std::string material_uuid = resource_ref_uuid(*material_value);
        TcMaterial material = TcMaterial::from_uuid(material_uuid);
        if (!material.is_valid()) {
            tc_log_error(
                "RuntimePackageLoader: MeshRenderer references missing material '%s'",
                material_uuid.c_str()
            );
            delete renderer;
            return false;
        }
        renderer->set_material(material);
    }
    entity.add_component(renderer);
    return true;
}

bool add_light_component(Entity& entity, const nos::trent& data) {
    auto* light = new LightComponent();
    const std::string type = string_field(data, "light_type");
    if (!type.empty()) {
        light->set_light_type_str(type);
    }
    light->intensity = number_field(data, "intensity", light->intensity);
    if (const nos::trent* color = dict_get(data, "color")) {
        double rgb[3];
        if (list3(*color, rgb)) {
            light->color = Vec3(rgb[0], rgb[1], rgb[2]);
        }
    }
    entity.add_component(light);
    return true;
}

bool add_component_from_spec(Entity& entity, const nos::trent& component_spec, CameraComponent** out_camera) {
    const std::string type = string_field(component_spec, "type");
    const nos::trent* data = dict_get(component_spec, "data");
    const nos::trent empty_data;
    const nos::trent& component_data = data ? *data : empty_data;

    if (type == "MeshComponent") {
        return add_mesh_component(entity, component_data);
    }
    if (type == "MeshRenderer") {
        return add_mesh_renderer(entity, component_data);
    }
    if (type == "CameraComponent") {
        CameraComponent* camera = add_camera_component(entity, component_data);
        if (out_camera && !*out_camera) {
            *out_camera = camera;
        }
        return true;
    }
    if (type == "LightComponent") {
        return add_light_component(entity, component_data);
    }

    tc_log_error("RuntimePackageLoader: unsupported runtime scene component '%s'", type.c_str());
    return false;
}

TcSceneRef load_runtime_scene(const std::filesystem::path& root, const std::string& rel_path) {
    const nos::trent scene_spec = nos::json::parse(read_text_file(package_path(root, rel_path)));
    const std::string name = string_field(scene_spec, "name", "runtime-scene");
    const std::string uuid = string_field(scene_spec, "uuid");
    TcSceneRef scene = TcSceneRef::create(name, uuid);
    if (!scene.valid()) {
        throw std::runtime_error("failed to create runtime scene");
    }
    scene.set_source_path(package_path(root, rel_path).string());

    CameraComponent* first_camera = nullptr;
    const nos::trent* entities = dict_get(scene_spec, "entities");
    if (!entities || !entities->is_list()) {
        throw std::runtime_error("runtime scene has no entities list: " + rel_path);
    }

    for (const nos::trent& entity_spec : entities->as_list()) {
        const std::string entity_name = string_field(entity_spec, "name", "Entity");
        const std::string entity_uuid = string_field(entity_spec, "uuid");
        Entity entity = entity_uuid.empty()
            ? scene.create_entity(entity_name)
            : Entity::create_with_uuid(scene.entity_pool(), entity_name, entity_uuid);
        if (!entity.valid()) {
            throw std::runtime_error("failed to create entity: " + entity_name);
        }
        apply_transform(entity, entity_spec);

        const nos::trent* components = dict_get(entity_spec, "components");
        if (!components || !components->is_list()) {
            continue;
        }
        for (const nos::trent& component_spec : components->as_list()) {
            if (!add_component_from_spec(entity, component_spec, &first_camera)) {
                throw std::runtime_error("failed to add component to entity: " + entity_name);
            }
        }
    }

    if (!first_camera) {
        tc_log_error("RuntimePackageLoader: scene '%s' has no CameraComponent", rel_path.c_str());
    }
    return scene;
}

} // namespace

RuntimePackageLoadResult RuntimePackageLoader::load(
    const std::string& root_path,
    const RuntimePackageLoadOptions&
) {
    RuntimePackageLoadResult result;
    try {
        const std::filesystem::path root(root_path);
        const std::filesystem::path manifest_path = root / "manifest.json";
        if (!std::filesystem::is_regular_file(manifest_path)) {
            result.message = "manifest.json not found in " + root.string();
            tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
            return result;
        }

        const nos::trent manifest = nos::json::parse(read_text_file(manifest_path));
        const std::string artifact_root = string_field(manifest, "shader_artifact_root", ".");
        const std::filesystem::path shader_root = package_path(root, artifact_root);
        tgfx2_set_shader_artifact_root(shader_root.string().c_str());

        const nos::trent* resources = dict_get(manifest, "resources");
        if (!resources || !resources->is_list()) {
            result.message = "manifest resources must be a list";
            tc_log_error("RuntimePackageLoader: %s", result.message.c_str());
            return result;
        }
        for (const nos::trent& resource : resources->as_list()) {
            if (!load_resource(root, resource)) {
                result.message = "failed to load resource";
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
    const std::string& root_path,
    const RuntimePackageLoadOptions& options
) {
    RuntimePackageLoader loader;
    return loader.load(root_path, options);
}

} // namespace termin::runtime
