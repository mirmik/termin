#include "guard_main.h"

#if defined(_WIN32)
#include <windows.h>
#else
#include <dlfcn.h>
#endif

#include <cstdlib>
#include <iostream>

namespace {

void load_render_components()
{
#if defined(_WIN32)
    const char* library_name = "termin_components_render.dll";
    HMODULE handle = LoadLibraryA(library_name);
    if (handle == nullptr) {
        std::cerr << "failed to load " << library_name << "\n";
        std::exit(1);
    }
#else
#if defined(__APPLE__)
    const char* library_name = "libtermin_components_render.dylib";
#else
    const char* library_name = "libtermin_components_render.so";
#endif
    void* handle = dlopen(library_name, RTLD_NOW | RTLD_GLOBAL);
    if (handle == nullptr) {
        std::cerr << "failed to load " << library_name << ": " << dlerror() << "\n";
        std::exit(1);
    }
#endif
}

struct RenderComponentsLoader {
    RenderComponentsLoader() { load_render_components(); }
};

RenderComponentsLoader render_components_loader;

} // namespace

GUARD_TEST_MAIN();
