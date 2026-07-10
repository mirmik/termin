#ifdef _WIN32
    #define TERMIN_MODULE_TEST_EXPORT __declspec(dllexport)
#else
    #define TERMIN_MODULE_TEST_EXPORT __attribute__((visibility("default")))
#endif

extern "C" TERMIN_MODULE_TEST_EXPORT int termin_shadow_test_dependency_value() {
    return 42;
}
