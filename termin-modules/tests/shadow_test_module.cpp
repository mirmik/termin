#ifdef _WIN32
    #define TERMIN_MODULE_TEST_EXPORT __declspec(dllexport)
#else
    #define TERMIN_MODULE_TEST_EXPORT __attribute__((visibility("default")))
#endif

extern "C" int termin_shadow_test_dependency_value();

extern "C" TERMIN_MODULE_TEST_EXPORT void module_init() {
    if (termin_shadow_test_dependency_value() != 42) {
        throw "shadow test dependency mismatch";
    }
}
extern "C" TERMIN_MODULE_TEST_EXPORT void module_shutdown() {}
