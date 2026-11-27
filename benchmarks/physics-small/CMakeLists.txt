cmake_minimum_required(VERSION 3.20)
project(termin_small_physics_benchmark LANGUAGES CXX)
find_package(termin_physics_qopt CONFIG REQUIRED)
find_package(termin_collision CONFIG REQUIRED)
add_executable(physics_small_benchmark bench.cpp benchmark_common.cpp controller.cpp contact_pipeline.cpp solver_replay.cpp)
target_compile_features(physics_small_benchmark PRIVATE cxx_std_20)
target_link_libraries(physics_small_benchmark PRIVATE termin_physics_qopt::termin_physics_qopt termin_collision::termin_collision)

option(TERMIN_BENCHMARK_SPIDER_SNAPSHOT "Build the live spider articulation reader" OFF)
if(TERMIN_BENCHMARK_SPIDER_SNAPSHOT)
    find_package(Python COMPONENTS Interpreter Development REQUIRED)
    find_package(nanobind CONFIG REQUIRED)
    find_package(termin_robotics CONFIG REQUIRED)
    nanobind_add_module(_spider_termin_snapshot NB_SHARED spider_termin_snapshot.cpp)
    target_compile_features(_spider_termin_snapshot PRIVATE cxx_std_20)
    target_link_libraries(_spider_termin_snapshot PRIVATE termin_robotics::termin_robotics)
endif()

set(TERMIN_BENCHMARK_MUJOCO_DIR "" CACHE PATH "Directory of the Linux MuJoCo 3.15.0 Python wheel")
if(TERMIN_BENCHMARK_MUJOCO_DIR)
    find_package(termin_robotics CONFIG REQUIRED)
    add_library(benchmark_mujoco SHARED IMPORTED)
    set_target_properties(benchmark_mujoco PROPERTIES
        IMPORTED_LOCATION "${TERMIN_BENCHMARK_MUJOCO_DIR}/libmujoco.so.3.15.0"
        INTERFACE_INCLUDE_DIRECTORIES "${TERMIN_BENCHMARK_MUJOCO_DIR}/include")

    add_library(predict_contact SHARED predict_contact_sweep.cpp predict_contact_step.cpp spider_termin_dynamics_mj.cpp)
    target_compile_features(predict_contact PRIVATE cxx_std_20)
    target_compile_definitions(predict_contact PRIVATE TERMIN_CONTACT_PREDICTION)
    target_link_libraries(predict_contact PRIVATE benchmark_mujoco termin_robotics::termin_robotics)

    add_library(predict_geometry SHARED spider_mujoco_hybrid.cpp)
    target_compile_features(predict_geometry PRIVATE cxx_std_20)
    target_link_libraries(predict_geometry PRIVATE benchmark_mujoco termin_collision::termin_collision)
endif()

if(UNIX AND NOT APPLE)
    # ELF symbol interposition lets a separate probe count SDK C++ new calls
    # without adding allocation hooks to the throughput executable.
    add_executable(physics_small_allocations allocation_probe.cpp benchmark_common.cpp)
    target_compile_features(physics_small_allocations PRIVATE cxx_std_20)
    target_link_libraries(physics_small_allocations PRIVATE termin_physics_qopt::termin_physics_qopt)
    set_target_properties(physics_small_allocations PROPERTIES ENABLE_EXPORTS ON)
endif()
