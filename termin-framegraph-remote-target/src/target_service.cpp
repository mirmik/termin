#include <termin/framegraph_remote_target/target_service.hpp>

#include <termin/framegraph_remote/wire_codec.hpp>
#include <termin/render/frame_graph_debugger.hpp>

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <limits>
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

        template <typename T> class BoundedSpscQueue
        {
        public:
            explicit BoundedSpscQueue(std::size_t capacity)
                : slots_(checked_size(capacity))
            {
            }

            bool try_push(T value)
            {
                const std::size_t tail = tail_.load(std::memory_order_relaxed);
                const std::size_t next = increment(tail);
                if (next == head_.load(std::memory_order_acquire))
                    return false;
                slots_[tail].emplace(std::move(value));
                tail_.store(next, std::memory_order_release);
                return true;
            }

            bool try_pop(T& value)
            {
                const std::size_t head = head_.load(std::memory_order_relaxed);
                if (head == tail_.load(std::memory_order_acquire))
                    return false;
                value = std::move(*slots_[head]);
                slots_[head].reset();
                head_.store(increment(head), std::memory_order_release);
                return true;
            }

            std::size_t size_approximate() const
            {
                const std::size_t head = head_.load(std::memory_order_acquire);
                const std::size_t tail = tail_.load(std::memory_order_acquire);
                return tail >= head ? tail - head : slots_.size() - head + tail;
            }

        private:
            static std::size_t checked_size(std::size_t capacity)
            {
                if (capacity == 0 ||
                    capacity == std::numeric_limits<std::size_t>::max())
                {
                    throw std::invalid_argument(
                        "framegraph target queue capacity is invalid");
                }
                return capacity + 1;
            }

            std::size_t increment(std::size_t value) const
            {
                return value + 1 == slots_.size() ? 0 : value + 1;
            }

            std::vector<std::optional<T>> slots_;
            alignas(64) std::atomic<std::size_t> head_{0};
            alignas(64) std::atomic<std::size_t> tail_{0};
        };

        struct QueuedCommand
        {
            std::uint64_t session_id = 0;
            std::uint32_t max_payload_bytes = WireLimits::max_payload_bytes;
            Command command;
        };

        struct OutboundPacket
        {
            std::uint64_t session_id = 0;
            std::optional<TopologySnapshot> topology;
            std::optional<Status> status;
            std::optional<DropEvent> drop;
            std::optional<ErrorEvent> error;
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
        Impl(FrameGraphDebugger& target_debugger,
             TargetServiceConfig target_config)
            : debugger(&target_debugger), config(std::move(target_config)),
              command_queue(config.command_queue_capacity),
              outbound_queue(config.outbound_queue_capacity),
              owner_thread(std::this_thread::get_id())
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
            pending_dropped_outbound = 0;
            tc_log_info("remote framegraph target: stopped");
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
        }

        TargetServiceStatus status() const
        {
            return {
                running.load(std::memory_order_acquire),
                client_connected.load(std::memory_order_acquire),
                listening_port.load(std::memory_order_acquire),
                active_session.load(std::memory_order_acquire),
                published_graph_revision.load(std::memory_order_acquire),
                rejected_clients.load(std::memory_order_relaxed),
                rejected_commands.load(std::memory_order_relaxed),
                dropped_outbound_messages.load(std::memory_order_relaxed),
                transmitted_bytes.load(std::memory_order_relaxed),
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
                project_state(debugger->state()),
                code,
                static_cast<std::uint32_t>(outbound_queue.size_approximate()),
                0,
                dropped_outbound_messages.load(std::memory_order_relaxed),
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
            if (pending_dropped_outbound != 0)
            {
                packet.drop = DropEvent{
                    DropKind::receiver, pending_dropped_outbound, 0, 0};
            }
            if (outbound_queue.try_push(std::move(packet)))
            {
                pending_dropped_outbound = 0;
                return;
            }
            ++pending_dropped_outbound;
            dropped_outbound_messages.fetch_add(1, std::memory_order_relaxed);
            tc_log_error("remote framegraph target: outbound queue full; "
                         "message dropped");
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

        void apply_command(const QueuedCommand& queued)
        {
            const Command& command = queued.command;
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

            if (command.kind == CommandKind::cancel)
            {
                OutboundPacket packet;
                packet.session_id = queued.session_id;
                packet.status =
                    make_status(command.request_id,
                                StatusCode::cancelled,
                                "no topology operation was pending");
                enqueue(std::move(packet));
                return;
            }

            OutboundPacket packet;
            packet.session_id = queued.session_id;
            packet.error = ErrorEvent{
                501,
                command.request_id,
                graph_revision,
                "capture commands are not enabled by the topology-only target"};
            enqueue(std::move(packet));
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
                       std::uint32_t& negotiated_payload_bytes)
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
                static_cast<std::uint64_t>(Capability::topology);
            target.process_id = config.process_id;
            target.max_payload_bytes = std::min(hello.max_payload_bytes,
                                                WireLimits::max_payload_bytes);
            target.max_blob_bytes =
                std::min(hello.max_blob_bytes, WireLimits::max_blob_bytes);
            target.max_chunk_bytes =
                std::min(hello.max_chunk_bytes, WireLimits::max_chunk_bytes);
            target.platform = config.platform;
            target.abi = config.abi;
            target.build_type = config.build_type;
            target.build_id = config.build_id;
            negotiated_payload_bytes = target.max_payload_bytes;
            return send_wire(
                socket, target, sequence, session_id, negotiated_payload_bytes);
        }

        bool send_packet(Socket socket,
                         const OutboundPacket& packet,
                         std::uint64_t& sequence,
                         std::uint64_t session_id,
                         std::uint32_t max_payload_bytes)
        {
            if (packet.session_id != session_id)
                return true;
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
            if (packet.status && !send_wire(socket,
                                            *packet.status,
                                            sequence,
                                            session_id,
                                            max_payload_bytes))
                return false;
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
                if (!handshake(client, sequence, session_id, max_payload_bytes))
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
                serve_client(client, sequence, session_id, max_payload_bytes);
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
                          std::uint32_t max_payload_bytes)
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
                if (!command_queue.try_push(
                        {session_id, max_payload_bytes, command}))
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
        std::string topology_error;
#if defined(_WIN32)
        bool winsock_started = false;
#endif
    };

    RemoteFrameGraphTarget::RemoteFrameGraphTarget(FrameGraphDebugger& debugger,
                                                   TargetServiceConfig config)
        : impl_(std::make_unique<Impl>(debugger, std::move(config)))
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
    void RemoteFrameGraphTarget::pump_render_thread()
    {
        impl_->pump_render_thread();
    }
    TargetServiceStatus RemoteFrameGraphTarget::status() const
    {
        return impl_->status();
    }

} // namespace termin::framegraph_remote_target
