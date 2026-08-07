#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>

#if defined(_WIN32) && defined(TERMIN_FRAMEGRAPH_REMOTE_TARGET_EXPORTS)
#define TERMIN_FRAMEGRAPH_REMOTE_TARGET_API __declspec(dllexport)
#elif defined(_WIN32)
#define TERMIN_FRAMEGRAPH_REMOTE_TARGET_API __declspec(dllimport)
#else
#define TERMIN_FRAMEGRAPH_REMOTE_TARGET_API                                    \
    __attribute__((visibility("default")))
#endif

namespace termin
{
    class FrameGraphDebugger;
}

namespace termin::framegraph_remote_target
{

    struct TargetServiceConfig
    {
        std::string bind_address = "127.0.0.1";
        std::uint16_t port = 0;
        std::string authentication_token;
        std::string platform;
        std::string abi;
        std::string build_type;
        std::string build_id;
        std::uint32_t process_id = 0;
        std::size_t command_queue_capacity = 64;
        std::size_t outbound_queue_capacity = 32;
        std::uint64_t capture_memory_budget_bytes = 256ULL * 1024ULL * 1024ULL;
    };

    struct TargetServiceStatus
    {
        bool running = false;
        bool client_connected = false;
        std::uint16_t listening_port = 0;
        std::uint64_t session_id = 0;
        std::uint64_t graph_revision = 0;
        std::uint64_t rejected_clients = 0;
        std::uint64_t rejected_commands = 0;
        std::uint64_t dropped_outbound_messages = 0;
        std::uint64_t transmitted_bytes = 0;
        std::uint64_t completed_captures = 0;
        std::uint64_t dropped_captures = 0;
        std::uint64_t preview_captures = 0;
        std::uint64_t burst_captures = 0;
        std::uint64_t capture_time_ns = 0;
        std::uint64_t readback_time_ns = 0;
        std::uint64_t conversion_time_ns = 0;
        std::uint64_t transfer_encode_time_ns = 0;
        std::uint64_t captured_bytes = 0;
        std::uint64_t effective_preview_millifps = 0;
    };

    // Construction, lifecycle and pump_render_thread() belong to the
    // render/main thread that owns the referenced debugger. status() is
    // thread-safe and may be called from any thread. The I/O thread never
    // touches FrameGraphDebugger.
    class TERMIN_FRAMEGRAPH_REMOTE_TARGET_API RemoteFrameGraphTarget
    {
    public:
        RemoteFrameGraphTarget(FrameGraphDebugger& debugger,
                               TargetServiceConfig config);
        ~RemoteFrameGraphTarget();

        RemoteFrameGraphTarget(const RemoteFrameGraphTarget&) = delete;
        RemoteFrameGraphTarget&
        operator=(const RemoteFrameGraphTarget&) = delete;

        bool start();
        void stop();
        void pump_render_thread();
        TargetServiceStatus status() const;

    private:
        class Impl;
        std::unique_ptr<Impl> impl_;
    };

} // namespace termin::framegraph_remote_target
