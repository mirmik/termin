#include <termin/modules/term_modules_integration.hpp>
#include <termin/scene/scene_manager.hpp>

#include <termin_modules/module_cpp_backend.hpp>
#include <termin_modules/module_runtime.hpp>

#include <tc_inspect_cpp.hpp>

#include <termin/entity/component.hpp>
#include <termin/entity/component_registry.hpp>
#include <termin/entity/entity.hpp>
#include <termin/entity/unknown_component.hpp>
#include <termin/tc_scene.hpp>

#include <inspect/tc_inspect.h>

#include <chrono>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <string>

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            std::cerr << "FAIL: " << msg << " (line " << __LINE__ << ")\n"; \
            return 1; \
        } \
    } while (0)

namespace {

constexpr const char* kModuleId = "native_probe";
constexpr const char* kComponentType = "HotReloadNativeProbeComponent";

class TempDir {
public:
    std::filesystem::path path;

    TempDir() {
        const auto unique = std::chrono::steady_clock::now().time_since_epoch().count();
        path = std::filesystem::temp_directory_path() /
            ("termin-engine-cpp-hot-reload-" + std::to_string(unique));
        std::filesystem::create_directories(path);
    }

    ~TempDir() {
        std::error_code ec;
        std::filesystem::remove_all(path, ec);
    }
};

void write_text_file(const std::filesystem::path& path, const std::string& text) {
    std::filesystem::create_directories(path.parent_path());
    std::ofstream out(path);
    out << text;
}

std::string yaml_quote(const std::string& value) {
    std::string result = "\"";
    for (const char ch : value) {
        if (ch == '\\' || ch == '"') {
            result.push_back('\\');
        }
        result.push_back(ch);
    }
    result.push_back('"');
    return result;
}

std::filesystem::path copy_module_artifact(const std::filesystem::path& source,
                                           const std::filesystem::path& dir) {
#ifdef _WIN32
    const std::filesystem::path artifact = dir / "native_probe.dll";
#elif defined(__APPLE__)
    const std::filesystem::path artifact = dir / "libnative_probe.dylib";
#else
    const std::filesystem::path artifact = dir / "libnative_probe.so";
#endif
    std::filesystem::copy_file(
        source,
        artifact,
        std::filesystem::copy_options::overwrite_existing
    );
    return artifact;
}

void write_descriptor(const std::filesystem::path& descriptor,
                      const std::filesystem::path& artifact) {
    write_text_file(
        descriptor,
        "name: native_probe\n"
        "components: [HotReloadNativeProbeComponent]\n"
        "build:\n"
        "  output: " + yaml_quote(artifact.string()) + "\n"
    );
}

int component_int_field(tc_component* component, const char* path) {
    void* object = termin::CxxComponent::from_tc(component);
    tc_value data = tc_inspect_serialize(object, kComponentType);
    tc_value* value = tc_value_dict_get(&data, path);
    const int result = value && value->type == TC_VALUE_INT
        ? static_cast<int>(value->data.i)
        : -1;
    tc_value_free(&data);
    return result;
}

void set_component_int_field(tc_component* component, const char* path, int field_value) {
    void* object = termin::CxxComponent::from_tc(component);
    tc_value data = tc_value_dict_new();
    tc_value_dict_set(&data, path, tc_value_int(field_value));
    tc_inspect_deserialize(object, kComponentType, &data, nullptr);
    tc_value_free(&data);
}

int run_cpp_module_hot_reload_smoke() {
    tc::init_cpp_inspect_vtable();
    tc::register_builtin_cpp_kinds();

    TempDir tmp;
    const std::filesystem::path source_artifact = TERMIN_ENGINE_CPP_HOT_RELOAD_TEST_MODULE;
    const std::filesystem::path artifact = copy_module_artifact(source_artifact, tmp.path);
    const std::filesystem::path descriptor = tmp.path / "native_probe.module";
    write_descriptor(descriptor, artifact);

    termin::SceneManager scene_manager;
    termin::TermModulesIntegration integration;

    termin_modules::ModuleRuntime runtime;
    runtime.register_backend(std::make_shared<termin_modules::CppModuleBackend>());
    integration.configure_runtime(runtime);
    runtime.discover(tmp.path);

    TEST_ASSERT(runtime.load_module(kModuleId), runtime.last_error());
    TEST_ASSERT(termin::ComponentRegistry::instance().has(kComponentType),
                "native component registered after load");
    TEST_ASSERT(termin::ComponentRegistry::instance().owner_of(kComponentType) == kModuleId,
                "native component owner captured");
    TEST_ASSERT(tc::InspectRegistry::instance().owner_of(kComponentType) == kModuleId,
                "inspect owner captured");
    TEST_ASSERT(tc::InspectRegistry::instance().find_field(kComponentType, "value") != nullptr,
                "inspect field registered after load");

    tc_scene_handle scene_handle = scene_manager.create_scene("cpp-hot-reload");
    termin::TcSceneRef scene(scene_handle);
    termin::Entity entity = scene.create_entity("entity");
    tc_component* component = tc_component_registry_create(kComponentType);
    TEST_ASSERT(component != nullptr, "native component instance created");
    set_component_int_field(component, "value", 77);
    entity.add_component_ptr(component);

    TEST_ASSERT(runtime.reload_module(kModuleId), runtime.last_error());
    TEST_ASSERT(termin::ComponentRegistry::instance().has(kComponentType),
                "native component registered after reload");
    TEST_ASSERT(tc::InspectRegistry::instance().find_field(kComponentType, "value") != nullptr,
                "inspect field registered after reload");

    tc_component* upgraded = entity.get_component_by_type_name(kComponentType);
    TEST_ASSERT(upgraded != nullptr, "UnknownComponent upgraded back after reload");
    TEST_ASSERT(entity.get_component_by_type_name("UnknownComponent") == nullptr,
                "no UnknownComponent remains after successful reload");
    TEST_ASSERT(component_int_field(upgraded, "value") == 77,
                "component inspect data survives reload roundtrip");

    TEST_ASSERT(runtime.unload_module(kModuleId), runtime.last_error());
    TEST_ASSERT(!termin::ComponentRegistry::instance().has(kComponentType),
                "native component unregistered before native close");
    TEST_ASSERT(tc::InspectRegistry::instance().find_field(kComponentType, "value") == nullptr,
                "inspect field removed before native close");
    TEST_ASSERT(entity.get_component_by_type_name(kComponentType) == nullptr,
                "live component degraded during unload");
    TEST_ASSERT(entity.get_component_by_type_name("UnknownComponent") != nullptr,
                "UnknownComponent remains after unloaded module");

    std::filesystem::path broken_artifact = artifact;
    broken_artifact += ".missing";
    std::filesystem::rename(artifact, broken_artifact);
    TEST_ASSERT(!runtime.load_module(kModuleId), "load must fail when artifact is missing");
    TEST_ASSERT(!termin::ComponentRegistry::instance().has(kComponentType),
                "failed load does not restore stale component registry entry");
    TEST_ASSERT(tc::InspectRegistry::instance().find_field(kComponentType, "value") == nullptr,
                "failed load does not restore stale inspect entry");
    std::filesystem::rename(broken_artifact, artifact);

    TEST_ASSERT(runtime.load_module(kModuleId), runtime.last_error());
    TEST_ASSERT(entity.get_component_by_type_name(kComponentType) != nullptr,
                "UnknownComponent upgraded after artifact restore");
    TEST_ASSERT(entity.get_component_by_type_name("UnknownComponent") == nullptr,
                "UnknownComponent removed after artifact restore");

    scene_manager.close_scene("cpp-hot-reload");
    runtime.unload_module(kModuleId);
    return 0;
}

} // namespace

int main() {
    return run_cpp_module_hot_reload_smoke();
}
