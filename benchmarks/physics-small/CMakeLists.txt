cmake_minimum_required(VERSION 3.20)
project(termin_small_physics_benchmark LANGUAGES CXX)
find_package(termin_physics_qopt CONFIG REQUIRED)
find_package(termin_collision CONFIG REQUIRED)
add_executable(physics_small_benchmark bench.cpp benchmark_common.cpp controller.cpp contact_pipeline.cpp solver_replay.cpp)
target_compile_features(physics_small_benchmark PRIVATE cxx_std_20)
target_link_libraries(physics_small_benchmark PRIVATE termin_physics_qopt::termin_physics_qopt termin_collision::termin_collision)

if(UNIX AND NOT APPLE)
    # ELF symbol interposition lets a separate probe count SDK C++ new calls
    # without adding allocation hooks to the throughput executable.
    add_executable(physics_small_allocations allocation_probe.cpp benchmark_common.cpp)
    target_compile_features(physics_small_allocations PRIVATE cxx_std_20)
    target_link_libraries(physics_small_allocations PRIVATE termin_physics_qopt::termin_physics_qopt)
    set_target_properties(physics_small_allocations PROPERTIES ENABLE_EXPORTS ON)
endif()
