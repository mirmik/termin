#include <iostream>
#include <string>

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

int validate_library(const char* path) {
#ifdef _WIN32
    HMODULE handle = LoadLibraryA(path);
    if (handle == nullptr) {
        const DWORD error_code = GetLastError();
        std::cerr << "LoadLibrary failed for '" << path << "' with error code " << error_code << "\n";
        return 2;
    }
    FreeLibrary(handle);
#else
    void* handle = dlopen(path, RTLD_NOW | RTLD_LOCAL);
    if (handle == nullptr) {
        const char* error = dlerror();
        std::cerr << "dlopen failed for '" << path << "': " << (error != nullptr ? error : "unknown error") << "\n";
        return 2;
    }
    dlclose(handle);
#endif
    return 0;
}

} // namespace

int main(int argc, char** argv) {
    if (argc != 2) {
        std::cerr << "usage: termin_module_native_validator <shared-library>\n";
        return 1;
    }

    return validate_library(argv[1]);
}
