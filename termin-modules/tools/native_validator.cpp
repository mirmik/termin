#include <filesystem>
#include <iostream>
#include <iterator>
#include <string>

#include <termin_modules/native_module_validation.hpp>

#ifdef _WIN32
    #ifndef NOMINMAX
        #define NOMINMAX
    #endif
    #ifndef WIN32_LEAN_AND_MEAN
        #define WIN32_LEAN_AND_MEAN
    #endif
    #include <windows.h>
#else
    #include <dlfcn.h>
#endif

namespace {

std::string json_escape(const char* value) {
    std::string result;
    if (!value) return result;
    for (const char* p = value; *p; ++p) {
        if (*p == '\\' || *p == '"') result.push_back('\\');
        result.push_back(*p);
    }
    return result;
}

int validate_library(
    const char* path,
    const std::string& expected_module_id,
    bool inspect
) {
#ifdef _WIN32
    wchar_t executable_path[MAX_PATH] = {};
    const DWORD executable_path_size = GetModuleFileNameW(
        nullptr,
        executable_path,
        static_cast<DWORD>(std::size(executable_path))
    );
    if (executable_path_size == 0 || executable_path_size >= std::size(executable_path)) {
        std::cerr << "Failed to resolve native validator directory, error code "
                  << GetLastError() << "\n";
        return 2;
    }
    const std::filesystem::path validator_directory =
        std::filesystem::path(executable_path).parent_path();
    if (!SetDllDirectoryW(validator_directory.c_str())) {
        std::cerr << "Failed to add native validator directory to DLL search path: '"
                  << validator_directory.string() << "', error code "
                  << GetLastError() << "\n";
        return 2;
    }
    std::filesystem::path load_path = std::filesystem::absolute(path);
    load_path.make_preferred();
    HMODULE handle = LoadLibraryExW(
        load_path.c_str(),
        nullptr,
        LOAD_WITH_ALTERED_SEARCH_PATH);
    if (!handle) {
        std::cerr << "LoadLibrary failed for '" << load_path.string()
                  << "' with error code "
                  << GetLastError() << "\n";
        return 2;
    }
    const auto* descriptor = reinterpret_cast<
        const termin_native_module_descriptor_v1_data*>(
            GetProcAddress(handle, TERMIN_NATIVE_MODULE_DESCRIPTOR_SYMBOL));
#else
    void* handle = dlopen(path, RTLD_NOW | RTLD_LOCAL);
    if (!handle) {
        const char* error = dlerror();
        std::cerr << "dlopen failed for '" << path << "': "
                  << (error ? error : "unknown error") << "\n";
        return 2;
    }
    const auto* descriptor = reinterpret_cast<
        const termin_native_module_descriptor_v1_data*>(
            dlsym(handle, TERMIN_NATIVE_MODULE_DESCRIPTOR_SYMBOL));
#endif

    const auto validation = termin_modules::validate_native_module_descriptor_v1(
        descriptor,
        expected_module_id
    );
    if (!validation.compatible) {
        std::cerr << validation.error << "\n";
#ifdef _WIN32
        FreeLibrary(handle);
#else
        dlclose(handle);
#endif
        return descriptor ? 4 : 3;
    }

    if (inspect) {
        std::cout << "{\"module_id\":\"" << json_escape(descriptor->module_id)
                  << "\",\"module_version\":\""
                  << json_escape(descriptor->module_version)
                  << "\",\"build_id\":\"" << json_escape(descriptor->build_id)
                  << "\",\"module_abi_version\":" << descriptor->module_abi_version
                  << ",\"sdk_version\":" << descriptor->sdk_version
                  << ",\"capabilities\":" << descriptor->capabilities << "}\n";
    }

#ifdef _WIN32
    FreeLibrary(handle);
#else
    dlclose(handle);
#endif
    return 0;
}

} // namespace

int main(int argc, char** argv) {
    bool inspect = false;
    int path_index = 1;
    if (argc > 1 && std::string(argv[1]) == "--inspect") {
        inspect = true;
        path_index = 2;
    }
    if (argc <= path_index || argc > path_index + 2) {
        std::cerr << "usage: termin_module_native_validator [--inspect] "
                     "<shared-library> [expected-module-id]\n";
        return 1;
    }
    const std::string expected = argc == path_index + 2 ? argv[path_index + 1] : "";
    return validate_library(argv[path_index], expected, inspect);
}
