#include <termin/framegraph_remote_target/target_service.hpp>

#include <termin/framegraph_remote/bounded_spsc_queue.hpp>
#include <termin/framegraph_remote/latest_value_slot.hpp>
#include <termin/framegraph_remote/wire_codec.hpp>
#include <termin/render/frame_graph_debugger.hpp>

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <cmath>
#include <cstring>
#include <limits>
#include <memory>
#include <optional>
#include <span>
#include <stdexcept>
#include <thread>
#include <unordered_set>
#include <utility>
#include <variant>
#include <vector>

#include <tcbase/tc_log.h>

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <arpa/inet.h>
#include <fcntl.h>
#include <netinet/in.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>
#endif

namespace termin::framegraph_remote_target
{
    namespace
    {

        using namespace termin::framegraph_remote;
        using Clock = std::chrono::steady_clock;

#if defined(_WIN32)
        using Socket = SOCKET;
        constexpr Socket invalid_socket = INVALID_SOCKET;
#else
        using Socket = int;
        constexpr Socket invalid_socket = -1;
#endif

        std::uint64_t now_ns()
        {
            return static_cast<std::uint64_t>(
                std::chrono::duration_cast<std::chrono::nanoseconds>(
                    Clock::now().time_since_epoch())
                    .count());
        }

        void close_socket(Socket socket)
        {
            if (socket == invalid_socket)
                return;
#if defined(_WIN32)
            closesocket(socket);
#else
            close(socket);
#endif
        }

        void shutdown_socket(Socket socket)
        {
            if (socket == invalid_socket)
                return;
#if defined(_WIN32)
            shutdown(socket, SD_BOTH);
#else
            shutdown(socket, SHUT_RDWR);
#endif
        }

        int socket_error()
        {
#if defined(_WIN32)
            return WSAGetLastError();
#else
            return errno;
#endif
        }

        bool interrupted_error(int error)
        {
#if defined(_WIN32)
            return error == WSAEINTR;
#else
            return error == EINTR;
#endif
        }

        bool would_block_error(int error)
        {
#if defined(_WIN32)
            return error == WSAEWOULDBLOCK;
#else
            return error == EAGAIN || error == EWOULDBLOCK;
#endif
        }

        bool set_nonblocking(Socket socket)
        {
#if defined(_WIN32)
            u_long enabled = 1;
            return ioctlsocket(socket, FIONBIO, &enabled) == 0;
#else
            const int flags = fcntl(socket, F_GETFL, 0);
            return flags >= 0 &&
                   fcntl(socket, F_SETFL, flags | O_NONBLOCK) == 0;
#endif
        }

        enum class WaitResult
        {
            ready,
            timeout,
            failed
        };

        WaitResult wait_socket(Socket socket,
                               bool write,
                               std::chrono::milliseconds timeout)
        {
            fd_set read_set;
            fd_set write_set;
            FD_ZERO(&read_set);
            FD_ZERO(&write_set);
            if (write)
                FD_SET(socket, &write_set);
            else
                FD_SET(socket, &read_set);
            timeval value{};
            value.tv_sec = static_cast<long>(timeout.count() / 1000);
            value.tv_usec = static_cast<long>((timeout.count() % 1000) * 1000);
#if defined(_WIN32)
            const int result =
                select(0, &read_set, &write_set, nullptr, &value);
#else
            const int result =
                select(socket + 1, &read_set, &write_set, nullptr, &value);
#endif
            if (result > 0)
                return WaitResult::ready;
            if (result == 0 || interrupted_error(socket_error()))
            {
                return WaitResult::timeout;
            }
            return WaitResult::failed;
        }

        template <typename Bytes, typename Transfer>
        bool transfer_exact(Socket socket,
                            Bytes bytes,
                            bool write,
                            const std::atomic<bool>& running,
                            Transfer transfer)
        {
            std::size_t offset = 0;
            const auto deadline = Clock::now() + std::chrono::seconds(2);
            while (offset < bytes.size() &&
                   running.load(std::memory_order_acquire))
            {
                const auto remaining =
                    std::chrono::duration_cast<std::chrono::milliseconds>(
                        deadline - Clock::now());
                if (remaining <= std::chrono::milliseconds::zero())
                {
                    tc_log_error(
                        "remote framegraph target: socket transfer timed out");
                    return false;
                }
                const WaitResult wait = wait_socket(
                    socket,
                    write,
                    std::min(remaining, std::chrono::milliseconds(50)));
                if (wait == WaitResult::timeout)
                    continue;
                if (wait == WaitResult::failed)
                {
                    tc_log_error("remote framegraph target: socket wait failed "
                                 "(error=%d)",
                                 socket_error());
                    return false;
                }
                const int count = transfer(bytes.subspan(offset));
                if (count > 0)
                {
                    offset += static_cast<std::size_t>(count);
                    continue;
                }
                if (count == 0)
                    return false;
                const int error = socket_error();
                if (interrupted_error(error) || would_block_error(error))
                    continue;
                tc_log_error(
                    "remote framegraph target: socket %s failed (error=%d)",
                    write ? "send" : "receive",
                    error);
                return false;
            }
            return offset == bytes.size();
        }

        bool send_bytes(Socket socket,
                        std::span<const std::uint8_t> bytes,
                        const std::atomic<bool>& running)
        {
            return transfer_exact(
                socket,
                bytes,
                true,
                running,
                [socket](std::span<const std::uint8_t> remaining)
                {
                    return send(socket,
                                reinterpret_cast<const char*>(remaining.data()),
                                static_cast<int>(remaining.size()),
                                0);
                });
        }

        bool receive_bytes(Socket socket,
                           std::span<std::uint8_t> bytes,
                           const std::atomic<bool>& running)
        {
            return transfer_exact(
                socket,
                bytes,
                false,
                running,
                [socket](std::span<std::uint8_t> remaining)
                {
                    return recv(socket,
                                reinterpret_cast<char*>(remaining.data()),
                                static_cast<int>(remaining.size()),
                                0);
                });
        }

        CodecResult<DecodedMessage>
        receive_message(Socket socket, const std::atomic<bool>& running)
        {
            std::vector<std::uint8_t> bytes(envelope_size);
            if (!receive_bytes(socket, bytes, running))
            {
                return {.value = std::nullopt,
                        .error = CodecError::truncated,
                        .detail = "connection closed while receiving envelope"};
            }
            auto envelope = decode_envelope(bytes);
            if (!envelope)
            {
                return {.value = std::nullopt,
                        .error = envelope.error,
                        .detail = std::move(envelope.detail)};
            }
            bytes.resize(envelope_size + envelope.value->payload_length);
            auto payload =
                std::span<std::uint8_t>(bytes).subspan(envelope_size);
            if (!payload.empty() && !receive_bytes(socket, payload, running))
            {
                return {.value = std::nullopt,
                        .error = CodecError::truncated,
                        .detail = "connection closed while receiving payload"};
            }
            return decode_message(bytes);
        }

        bool constant_time_equal(const std::string& left,
                                 const std::string& right)
        {
            std::size_t difference = left.size() ^ right.size();
            const std::size_t count = std::max(left.size(), right.size());
            for (std::size_t index = 0; index < count; ++index)
            {
                const unsigned char a =
                    index < left.size()
                        ? static_cast<unsigned char>(left[index])
                        : 0;
                const unsigned char b =
                    index < right.size()
                        ? static_cast<unsigned char>(right[index])
                        : 0;
                difference |= static_cast<std::size_t>(a ^ b);
            }
            return difference == 0;
        }

        struct QueuedCommand
        {
            std::uint64_t session_id = 0;
            std::uint32_t max_payload_bytes = WireLimits::max_payload_bytes;
            std::uint64_t max_blob_bytes = WireLimits::max_blob_bytes;
            std::uint32_t max_chunk_bytes = WireLimits::max_chunk_bytes;
            Command command;
        };

        struct CaptureBlob
        {
            std::uint64_t session_id = 0;
            CaptureMetadata metadata;
            std::vector<std::uint8_t> bytes;
            std::uint32_t chunk_bytes = 0;
        };

        struct OutboundPacket
        {
            std::uint64_t session_id = 0;
            std::optional<TopologySnapshot> topology;
            std::shared_ptr<const CaptureBlob> capture;
            std::optional<Status> status;
            std::optional<DropEvent> drop;
            std::optional<ErrorEvent> error;
        };

        struct PendingCapture
        {
            QueuedCommand queued;
            std::uint64_t debugger_generation = 0;
            Clock::time_point requested_at;
            CaptureKind kind = CaptureKind::snapshot;
            std::uint16_t burst_index = 0;
            std::uint16_t burst_count = 0;
        };

        struct StreamState
        {
            QueuedCommand queued;
            Clock::time_point next_capture_at{};
            Clock::time_point started_at{};
            std::uint64_t delivered_frames = 0;
        };

        struct BurstState
        {
            QueuedCommand queued;
            std::uint16_t next_index = 0;
            std::uint64_t retained_bytes = 0;
        };

        struct TargetBinding
        {
            std::uint64_t id = 0;
            RenderExecutionTargetId native_id;
        };

        bool topology_structure_equal(const TopologySnapshot& left,
                                      const TopologySnapshot& right)
        {
            return left.selected_target_id == right.selected_target_id &&
                   left.targets == right.targets &&
                   left.passes == right.passes &&
                   left.schedule == right.schedule &&
                   left.resources == right.resources &&
                   left.alias_groups == right.alias_groups;
        }

        bool valid_wire_name(const std::string& value)
        {
            return !value.empty() && value.size() <= WireLimits::max_name_bytes;
        }

        bool valid_wire_names(const std::vector<std::string>& values)
        {
            return std::all_of(values.begin(), values.end(), valid_wire_name);
        }

        SessionState project_state(FrameGraphDebuggerState state)
        {
            switch (state)
            {
            case FrameGraphDebuggerState::WaitingFrame:
                return SessionState::waiting_capture;
            case FrameGraphDebuggerState::Suspended:
                return SessionState::suspended;
            case FrameGraphDebuggerState::Error:
                return SessionState::error;
            case FrameGraphDebuggerState::Unbound:
            case FrameGraphDebuggerState::Bound:
            case FrameGraphDebuggerState::Captured:
                return SessionState::idle;
            }
            return SessionState::error;
        }

    } // namespace

    class RemoteFrameGraphTarget::Impl
    {
    public:
        Impl(FrameGraphDebugger* target_debugger,
             TargetServiceConfig target_config)
            : debugger(target_debugger), config(std::move(target_config)),
              command_queue(config.command_queue_capacity),
              outbound_queue(config.outbound_queue_capacity),
              owner_thread(std::this_thread::get_id()),
              debugger_attached(target_debugger != nullptr)
        {
            validate_config();
            refresh_topology();
        }

        ~Impl()
        {
            stop();
        }

        bool start()
        {
            if (!require_owner("start"))
                return false;
            if (running.load(std::memory_order_acquire))
                return true;
            if (config.bind_address != "127.0.0.1")
            {
                tc_log_error("remote framegraph target: non-loopback bind '%s' "
                             "is forbidden",
                             config.bind_address.c_str());
                return false;
            }
            if (config.authentication_token.empty())
            {
                tc_log_error("remote framegraph target: authentication token "
                             "must not be empty");
                return false;
            }
#if defined(_WIN32)
            WSADATA data{};
            if (WSAStartup(MAKEWORD(2, 2), &data) != 0)
            {
                tc_log_error("remote framegraph target: WSAStartup failed");
                return false;
            }
            winsock_started = true;
#endif
            const Socket listener = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
            if (listener == invalid_socket)
            {
                tc_log_error("remote framegraph target: socket creation failed "
                             "(error=%d)",
                             socket_error());
                cleanup_socket_runtime();
                return false;
            }
            int reuse = 1;
            setsockopt(listener,
                       SOL_SOCKET,
                       SO_REUSEADDR,
                       reinterpret_cast<const char*>(&reuse),
                       sizeof(reuse));
            sockaddr_in address{};
            address.sin_family = AF_INET;
            address.sin_port = htons(config.port);
            address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
            if (bind(listener,
                     reinterpret_cast<const sockaddr*>(&address),
                     sizeof(address)) != 0 ||
                listen(listener, 1) != 0 || !set_nonblocking(listener))
            {
                tc_log_error(
                    "remote framegraph target: loopback bind/listen failed "
                    "(port=%u error=%d)",
                    static_cast<unsigned>(config.port),
                    socket_error());
                close_socket(listener);
                cleanup_socket_runtime();
                return false;
            }
            sockaddr_in actual{};
#if defined(_WIN32)
            int actual_size = sizeof(actual);
#else
            socklen_t actual_size = sizeof(actual);
#endif
            if (getsockname(listener,
                            reinterpret_cast<sockaddr*>(&actual),
                            &actual_size) != 0)
            {
                tc_log_error(
                    "remote framegraph target: getsockname failed (error=%d)",
                    socket_error());
                close_socket(listener);
                cleanup_socket_runtime();
                return false;
            }
            listening_port.store(ntohs(actual.sin_port),
                                 std::memory_order_release);
            listener_socket.store(listener, std::memory_order_release);
            running.store(true, std::memory_order_release);
            io_thread = std::thread([this] { io_main(); });
            tc_log_info("remote framegraph target: listening on 127.0.0.1:%u",
                        static_cast<unsigned>(listening_port.load()));
            return true;
        }

        void stop()
        {
            if (std::this_thread::get_id() != owner_thread)
            {
                tc_log_error("remote framegraph target: stop called outside "
                             "owner thread");
            }
            if (!running.exchange(false, std::memory_order_acq_rel))
                return;
            close_owned_socket(client_socket);
            close_owned_socket(listener_socket);
            if (io_thread.joinable())
                io_thread.join();
            client_connected.store(false, std::memory_order_release);
            active_session.store(0, std::memory_order_release);
            listening_port.store(0, std::memory_order_release);
            cleanup_socket_runtime();
            QueuedCommand command;
            while (command_queue.try_pop(command))
            {
            }
            OutboundPacket packet;
            while (outbound_queue.try_pop(packet))
            {
            }
            if (pending_capture && debugger &&
                std::this_thread::get_id() == owner_thread)
                debugger->cancel_request();
            pending_capture.reset();
            stream.reset();
            burst.reset();
            clear_ready_preview();
            queued_capture_bytes.store(0, std::memory_order_relaxed);
            pending_dropped_outbound = 0;
            tc_log_info("remote framegraph target: stopped");
        }

        bool attach_debugger(FrameGraphDebugger& target_debugger)
        {
            if (!require_owner("attach_debugger"))
                return false;
            if (debugger == &target_debugger)
                return true;
            if (debugger)
                detach_debugger();
            debugger = &target_debugger;
            if (!refresh_topology())
            {
                debugger = nullptr;
                debugger_attached.store(false, std::memory_order_release);
                (void)refresh_topology();
                return false;
            }
            debugger_attached.store(true, std::memory_order_release);
            emit_lifecycle_status("render runtime attached");
            tc_log_info("remote framegraph target: render debugger attached");
            return true;
        }

        void detach_debugger()
        {
            if (!require_owner("detach_debugger") || !debugger)
                return;
            if (pending_capture)
                finish_operation(StatusCode::resource_unavailable,
                                 "render runtime was detached");
            if (stream)
            {
                emit_status(stream->queued,
                            StatusCode::resource_unavailable,
                            "render runtime was detached");
                stream.reset();
            }
            if (burst)
            {
                emit_status(burst->queued,
                            StatusCode::resource_unavailable,
                            "render runtime was detached");
                burst.reset();
            }
            clear_ready_preview();
            debugger = nullptr;
            debugger_attached.store(false, std::memory_order_release);
            target_bindings.clear();
            if (!refresh_topology())
                tc_log_error("remote framegraph target: failed to publish "
                             "detached runtime topology");
            emit_lifecycle_status("render runtime detached");
            tc_log_info("remote framegraph target: render debugger detached");
        }

        void pump_render_thread()
        {
            if (!require_owner("pump_render_thread"))
                return;
            QueuedCommand queued;
            while (command_queue.try_pop(queued))
            {
                apply_command(queued);
            }
            if (!debugger)
                return;
            poll_capture();
            schedule_continuous_capture();
        }

        TargetServiceStatus status() const
        {
            return {
                running.load(std::memory_order_acquire),
                client_connected.load(std::memory_order_acquire),
                debugger_attached.load(std::memory_order_acquire),
                listening_port.load(std::memory_order_acquire),
                active_session.load(std::memory_order_acquire),
                published_graph_revision.load(std::memory_order_acquire),
                rejected_clients.load(std::memory_order_relaxed),
                rejected_commands.load(std::memory_order_relaxed),
                dropped_outbound_messages.load(std::memory_order_relaxed),
                transmitted_bytes.load(std::memory_order_relaxed),
                completed_captures.load(std::memory_order_relaxed),
                dropped_captures.load(std::memory_order_relaxed),
                preview_captures.load(std::memory_order_relaxed),
                burst_captures.load(std::memory_order_relaxed),
                capture_time_ns.load(std::memory_order_relaxed),
                readback_time_ns.load(std::memory_order_relaxed),
                conversion_time_ns.load(std::memory_order_relaxed),
                transfer_encode_time_ns.load(std::memory_order_relaxed),
                captured_bytes.load(std::memory_order_relaxed),
                effective_preview_millifps.load(std::memory_order_relaxed),
            };
        }

    private:
        bool require_owner(const char* operation) const
        {
            if (std::this_thread::get_id() == owner_thread)
                return true;
            tc_log_error(
                "remote framegraph target: %s called outside owner thread",
                operation);
            return false;
        }

        void validate_config() const
        {
            if (config.capture_memory_budget_bytes == 0 ||
                config.capture_memory_budget_bytes > WireLimits::max_blob_bytes)
            {
                throw std::invalid_argument(
                    "remote framegraph target capture budget is invalid");
            }
            if (config.authentication_token.size() >
                WireLimits::max_token_bytes)
            {
                throw std::invalid_argument(
                    "remote framegraph target token exceeds wire limit");
            }
            for (const auto* field : {&config.platform,
                                      &config.abi,
                                      &config.build_type,
                                      &config.build_id})
            {
                if (field->size() > WireLimits::max_identity_bytes)
                {
                    throw std::invalid_argument(
                        "remote framegraph target identity exceeds wire limit");
                }
            }
        }

        void close_owned_socket(std::atomic<Socket>& storage)
        {
            const Socket socket =
                storage.exchange(invalid_socket, std::memory_order_acq_rel);
            if (socket != invalid_socket)
            {
                shutdown_socket(socket);
                close_socket(socket);
            }
        }

        void cleanup_socket_runtime()
        {
#if defined(_WIN32)
            if (winsock_started)
            {
                WSACleanup();
                winsock_started = false;
            }
#endif
        }

        std::uint64_t target_id_for(const RenderExecutionTargetId& native_id,
                                    std::vector<TargetBinding>& next_bindings)
        {
            const auto found =
                std::find_if(target_bindings.begin(),
                             target_bindings.end(),
                             [&native_id](const auto& binding)
                             { return binding.native_id == native_id; });
            const std::uint64_t id =
                found == target_bindings.end() ? next_target_id++ : found->id;
            next_bindings.push_back({id, native_id});
            return id;
        }

        bool build_topology(TopologySnapshot& next,
                            std::vector<TargetBinding>& next_bindings,
                            std::string& error)
        {
            if (!debugger)
                return true;
            const auto& targets = debugger->targets();
            const auto passes = debugger->passes();
            const auto schedule = debugger->schedule();
            const auto resources = debugger->resources();
            const auto aliases = debugger->alias_groups();
            if (targets.size() > WireLimits::max_targets ||
                passes.size() > WireLimits::max_passes ||
                schedule.size() > WireLimits::max_schedule_entries ||
                resources.size() > WireLimits::max_resources ||
                aliases.size() > WireLimits::max_alias_groups)
            {
                error = "framegraph topology exceeds a protocol hard limit";
                return false;
            }

            next_bindings.reserve(targets.size());
            next.targets.reserve(targets.size());
            for (const auto& target : targets)
            {
                if (target.label.empty() ||
                    target.label.size() > WireLimits::max_name_bytes)
                {
                    error = "framegraph target label exceeds protocol limits";
                    return false;
                }
                next.targets.push_back({target_id_for(target.id, next_bindings),
                                        target.label,
                                        target.renderable});
            }
            if (const auto selected = debugger->selected_target_index())
            {
                if (*selected < next.targets.size())
                {
                    next.selected_target_id = next.targets[*selected].id;
                }
            }

            next.passes.reserve(passes.size());
            std::unordered_set<std::uint64_t> pass_ids;
            for (const auto& pass : passes)
            {
                if (pass.index >= std::numeric_limits<std::uint32_t>::max() ||
                    !valid_wire_name(pass.name) ||
                    !valid_wire_name(pass.type) ||
                    pass.reads.size() > WireLimits::max_names_per_pass ||
                    pass.writes.size() > WireLimits::max_names_per_pass ||
                    pass.internal_symbols.size() >
                        WireLimits::max_names_per_pass ||
                    !valid_wire_names(pass.reads) ||
                    !valid_wire_names(pass.writes) ||
                    !valid_wire_names(pass.internal_symbols))
                {
                    error = "framegraph pass exceeds protocol limits";
                    return false;
                }
                const std::uint64_t pass_id =
                    static_cast<std::uint64_t>(pass.index) + 1;
                if (!pass_ids.insert(pass_id).second)
                {
                    error =
                        "framegraph contains duplicate authored pass indices";
                    return false;
                }
                next.passes.push_back({pass_id,
                                       static_cast<std::uint32_t>(pass.index),
                                       pass.name,
                                       pass.type,
                                       pass.enabled,
                                       pass.passthrough,
                                       pass.reads,
                                       pass.writes,
                                       pass.internal_symbols});
            }
            next.schedule.reserve(schedule.size());
            for (const auto& pass : schedule)
            {
                const std::uint64_t pass_id =
                    static_cast<std::uint64_t>(pass.index) + 1;
                if (!pass_ids.contains(pass_id))
                {
                    error =
                        "framegraph schedule references an unpublished pass";
                    return false;
                }
                next.schedule.push_back(pass_id);
            }
            if (!valid_wire_names(resources))
            {
                error = "framegraph resource name exceeds protocol limits";
                return false;
            }
            next.resources = resources;
            next.alias_groups.reserve(aliases.size());
            for (const auto& [canonical, names] : aliases)
            {
                if (!valid_wire_name(canonical) ||
                    names.size() > WireLimits::max_resources ||
                    !valid_wire_names(names))
                {
                    error = "framegraph alias group exceeds protocol limits";
                    return false;
                }
                next.alias_groups.push_back({canonical, names});
            }
            next.render_stats = debugger->format_render_stats();
            if (next.render_stats.size() > WireLimits::max_detail_bytes)
            {
                error = "framegraph render stats exceed protocol limits";
                return false;
            }
            return true;
        }

        bool refresh_topology()
        {
            if (debugger)
                debugger->refresh();
            TopologySnapshot next;
            std::vector<TargetBinding> next_bindings;
            std::string error;
            if (!build_topology(next, next_bindings, error))
            {
                topology_error = std::move(error);
                tc_log_error(
                    "remote framegraph target: topology projection failed: %s",
                    topology_error.c_str());
                return false;
            }
            std::uint64_t next_revision = graph_revision;
            if (topology.graph_revision == 0 ||
                !topology_structure_equal(topology, next))
            {
                ++next_revision;
            }
            next.graph_revision = next_revision;
            const auto encoded = encode_message(next, 1, 1);
            if (!encoded)
            {
                topology_error =
                    "framegraph topology cannot be encoded: " + encoded.detail;
                tc_log_error(
                    "remote framegraph target: topology projection failed: %s",
                    topology_error.c_str());
                return false;
            }
            topology_error.clear();
            graph_revision = next_revision;
            topology = std::move(next);
            target_bindings = std::move(next_bindings);
            published_graph_revision.store(graph_revision,
                                           std::memory_order_release);
            return true;
        }

        Status make_status(std::uint64_t request_id,
                           StatusCode code,
                           std::string detail) const
        {
            return {
                request_id,
                graph_revision,
                stream ? SessionState::streaming
                       : debugger ? project_state(debugger->state())
                                  : SessionState::suspended,
                code,
                static_cast<std::uint32_t>(outbound_queue.size_approximate()),
                completed_captures.load(std::memory_order_relaxed),
                dropped_captures.load(std::memory_order_relaxed),
                now_ns(),
                std::move(detail),
            };
        }

        void enforce_peer_payload_limit(OutboundPacket& packet,
                                        const QueuedCommand& queued)
        {
            if (!packet.topology)
                return;
            const auto encoded =
                encode_message(*packet.topology, 1, queued.session_id);
            if (encoded && encoded.value->size() - envelope_size <=
                               queued.max_payload_bytes)
                return;

            packet.topology.reset();
            packet.status = make_status(
                queued.command.request_id,
                StatusCode::limit_exceeded,
                encoded
                    ? "topology exceeds the client's negotiated payload limit"
                    : "topology failed final wire validation");
            tc_log_error("remote framegraph target: topology response exceeds "
                         "negotiated "
                         "payload limit (%u bytes)",
                         queued.max_payload_bytes);
        }

        void enqueue(OutboundPacket packet)
        {
            const std::uint64_t capture_bytes = packet.capture
                ? packet.capture->bytes.size() : 0;
            const std::int64_t capture_frame = packet.capture
                ? packet.capture->metadata.frame_number : 0;
            if (pending_dropped_outbound != 0)
            {
                packet.drop = DropEvent{
                    DropKind::receiver,
                    pending_dropped_outbound,
                    pending_dropped_after_frame,
                    0};
            }
            if (outbound_queue.try_push(std::move(packet)))
            {
                pending_dropped_outbound = 0;
                pending_dropped_after_frame = 0;
                return;
            }
            if (capture_bytes != 0)
            {
                queued_capture_bytes.fetch_sub(capture_bytes,
                                               std::memory_order_relaxed);
                dropped_captures.fetch_add(1, std::memory_order_relaxed);
                pending_dropped_after_frame = capture_frame;
            }
            ++pending_dropped_outbound;
            dropped_outbound_messages.fetch_add(1, std::memory_order_relaxed);
            tc_log_error("remote framegraph target: outbound queue full; "
                         "message dropped");
        }

        void note_preview_drop()
        {
            preview_slot.note_drop();
        }

        void publish_ready_preview(std::shared_ptr<CaptureBlob> blob)
        {
            const std::size_t new_bytes = blob->bytes.size();
            queued_capture_bytes.fetch_add(new_bytes,
                                           std::memory_order_relaxed);
            if (auto replaced = preview_slot.publish(std::move(blob)))
            {
                queued_capture_bytes.fetch_sub((*replaced)->bytes.size(),
                                               std::memory_order_relaxed);
                dropped_captures.fetch_add(1, std::memory_order_relaxed);
            }
        }

        void discard_obsolete_preview()
        {
            if (auto discarded = preview_slot.discard_ready())
            {
                queued_capture_bytes.fetch_sub((*discarded)->bytes.size(),
                                               std::memory_order_relaxed);
                dropped_captures.fetch_add(1, std::memory_order_relaxed);
            }
        }

        std::optional<LatestValueSlot<std::shared_ptr<CaptureBlob>>::Delivery>
        take_ready_preview()
        {
            return preview_slot.take();
        }

        void clear_ready_preview()
        {
            if (auto discarded = preview_slot.clear())
            {
                queued_capture_bytes.fetch_sub((*discarded)->bytes.size(),
                                               std::memory_order_relaxed);
            }
        }

        void reject_command(const QueuedCommand& queued,
                            StatusCode code,
                            const std::string& detail)
        {
            OutboundPacket packet;
            packet.session_id = queued.session_id;
            packet.status =
                make_status(queued.command.request_id, code, detail);
            enqueue(std::move(packet));
        }

        void emit_status(const QueuedCommand& queued,
                         StatusCode code,
                         std::string detail)
        {
            OutboundPacket packet;
            packet.session_id = queued.session_id;
            packet.status = make_status(
                queued.command.request_id, code, std::move(detail));
            enqueue(std::move(packet));
        }

        void emit_lifecycle_status(std::string detail)
        {
            const std::uint64_t session =
                active_session.load(std::memory_order_acquire);
            if (session == 0)
                return;
            OutboundPacket packet;
            packet.session_id = session;
            packet.status =
                make_status(0, StatusCode::completed, std::move(detail));
            enqueue(std::move(packet));
        }

        bool configure_capture_selector(const QueuedCommand& queued,
                                        std::uint32_t max_long_edge)
        {
            const Command& command = queued.command;
            if (command.target_id != topology.selected_target_id)
            {
                reject_command(queued,
                               StatusCode::target_unavailable,
                               "capture target must be selected first");
                return false;
            }
            debugger->set_capture_max_long_edge(max_long_edge);
            if (command.selector_kind == CaptureSelectorKind::resource)
            {
                if (std::find(topology.resources.begin(),
                              topology.resources.end(),
                              command.resource) == topology.resources.end())
                {
                    reject_command(queued,
                                   StatusCode::resource_unavailable,
                                   "capture resource is absent from topology");
                    return false;
                }
                debugger->request_resource(command.resource);
                return true;
            }
            const auto pass = std::find_if(
                topology.passes.begin(),
                topology.passes.end(),
                [&command](const WirePass& value)
                { return value.id == command.pass_id; });
            if (pass != topology.passes.end() &&
                std::find(pass->internal_symbols.begin(),
                          pass->internal_symbols.end(),
                          command.symbol) != pass->internal_symbols.end() &&
                debugger->request_internal(pass->authored_index,
                                           command.symbol))
            {
                return true;
            }
            reject_command(queued,
                           StatusCode::resource_unavailable,
                           "capture selector is unavailable");
            return false;
        }

        bool issue_capture(const QueuedCommand& queued,
                           CaptureKind kind,
                           std::uint16_t burst_index = 0,
                           std::uint16_t burst_count = 0,
                           bool announce = false)
        {
            if (pending_capture)
            {
                if (announce)
                {
                    reject_command(queued,
                                   StatusCode::limit_exceeded,
                                   "a framegraph capture is already pending");
                }
                return false;
            }
            const CaptureEncoding required = kind == CaptureKind::preview
                ? CaptureEncoding::rgba8
                : CaptureEncoding::native_pixels;
            if (queued.command.encoding != required)
            {
                reject_command(
                    queued,
                    StatusCode::limit_exceeded,
                    kind == CaptureKind::preview
                        ? "preview capture requires rgba8 encoding"
                        : "exact capture requires native_pixels encoding");
                return false;
            }
            const std::uint32_t max_long_edge = kind == CaptureKind::preview
                ? queued.command.max_preview_long_edge
                : 0;
            if (!configure_capture_selector(queued, max_long_edge))
                return false;
            pending_capture = PendingCapture{queued,
                                             debugger->request_generation(),
                                             Clock::now(),
                                             kind,
                                             burst_index,
                                             burst_count};
            if (announce)
            {
                emit_status(queued,
                            StatusCode::accepted,
                            kind == CaptureKind::snapshot
                                ? "exact capture accepted"
                                : kind == CaptureKind::preview
                                    ? "live preview accepted"
                                    : "burst capture accepted");
            }
            return true;
        }

        bool begin_capture(const QueuedCommand& queued)
        {
            if (stream || burst)
            {
                reject_command(queued,
                               StatusCode::limit_exceeded,
                               "continuous capture operation is active");
                return false;
            }
            return issue_capture(queued, CaptureKind::snapshot, 0, 0, true);
        }

        void reset_pending_capture()
        {
            if (debugger)
            {
                debugger->cancel_request();
                debugger->set_capture_max_long_edge(0);
            }
            pending_capture.reset();
        }

        void finish_operation(StatusCode code, std::string detail)
        {
            if (!pending_capture)
                return;
            const PendingCapture pending = *pending_capture;
            reset_pending_capture();
            if (pending.kind == CaptureKind::preview && stream)
            {
                emit_status(stream->queued, code, std::move(detail));
                stream.reset();
                clear_ready_preview();
                return;
            }
            if (pending.kind == CaptureKind::burst && burst)
            {
                emit_status(burst->queued, code, std::move(detail));
                burst.reset();
                return;
            }
            emit_status(pending.queued, code, std::move(detail));
        }

        std::chrono::nanoseconds preview_interval() const
        {
            if (!stream || stream->queued.command.max_preview_millifps == 0)
                return std::chrono::seconds(1);
            return std::chrono::nanoseconds(
                1'000'000'000'000ULL /
                stream->queued.command.max_preview_millifps);
        }

        void schedule_continuous_capture()
        {
            if (pending_capture)
                return;
            if (stream)
            {
                if (Clock::now() < stream->next_capture_at)
                    return;
                if (!issue_capture(stream->queued, CaptureKind::preview))
                {
                    emit_status(stream->queued,
                                StatusCode::resource_unavailable,
                                "live preview selector became unavailable");
                    stream.reset();
                }
                return;
            }
            if (burst)
            {
                if (!issue_capture(burst->queued,
                                   CaptureKind::burst,
                                   burst->next_index,
                                   burst->queued.command.burst_frames))
                {
                    emit_status(burst->queued,
                                StatusCode::resource_unavailable,
                                "burst selector became unavailable");
                    burst.reset();
                }
            }
        }

        void poll_capture()
        {
            if (!pending_capture)
                return;
            if (active_session.load(std::memory_order_acquire) !=
                pending_capture->queued.session_id)
            {
                reset_pending_capture();
                stream.reset();
                burst.reset();
                clear_ready_preview();
                return;
            }
            if (!refresh_topology())
            {
                finish_operation(StatusCode::resource_unavailable,
                                 "topology refresh failed during capture");
                return;
            }
            if (graph_revision !=
                pending_capture->queued.command.graph_revision)
            {
                finish_operation(StatusCode::stale_revision,
                                 "topology changed while capture was pending");
                return;
            }
            debugger->finish_frame();
            if (debugger->request_generation() !=
                pending_capture->debugger_generation)
            {
                finish_operation(
                    StatusCode::cancelled,
                    "capture was superseded by local debugger state");
                return;
            }
            if (debugger->capture_status() ==
                FrameGraphCaptureRequestStatus::ResourceUnavailable)
            {
                finish_operation(StatusCode::resource_unavailable,
                                 "capture resource became unavailable");
                return;
            }
            if (debugger->state() != FrameGraphDebuggerState::Captured)
                return;

            const FrameGraphCapture& capture = debugger->capture();
            if (!capture.has_capture() || capture.width() <= 0 ||
                capture.height() <= 0)
            {
                finish_operation(
                    StatusCode::resource_unavailable,
                    "capture completed without a readable texture");
                return;
            }
            const PendingCapture pending = *pending_capture;
            const std::uint64_t pixels =
                static_cast<std::uint64_t>(capture.width()) *
                static_cast<std::uint64_t>(capture.height());
            const bool depth = capture.is_depth();
            const bool source_rgba8 = !depth &&
                (capture.format() == tgfx::PixelFormat::RGBA8_UNorm ||
                 capture.format() == tgfx::PixelFormat::RGBA8_sRGB ||
                 capture.format() == tgfx::PixelFormat::BGRA8_UNorm ||
                 capture.format() == tgfx::PixelFormat::BGRA8_sRGB);
            const bool preview = pending.kind == CaptureKind::preview;
            const std::uint64_t output_bytes = preview
                ? pixels * 4ULL
                : pixels * (source_rgba8 ? 4ULL
                                         : depth ? sizeof(float)
                                                 : 4ULL * sizeof(float));
            const std::uint64_t temporary_bytes =
                pixels * (depth ? sizeof(float) : 4ULL * sizeof(float));
            const std::uint64_t peer_limit = std::min(
                pending.queued.max_blob_bytes,
                config.capture_memory_budget_bytes);
            if (preview)
                discard_obsolete_preview();
            const std::uint64_t already_queued =
                queued_capture_bytes.load(std::memory_order_relaxed);
            if (output_bytes > peer_limit ||
                temporary_bytes > peer_limit - output_bytes ||
                already_queued >
                    peer_limit - output_bytes - temporary_bytes ||
                (pending.kind == CaptureKind::burst && burst &&
                 burst->retained_bytes > peer_limit - output_bytes))
            {
                tc_log_error("remote framegraph target: capture exceeds "
                             "memory/peer budget (%llu bytes)",
                             static_cast<unsigned long long>(output_bytes));
                if (preview)
                {
                    dropped_captures.fetch_add(1, std::memory_order_relaxed);
                    note_preview_drop();
                    reset_pending_capture();
                    if (stream)
                        stream->next_capture_at = Clock::now() +
                            preview_interval();
                    return;
                }
                finish_operation(StatusCode::limit_exceeded,
                                 "capture exceeds memory or peer budget");
                return;
            }

            auto blob = std::make_shared<CaptureBlob>();
            const auto readback_started = Clock::now();
            std::vector<float> values;
            const bool read = depth ? capture.read_depth_float(values)
                                    : capture.read_color_rgba_float(values);
            const std::uint64_t elapsed = static_cast<std::uint64_t>(
                std::chrono::duration_cast<std::chrono::nanoseconds>(
                    Clock::now() - readback_started).count());
            if (!read)
            {
                finish_operation(StatusCode::resource_unavailable,
                                 "GPU readback failed");
                return;
            }
            const auto conversion_started = Clock::now();
            blob->bytes.resize(static_cast<std::size_t>(output_bytes));
            if (preview && depth)
            {
                for (std::uint64_t pixel = 0; pixel < pixels; ++pixel)
                {
                    const auto value = static_cast<std::uint8_t>(std::lround(
                        std::clamp(values[static_cast<std::size_t>(pixel)],
                                   0.0F,
                                   1.0F) * 255.0F));
                    const std::size_t offset =
                        static_cast<std::size_t>(pixel) * 4;
                    blob->bytes[offset] = value;
                    blob->bytes[offset + 1] = value;
                    blob->bytes[offset + 2] = value;
                    blob->bytes[offset + 3] = 255;
                }
            }
            else if (preview || source_rgba8)
            {
                std::transform(values.begin(), values.end(),
                               blob->bytes.begin(),
                               [](float value)
                               {
                                   const float bounded =
                                       std::clamp(value, 0.0F, 1.0F);
                                   return static_cast<std::uint8_t>(
                                       std::lround(bounded * 255.0F));
                               });
            }
            else
            {
                std::memcpy(blob->bytes.data(),
                            values.data(),
                            blob->bytes.size());
            }
            const std::uint64_t conversion_elapsed =
                static_cast<std::uint64_t>(
                    std::chrono::duration_cast<std::chrono::nanoseconds>(
                        Clock::now() - conversion_started).count());
            const std::uint32_t chunk_bytes = std::min(
                pending.queued.max_chunk_bytes,
                WireLimits::max_chunk_bytes);
            if (chunk_bytes == 0)
            {
                finish_operation(StatusCode::limit_exceeded,
                                 "capture chunk size is zero");
                return;
            }
            const std::uint64_t chunks64 =
                (output_bytes + chunk_bytes - 1) / chunk_bytes;
            if (chunks64 == 0 ||
                chunks64 > WireLimits::max_chunks_per_blob)
            {
                finish_operation(
                    StatusCode::limit_exceeded,
                    "capture chunk count exceeds protocol limits");
                return;
            }
            const std::uint64_t capture_elapsed =
                static_cast<std::uint64_t>(
                    std::chrono::duration_cast<std::chrono::nanoseconds>(
                        Clock::now() - pending.requested_at).count());
            blob->session_id = pending.queued.session_id;
            blob->chunk_bytes = chunk_bytes;
            blob->metadata = {
                pending.queued.command.request_id,
                graph_revision,
                next_blob_id++,
                next_capture_frame_number++,
                pending.kind,
                preview ? CaptureEncoding::rgba8
                        : CaptureEncoding::native_pixels,
                preview ? PixelFormat::rgba8_unorm
                        : depth ? PixelFormat::depth32_float
                                : source_rgba8 ? PixelFormat::rgba8_unorm
                                               : PixelFormat::rgba32_float,
                static_cast<std::uint32_t>(capture.width()),
                static_cast<std::uint32_t>(capture.height()),
                preview ? false : depth,
                !preview,
                output_bytes,
                static_cast<std::uint32_t>(chunks64),
                pending.burst_index,
                pending.burst_count,
            };
            readback_time_ns.fetch_add(elapsed, std::memory_order_relaxed);
            conversion_time_ns.fetch_add(conversion_elapsed,
                                         std::memory_order_relaxed);
            capture_time_ns.fetch_add(capture_elapsed,
                                      std::memory_order_relaxed);
            captured_bytes.fetch_add(output_bytes, std::memory_order_relaxed);
            completed_captures.fetch_add(1, std::memory_order_relaxed);
            reset_pending_capture();

            if (preview)
            {
                preview_captures.fetch_add(1, std::memory_order_relaxed);
                publish_ready_preview(std::move(blob));
                if (stream)
                {
                    ++stream->delivered_frames;
                    stream->next_capture_at = Clock::now() +
                        preview_interval();
                }
                return;
            }

            queued_capture_bytes.fetch_add(output_bytes,
                                           std::memory_order_relaxed);
            OutboundPacket packet;
            packet.session_id = pending.queued.session_id;
            packet.capture = std::move(blob);
            if (pending.kind == CaptureKind::burst && burst)
            {
                burst_captures.fetch_add(1, std::memory_order_relaxed);
                burst->retained_bytes += output_bytes;
                ++burst->next_index;
                if (burst->next_index == burst->queued.command.burst_frames)
                {
                    packet.status = make_status(
                        burst->queued.command.request_id,
                        StatusCode::completed,
                        "burst completed; frames=" +
                            std::to_string(burst->next_index) +
                            "; bytes=" +
                            std::to_string(burst->retained_bytes) +
                            "; last_readback_ns=" + std::to_string(elapsed));
                    burst.reset();
                }
            }
            else
            {
                packet.status = make_status(
                    pending.queued.command.request_id,
                    StatusCode::completed,
                    "exact capture completed; readback_ns=" +
                        std::to_string(elapsed) + "; bytes=" +
                        std::to_string(output_bytes) + "; capture_ns=" +
                        std::to_string(capture_elapsed));
            }
            enqueue(std::move(packet));
        }

        void apply_command(const QueuedCommand& queued)
        {
            const Command& command = queued.command;
            if (!debugger && command.kind != CommandKind::refresh_topology &&
                command.kind != CommandKind::request_status &&
                command.kind != CommandKind::ping &&
                command.kind != CommandKind::disconnect)
            {
                reject_command(queued,
                               StatusCode::resource_unavailable,
                               "render runtime is not attached");
                return;
            }
            const auto validation = validate_command(command, graph_revision);
            if (!validation)
            {
                if (validation.error == SelectorError::stale_revision)
                {
                    reject_command(
                        queued, StatusCode::stale_revision, validation.detail);
                }
                else
                {
                    OutboundPacket packet;
                    packet.session_id = queued.session_id;
                    packet.error = ErrorEvent{422,
                                              command.request_id,
                                              graph_revision,
                                              validation.detail};
                    enqueue(std::move(packet));
                }
                return;
            }

            if (command.kind == CommandKind::refresh_topology)
            {
                OutboundPacket packet;
                packet.session_id = queued.session_id;
                if (refresh_topology())
                {
                    packet.topology = topology;
                    packet.status = make_status(command.request_id,
                                                StatusCode::completed,
                                                "topology refreshed");
                }
                else
                {
                    packet.status = make_status(command.request_id,
                                                StatusCode::limit_exceeded,
                                                topology_error);
                }
                enforce_peer_payload_limit(packet, queued);
                enqueue(std::move(packet));
                return;
            }

            if (command.kind == CommandKind::select_target)
            {
                const auto binding =
                    std::find_if(target_bindings.begin(),
                                 target_bindings.end(),
                                 [&command](const auto& item)
                                 { return item.id == command.target_id; });
                if (binding == target_bindings.end() ||
                    !debugger->select_target(binding->native_id))
                {
                    reject_command(queued,
                                   StatusCode::target_unavailable,
                                   "selected target is unavailable");
                    return;
                }
                OutboundPacket packet;
                packet.session_id = queued.session_id;
                if (refresh_topology())
                {
                    packet.topology = topology;
                    packet.status = make_status(command.request_id,
                                                StatusCode::completed,
                                                "target selected");
                }
                else
                {
                    packet.status = make_status(command.request_id,
                                                StatusCode::limit_exceeded,
                                                topology_error);
                }
                enforce_peer_payload_limit(packet, queued);
                enqueue(std::move(packet));
                return;
            }

            if (command.kind == CommandKind::request_status ||
                command.kind == CommandKind::ping)
            {
                OutboundPacket packet;
                packet.session_id = queued.session_id;
                packet.status = make_status(
                    command.request_id,
                    StatusCode::completed,
                    command.kind == CommandKind::ping ? "pong" : "status");
                enqueue(std::move(packet));
                return;
            }

            if (command.kind == CommandKind::capture_snapshot)
            {
                begin_capture(queued);
                return;
            }

            if (command.kind == CommandKind::start_stream ||
                command.kind == CommandKind::update_stream)
            {
                if (burst || (pending_capture &&
                    pending_capture->kind != CaptureKind::preview))
                {
                    reject_command(queued,
                                   StatusCode::limit_exceeded,
                                   "another capture operation is active");
                    return;
                }
                if (command.kind == CommandKind::update_stream && !stream)
                {
                    emit_status(queued,
                                StatusCode::completed,
                                "live preview is already stopped");
                    return;
                }
                if (stream)
                {
                    const QueuedCommand previous = stream->queued;
                    if (pending_capture)
                    {
                        dropped_captures.fetch_add(
                            1, std::memory_order_relaxed);
                        reset_pending_capture();
                    }
                    discard_obsolete_preview();
                    emit_status(previous,
                                StatusCode::completed,
                                "live preview configuration replaced");
                }
                stream = StreamState{
                    queued, Clock::now(), Clock::now(), 0};
                emit_status(queued,
                            StatusCode::accepted,
                            command.kind == CommandKind::start_stream
                                ? "live preview started"
                                : "live preview updated");
                return;
            }

            if (command.kind == CommandKind::stop_stream)
            {
                if (!stream)
                {
                    emit_status(queued,
                                StatusCode::completed,
                                "live preview is already stopped");
                    return;
                }
                const StreamState stopped = *stream;
                if (pending_capture &&
                    pending_capture->kind == CaptureKind::preview)
                {
                    reset_pending_capture();
                }
                stream.reset();
                clear_ready_preview();
                const auto elapsed_ns = std::max<std::uint64_t>(
                    1,
                    static_cast<std::uint64_t>(
                        std::chrono::duration_cast<std::chrono::nanoseconds>(
                            Clock::now() - stopped.started_at).count()));
                const std::uint64_t effective_millifps =
                    stopped.delivered_frames * 1'000'000'000'000ULL /
                    elapsed_ns;
                effective_preview_millifps.store(
                    effective_millifps, std::memory_order_relaxed);
                emit_status(stopped.queued,
                            StatusCode::completed,
                            "live preview stopped; frames=" +
                                std::to_string(stopped.delivered_frames) +
                                "; effective_millifps=" +
                                std::to_string(effective_millifps) +
                                "; readback_ns=" +
                                std::to_string(readback_time_ns.load(
                                    std::memory_order_relaxed)) +
                                "; convert_ns=" +
                                std::to_string(conversion_time_ns.load(
                                    std::memory_order_relaxed)) +
                                "; bytes=" +
                                std::to_string(captured_bytes.load(
                                    std::memory_order_relaxed)) +
                                "; dropped=" +
                                std::to_string(dropped_captures.load(
                                    std::memory_order_relaxed)));
                emit_status(queued,
                            StatusCode::completed,
                            "live preview stop processed");
                return;
            }

            if (command.kind == CommandKind::capture_burst)
            {
                if (pending_capture || stream || burst)
                {
                    reject_command(queued,
                                   StatusCode::limit_exceeded,
                                   "another capture operation is active");
                    return;
                }
                const std::size_t required_slots =
                    outbound_queue.size_approximate() +
                    static_cast<std::size_t>(command.burst_frames) + 1;
                if (required_slots > outbound_queue.capacity())
                {
                    reject_command(
                        queued,
                        StatusCode::limit_exceeded,
                        "burst exceeds the target outbound queue capacity");
                    return;
                }
                if (command.encoding != CaptureEncoding::native_pixels)
                {
                    reject_command(queued,
                                   StatusCode::limit_exceeded,
                                   "burst capture requires native_pixels");
                    return;
                }
                burst = BurstState{queued, 0, 0};
                emit_status(queued,
                            StatusCode::accepted,
                            "burst capture accepted; frames=" +
                                std::to_string(command.burst_frames));
                return;
            }

            if (command.kind == CommandKind::cancel)
            {
                if (pending_capture)
                {
                    finish_operation(StatusCode::cancelled,
                                     "capture operation cancelled");
                    OutboundPacket acknowledgement;
                    acknowledgement.session_id = queued.session_id;
                    acknowledgement.status = make_status(
                        command.request_id,
                        StatusCode::cancelled,
                        "capture cancellation processed");
                    enqueue(std::move(acknowledgement));
                    return;
                }
                if (stream)
                {
                    emit_status(stream->queued,
                                StatusCode::cancelled,
                                "live preview cancelled");
                    stream.reset();
                    clear_ready_preview();
                    emit_status(queued,
                                StatusCode::cancelled,
                                "capture cancellation processed");
                    return;
                }
                else if (burst)
                {
                    emit_status(burst->queued,
                                StatusCode::cancelled,
                                "burst capture cancelled");
                    burst.reset();
                    emit_status(queued,
                                StatusCode::cancelled,
                                "capture cancellation processed");
                    return;
                }
                OutboundPacket packet;
                packet.session_id = queued.session_id;
                packet.status =
                    make_status(command.request_id,
                                StatusCode::cancelled,
                                "no topology operation was pending");
                enqueue(std::move(packet));
                return;
            }
        }

        bool send_wire(
            Socket socket,
            const Message& message,
            std::uint64_t& sequence,
            std::uint64_t session_id,
            std::uint32_t max_payload_bytes = WireLimits::max_payload_bytes)
        {
            auto encoded = encode_message(message, sequence++, session_id);
            if (!encoded)
            {
                tc_log_error(
                    "remote framegraph target: failed to encode message: %s",
                    encoded.detail.c_str());
                return false;
            }
            if (encoded.value->size() - envelope_size > max_payload_bytes)
            {
                tc_log_error(
                    "remote framegraph target: encoded message exceeds the "
                    "negotiated payload limit (%u bytes)",
                    max_payload_bytes);
                return false;
            }
            const bool sent = send_bytes(socket, *encoded.value, running);
            if (sent)
            {
                transmitted_bytes.fetch_add(encoded.value->size(),
                                            std::memory_order_relaxed);
            }
            return sent;
        }

        bool handshake(Socket socket,
                       std::uint64_t& sequence,
                       std::uint64_t session_id,
                       std::uint32_t& negotiated_payload_bytes,
                       std::uint64_t& negotiated_blob_bytes,
                       std::uint32_t& negotiated_chunk_bytes)
        {
            auto decoded = receive_message(socket, running);
            if (!decoded ||
                !std::holds_alternative<ClientHello>(decoded.value->message))
            {
                tc_log_error(
                    "remote framegraph target: client handshake is malformed");
                return false;
            }
            const ClientHello& hello =
                std::get<ClientHello>(decoded.value->message);
            const bool version_ok = hello.minimum_major == protocol_major &&
                                    hello.minimum_minor <= protocol_minor;
            if (!version_ok ||
                !constant_time_equal(hello.authentication_token,
                                     config.authentication_token))
            {
                const std::string detail =
                    !version_ok ? "client version range is incompatible"
                                : "client authentication token is invalid";
                send_wire(socket,
                          ErrorEvent{401,
                                     0,
                                     published_graph_revision.load(
                                         std::memory_order_acquire),
                                     detail},
                          sequence,
                          session_id);
                tc_log_error("remote framegraph target: rejected client: %s",
                             detail.c_str());
                return false;
            }
            TargetHello target;
            target.capabilities =
                static_cast<std::uint64_t>(Capability::topology) |
                static_cast<std::uint64_t>(Capability::exact_snapshot) |
                static_cast<std::uint64_t>(Capability::live_preview) |
                static_cast<std::uint64_t>(Capability::burst_capture) |
                static_cast<std::uint64_t>(Capability::hdr_pixels) |
                static_cast<std::uint64_t>(Capability::depth_pixels);
            target.process_id = config.process_id;
            target.max_payload_bytes = std::min(hello.max_payload_bytes,
                                                WireLimits::max_payload_bytes);
            target.max_blob_bytes =
                std::min(hello.max_blob_bytes, WireLimits::max_blob_bytes);
            target.max_chunk_bytes =
                std::min({hello.max_chunk_bytes,
                          WireLimits::max_chunk_bytes,
                          target.max_payload_bytes > 64
                              ? target.max_payload_bytes - 64
                              : 0U});
            target.platform = config.platform;
            target.abi = config.abi;
            target.build_type = config.build_type;
            target.build_id = config.build_id;
            negotiated_payload_bytes = target.max_payload_bytes;
            negotiated_blob_bytes = target.max_blob_bytes;
            negotiated_chunk_bytes = target.max_chunk_bytes;
            return send_wire(
                socket, target, sequence, session_id, negotiated_payload_bytes);
        }

        bool send_packet(Socket socket,
                         const OutboundPacket& packet,
                         std::uint64_t& sequence,
                         std::uint64_t session_id,
                         std::uint32_t max_payload_bytes)
        {
            std::uint64_t capture_transfer_ns = 0;
            if (packet.session_id != session_id)
            {
                if (packet.capture)
                    queued_capture_bytes.fetch_sub(packet.capture->bytes.size(),
                                                   std::memory_order_relaxed);
                return true;
            }
            if (packet.drop && !send_wire(socket,
                                          *packet.drop,
                                          sequence,
                                          session_id,
                                          max_payload_bytes))
                return false;
            if (packet.error && !send_wire(socket,
                                           *packet.error,
                                           sequence,
                                           session_id,
                                           max_payload_bytes))
                return false;
            if (packet.topology && !send_wire(socket,
                                              *packet.topology,
                                              sequence,
                                              session_id,
                                              max_payload_bytes))
                return false;
            if (packet.capture)
            {
                const auto transfer_started = Clock::now();
                const CaptureBlob& capture = *packet.capture;
                bool sent = send_wire(socket,
                                      capture.metadata,
                                      sequence,
                                      session_id,
                                      max_payload_bytes);
                for (std::uint32_t index = 0;
                     sent && index < capture.metadata.chunk_count;
                     ++index)
                {
                    const std::uint64_t offset =
                        static_cast<std::uint64_t>(index) *
                        capture.chunk_bytes;
                    const std::size_t count = static_cast<std::size_t>(
                        std::min<std::uint64_t>(capture.chunk_bytes,
                            capture.bytes.size() - offset));
                    BlobChunk chunk;
                    chunk.blob_id = capture.metadata.blob_id;
                    chunk.chunk_index = index;
                    chunk.chunk_count = capture.metadata.chunk_count;
                    chunk.offset = offset;
                    chunk.total_bytes = capture.bytes.size();
                    chunk.bytes.assign(capture.bytes.begin() + offset,
                                       capture.bytes.begin() + offset + count);
                    sent = send_wire(socket,
                                     chunk,
                                     sequence,
                                     session_id,
                                     max_payload_bytes);
                }
                queued_capture_bytes.fetch_sub(capture.bytes.size(),
                                               std::memory_order_relaxed);
                capture_transfer_ns = static_cast<std::uint64_t>(
                    std::chrono::duration_cast<std::chrono::nanoseconds>(
                        Clock::now() - transfer_started).count());
                transfer_encode_time_ns.fetch_add(capture_transfer_ns,
                                                  std::memory_order_relaxed);
                if (!sent)
                    return false;
            }
            if (packet.status)
            {
                Status status = *packet.status;
                if (capture_transfer_ns != 0)
                    status.detail += "; transfer_encode_ns=" +
                        std::to_string(capture_transfer_ns);
                if (!send_wire(socket,
                               status,
                               sequence,
                               session_id,
                               max_payload_bytes))
                    return false;
            }
            return true;
        }

        void io_main()
        {
            while (running.load(std::memory_order_acquire))
            {
                const Socket listener =
                    listener_socket.load(std::memory_order_acquire);
                if (listener == invalid_socket)
                    break;
                const WaitResult wait =
                    wait_socket(listener, false, std::chrono::milliseconds(50));
                if (wait == WaitResult::timeout)
                    continue;
                if (wait == WaitResult::failed)
                {
                    if (running.load(std::memory_order_acquire))
                    {
                        tc_log_error(
                            "remote framegraph target: listener wait failed");
                    }
                    break;
                }
                sockaddr_in peer{};
#if defined(_WIN32)
                int peer_size = sizeof(peer);
#else
                socklen_t peer_size = sizeof(peer);
#endif
                const Socket client = accept(
                    listener, reinterpret_cast<sockaddr*>(&peer), &peer_size);
                if (client == invalid_socket)
                    continue;
                if (ntohl(peer.sin_addr.s_addr) != INADDR_LOOPBACK ||
                    !set_nonblocking(client))
                {
                    tc_log_error("remote framegraph target: rejected "
                                 "non-loopback client");
                    rejected_clients.fetch_add(1, std::memory_order_relaxed);
                    close_socket(client);
                    continue;
                }
                client_socket.store(client, std::memory_order_release);
                const std::uint64_t session_id =
                    next_session_id.fetch_add(1, std::memory_order_relaxed);
                std::uint64_t sequence = 1;
                std::uint32_t max_payload_bytes = WireLimits::max_payload_bytes;
                std::uint64_t max_blob_bytes = WireLimits::max_blob_bytes;
                std::uint32_t max_chunk_bytes = WireLimits::max_chunk_bytes;
                if (!handshake(client,
                               sequence,
                               session_id,
                               max_payload_bytes,
                               max_blob_bytes,
                               max_chunk_bytes))
                {
                    rejected_clients.fetch_add(1, std::memory_order_relaxed);
                    release_client(client);
                    continue;
                }
                active_session.store(session_id, std::memory_order_release);
                client_connected.store(true, std::memory_order_release);
                tc_log_info(
                    "remote framegraph target: client connected (session=%llu)",
                    static_cast<unsigned long long>(session_id));
                serve_client(client,
                             sequence,
                             session_id,
                             max_payload_bytes,
                             max_blob_bytes,
                             max_chunk_bytes);
                client_connected.store(false, std::memory_order_release);
                active_session.store(0, std::memory_order_release);
                release_client(client);
                tc_log_info("remote framegraph target: client disconnected "
                            "(session=%llu)",
                            static_cast<unsigned long long>(session_id));
            }
        }

        void serve_client(Socket socket,
                          std::uint64_t sequence,
                          std::uint64_t session_id,
                          std::uint32_t max_payload_bytes,
                          std::uint64_t max_blob_bytes,
                          std::uint32_t max_chunk_bytes)
        {
            while (running.load(std::memory_order_acquire))
            {
                OutboundPacket packet;
                while (outbound_queue.try_pop(packet))
                {
                    if (!send_packet(socket,
                                     packet,
                                     sequence,
                                     session_id,
                                     max_payload_bytes))
                        return;
                }
                if (auto preview = take_ready_preview())
                {
                    OutboundPacket preview_packet;
                    preview_packet.session_id = preview->value->session_id;
                    if (preview->dropped_before != 0)
                    {
                        preview_packet.drop = DropEvent{
                            DropKind::receiver,
                            preview->dropped_before,
                            preview->value->metadata.frame_number,
                            sequence};
                    }
                    preview_packet.capture = std::move(preview->value);
                    if (!send_packet(socket,
                                     preview_packet,
                                     sequence,
                                     session_id,
                                     max_payload_bytes))
                        return;
                }
                const WaitResult wait =
                    wait_socket(socket, false, std::chrono::milliseconds(10));
                if (wait == WaitResult::timeout)
                    continue;
                if (wait == WaitResult::failed)
                    return;
                auto decoded = receive_message(socket, running);
                if (!decoded)
                {
                    if (decoded.detail !=
                        "connection closed while receiving envelope")
                    {
                        tc_log_error("remote framegraph target: malformed "
                                     "client message: %s",
                                     decoded.detail.c_str());
                    }
                    return;
                }
                if (decoded.value->envelope.session_id != session_id)
                {
                    const std::uint64_t revision =
                        published_graph_revision.load(
                            std::memory_order_acquire);
                    if (!send_wire(
                            socket,
                            ErrorEvent{
                                409,
                                0,
                                revision,
                                "message session_id does not match connection"},
                            sequence,
                            session_id,
                            max_payload_bytes))
                        return;
                    continue;
                }
                if (!std::holds_alternative<Command>(decoded.value->message))
                {
                    const std::uint64_t revision =
                        published_graph_revision.load(
                            std::memory_order_acquire);
                    if (!send_wire(socket,
                                   ErrorEvent{400,
                                              0,
                                              revision,
                                              "only Command messages are "
                                              "accepted after handshake"},
                                   sequence,
                                   session_id,
                                   max_payload_bytes))
                        return;
                    continue;
                }
                const Command& command =
                    std::get<Command>(decoded.value->message);
                if (command.kind == CommandKind::disconnect)
                {
                    const std::uint64_t revision =
                        published_graph_revision.load(
                            std::memory_order_acquire);
                    Status status{command.request_id,
                                  revision,
                                  SessionState::idle,
                                  StatusCode::completed,
                                  static_cast<std::uint32_t>(
                                      outbound_queue.size_approximate()),
                                  0,
                                  dropped_outbound_messages.load(
                                      std::memory_order_relaxed),
                                  now_ns(),
                                  "disconnecting"};
                    send_wire(socket,
                              status,
                              sequence,
                              session_id,
                              max_payload_bytes);
                    return;
                }
                    if (!command_queue.try_push({session_id,
                                                 max_payload_bytes,
                                                 max_blob_bytes,
                                                 max_chunk_bytes,
                                                 command}))
                {
                    rejected_commands.fetch_add(1, std::memory_order_relaxed);
                    tc_log_error("remote framegraph target: command queue "
                                 "full; command rejected");
                    const std::uint64_t revision =
                        published_graph_revision.load(
                            std::memory_order_acquire);
                    if (!send_wire(socket,
                                   ErrorEvent{429,
                                              command.request_id,
                                              revision,
                                              "target command queue is full"},
                                   sequence,
                                   session_id,
                                   max_payload_bytes))
                        return;
                }
            }
        }

        void release_client(Socket socket)
        {
            Socket expected = socket;
            if (client_socket.compare_exchange_strong(
                    expected, invalid_socket, std::memory_order_acq_rel))
            {
                shutdown_socket(socket);
                close_socket(socket);
            }
        }

        FrameGraphDebugger* debugger = nullptr;
        TargetServiceConfig config;
        BoundedSpscQueue<QueuedCommand> command_queue;
        BoundedSpscQueue<OutboundPacket> outbound_queue;
        std::thread::id owner_thread;
        std::thread io_thread;
        std::atomic<bool> running{false};
        std::atomic<bool> client_connected{false};
        std::atomic<bool> debugger_attached{false};
        std::atomic<Socket> listener_socket{invalid_socket};
        std::atomic<Socket> client_socket{invalid_socket};
        std::atomic<std::uint16_t> listening_port{0};
        std::atomic<std::uint64_t> next_session_id{1};
        std::atomic<std::uint64_t> active_session{0};
        std::atomic<std::uint64_t> published_graph_revision{0};
        std::atomic<std::uint64_t> rejected_clients{0};
        std::atomic<std::uint64_t> rejected_commands{0};
        std::atomic<std::uint64_t> dropped_outbound_messages{0};
        std::atomic<std::uint64_t> transmitted_bytes{0};
        TopologySnapshot topology;
        std::vector<TargetBinding> target_bindings;
        std::uint64_t next_target_id = 1;
        std::uint64_t graph_revision = 0;
        std::uint64_t pending_dropped_outbound = 0;
        std::int64_t pending_dropped_after_frame = 0;
        std::optional<PendingCapture> pending_capture;
        std::optional<StreamState> stream;
        std::optional<BurstState> burst;
        std::uint64_t next_blob_id = 1;
        std::int64_t next_capture_frame_number = 1;
        std::string topology_error;
        LatestValueSlot<std::shared_ptr<CaptureBlob>> preview_slot;
        std::atomic<std::uint64_t> queued_capture_bytes{0};
        std::atomic<std::uint64_t> completed_captures{0};
        std::atomic<std::uint64_t> dropped_captures{0};
        std::atomic<std::uint64_t> preview_captures{0};
        std::atomic<std::uint64_t> burst_captures{0};
        std::atomic<std::uint64_t> capture_time_ns{0};
        std::atomic<std::uint64_t> readback_time_ns{0};
        std::atomic<std::uint64_t> conversion_time_ns{0};
        std::atomic<std::uint64_t> transfer_encode_time_ns{0};
        std::atomic<std::uint64_t> captured_bytes{0};
        std::atomic<std::uint64_t> effective_preview_millifps{0};
#if defined(_WIN32)
        bool winsock_started = false;
#endif
    };

    RemoteFrameGraphTarget::RemoteFrameGraphTarget(TargetServiceConfig config)
        : impl_(std::make_unique<Impl>(nullptr, std::move(config)))
    {
    }

    RemoteFrameGraphTarget::RemoteFrameGraphTarget(FrameGraphDebugger& debugger,
                                                   TargetServiceConfig config)
        : impl_(std::make_unique<Impl>(&debugger, std::move(config)))
    {
    }

    RemoteFrameGraphTarget::~RemoteFrameGraphTarget() = default;

    bool RemoteFrameGraphTarget::start()
    {
        return impl_->start();
    }
    void RemoteFrameGraphTarget::stop()
    {
        impl_->stop();
    }
    bool RemoteFrameGraphTarget::attach_debugger(FrameGraphDebugger& debugger)
    {
        return impl_->attach_debugger(debugger);
    }
    void RemoteFrameGraphTarget::detach_debugger()
    {
        impl_->detach_debugger();
    }
    void RemoteFrameGraphTarget::pump_render_thread()
    {
        impl_->pump_render_thread();
    }
    TargetServiceStatus RemoteFrameGraphTarget::status() const
    {
        return impl_->status();
    }

} // namespace termin::framegraph_remote_target
