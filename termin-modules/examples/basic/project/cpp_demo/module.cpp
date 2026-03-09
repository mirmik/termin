#include <iostream>

extern "C" void module_init() {
    std::cout << "[cpp_demo] module_init\n";
}

extern "C" void module_shutdown() {
    std::cout << "[cpp_demo] module_shutdown\n";
}
