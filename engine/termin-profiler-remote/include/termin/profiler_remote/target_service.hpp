#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>

#include <termin/profiler_remote/wire_codec.hpp>

namespace termin::profiler_remote {

    struct TargetServiceConfig {
        std::string bind_address = "127.0.0.1";
        std::uint16_t port = 0;
        std::string authentication_token;
        std::string platform;
        std::string abi;
        std::string build_type;
        std::string build_id;
        std::uint32_t process_id = 0;
        std::size_t command_queue_capacity = 64;
        std::size_t outbound_queue_capacity = 16;
        std::size_t capture_capacity = 512;
        std::size_t frames_per_batch = 16;
    };

    struct TargetServiceStatus {
        bool running = false;
        bool client_connected = false;
        bool capturing = false;
        bool profiling_sections = false;
        std::uint16_t listening_port = 0;
        std::uint64_t completed_frames = 0;
        std::uint64_t dropped_batches = 0;
        std::uint64_t dropped_frames = 0;
        std::uint64_t rejected_clients = 0;
        std::uint64_t transmitted_bytes = 0;
    };

    // Construction, start(), stop(), destruction and pump_frame_thread() belong to
    // the profiler frame thread. status() may be called from any thread. The owned
    // I/O thread never receives a tc_profiler pointer and the frame thread never
    // performs socket I/O.
    class TERMIN_PROFILER_REMOTE_API RemoteProfilerTarget {
    public:
        explicit RemoteProfilerTarget(TargetServiceConfig config);
        ~RemoteProfilerTarget();

        RemoteProfilerTarget(const RemoteProfilerTarget&) = delete;
        RemoteProfilerTarget& operator=(const RemoteProfilerTarget&) = delete;

        bool start();
        void stop();
        void pump_frame_thread();
        TargetServiceStatus status() const;

    private:
        class Impl;
        std::unique_ptr<Impl> impl_;
    };

} // namespace termin::profiler_remote
