#include <termin/profiler_remote/target_service.hpp>

#include <termin/profiler_remote/bounded_spsc_queue.hpp>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <climits>
#include <cstring>
#include <stdexcept>
#include <thread>
#include <unordered_map>
#include <unordered_set>
#include <utility>
#include <vector>

#include <tcbase/tc_log.h>

extern "C" {
#include <tc_profiler.h>
}

#if defined(_WIN32)
#define WIN32_LEAN_AND_MEAN
#include <winsock2.h>
#include <ws2tcpip.h>
#else
#include <arpa/inet.h>
#include <cerrno>
#include <fcntl.h>
#include <netinet/in.h>
#include <sys/select.h>
#include <sys/socket.h>
#include <unistd.h>
#endif

namespace termin::profiler_remote {
    namespace {

#if defined(_WIN32)
        using Socket = SOCKET;
        constexpr Socket invalid_socket = INVALID_SOCKET;
#else
        using Socket = int;
        constexpr Socket invalid_socket = -1;
#endif

        using Clock = std::chrono::steady_clock;

        std::uint64_t now_ns() {
            return static_cast<std::uint64_t>(
                std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now().time_since_epoch()).count());
        }

        void close_socket(Socket socket) {
            if (socket == invalid_socket) {
                return;
            }
#if defined(_WIN32)
            closesocket(socket);
#else
            close(socket);
#endif
        }

        void shutdown_socket(Socket socket) {
            if (socket == invalid_socket) {
                return;
            }
#if defined(_WIN32)
            shutdown(socket, SD_BOTH);
#else
            shutdown(socket, SHUT_RDWR);
#endif
        }

        int socket_error() {
#if defined(_WIN32)
            return WSAGetLastError();
#else
            return errno;
#endif
        }

        bool interrupted_error(int error) {
#if defined(_WIN32)
            return error == WSAEINTR;
#else
            return error == EINTR;
#endif
        }

        bool would_block_error(int error) {
#if defined(_WIN32)
            return error == WSAEWOULDBLOCK;
#else
            return error == EAGAIN || error == EWOULDBLOCK;
#endif
        }

        bool set_nonblocking(Socket socket) {
#if defined(_WIN32)
            u_long enabled = 1;
            return ioctlsocket(socket, FIONBIO, &enabled) == 0;
#else
            const int flags = fcntl(socket, F_GETFL, 0);
            return flags >= 0 && fcntl(socket, F_SETFL, flags | O_NONBLOCK) == 0;
#endif
        }

        enum class WaitResult {
            ready,
            timeout,
            failed
        };

        WaitResult wait_socket(Socket socket, bool write, std::chrono::milliseconds timeout) {
            fd_set read_set;
            fd_set write_set;
            FD_ZERO(&read_set);
            FD_ZERO(&write_set);
            if (write) {
                FD_SET(socket, &write_set);
            } else {
                FD_SET(socket, &read_set);
            }
            timeval value{};
            value.tv_sec = static_cast<long>(timeout.count() / 1000);
            value.tv_usec = static_cast<long>((timeout.count() % 1000) * 1000);
#if defined(_WIN32)
            const int result = select(0, &read_set, &write_set, nullptr, &value);
#else
            const int result = select(socket + 1, &read_set, &write_set, nullptr, &value);
#endif
            if (result > 0) {
                return WaitResult::ready;
            }
            if (result == 0) {
                return WaitResult::timeout;
            }
            return interrupted_error(socket_error()) ? WaitResult::timeout : WaitResult::failed;
        }

        template <typename Bytes, typename Transfer>
        bool transfer_exact(Socket socket,
                            Bytes bytes,
                            bool write,
                            const std::atomic<bool>& running,
                            std::chrono::milliseconds timeout,
                            Transfer transfer) {
            std::size_t offset = 0;
            const auto deadline = Clock::now() + timeout;
            while (offset < bytes.size() && running.load(std::memory_order_acquire)) {
                const auto remaining = std::chrono::duration_cast<std::chrono::milliseconds>(deadline - Clock::now());
                if (remaining <= std::chrono::milliseconds::zero()) {
                    tc_log_error("remote profiler target: socket transfer timed out");
                    return false;
                }
                const auto slice = std::min(remaining, std::chrono::milliseconds(50));
                const WaitResult wait = wait_socket(socket, write, slice);
                if (wait == WaitResult::timeout) {
                    continue;
                }
                if (wait == WaitResult::failed) {
                    tc_log_error("remote profiler target: socket wait failed (error=%d)", socket_error());
                    return false;
                }

                const int transferred = transfer(bytes.subspan(offset));
                if (transferred > 0) {
                    offset += static_cast<std::size_t>(transferred);
                    continue;
                }
                if (transferred == 0) {
                    return false;
                }
                const int error = socket_error();
                if (interrupted_error(error) || would_block_error(error)) {
                    continue;
                }
                tc_log_error("remote profiler target: socket %s failed (error=%d)", write ? "send" : "receive", error);
                return false;
            }
            return offset == bytes.size();
        }

        bool send_bytes(Socket socket, std::span<const std::uint8_t> bytes, const std::atomic<bool>& running) {
            return transfer_exact(socket,
                                  bytes,
                                  true,
                                  running,
                                  std::chrono::seconds(2),
                                  [socket](std::span<const std::uint8_t> remaining) {
                                      return send(socket,
                                                  reinterpret_cast<const char*>(remaining.data()),
                                                  static_cast<int>(remaining.size()),
                                                  0);
                                  });
        }

        bool receive_bytes(Socket socket, std::span<std::uint8_t> bytes, const std::atomic<bool>& running) {
            return transfer_exact(
                socket, bytes, false, running, std::chrono::seconds(2), [socket](std::span<std::uint8_t> remaining) {
                    return recv(
                        socket, reinterpret_cast<char*>(remaining.data()), static_cast<int>(remaining.size()), 0);
                });
        }

        CodecResult<DecodedMessage> receive_message(Socket socket, const std::atomic<bool>& running) {
            std::vector<std::uint8_t> bytes(envelope_size);
            if (!receive_bytes(socket, bytes, running)) {
                return {.value = std::nullopt,
                        .error = CodecError::truncated,
                        .detail = "connection closed while receiving envelope"};
            }
            auto envelope = decode_envelope(bytes);
            if (!envelope) {
                return {.value = std::nullopt, .error = envelope.error, .detail = std::move(envelope.detail)};
            }
            bytes.resize(envelope_size + envelope.value->payload_length);
            auto payload = std::span<std::uint8_t>(bytes).subspan(envelope_size);
            if (!payload.empty() && !receive_bytes(socket, payload, running)) {
                return {.value = std::nullopt,
                        .error = CodecError::truncated,
                        .detail = "connection closed while receiving payload"};
            }
            return decode_message(bytes);
        }

        bool constant_time_equal(const std::string& left, const std::string& right) {
            std::size_t difference = left.size() ^ right.size();
            const std::size_t count = std::max(left.size(), right.size());
            for (std::size_t index = 0; index < count; ++index) {
                const unsigned char a = index < left.size() ? static_cast<unsigned char>(left[index]) : 0;
                const unsigned char b = index < right.size() ? static_cast<unsigned char>(right[index]) : 0;
                difference |= static_cast<std::size_t>(a ^ b);
            }
            return difference == 0;
        }

        struct FrameCommand {
            Control control;
        };

        struct OutboundPacket {
            std::vector<DictionaryEntry> required_names;
            std::optional<Status> status;
            std::optional<GapEvent> gap;
            std::optional<DropEvent> drop;
            std::optional<FrameBatch> frames;
            std::uint64_t frame_count = 0;
        };

        WireFrame copy_frame(const tc_frame_profile& source) {
            WireFrame result;
            result.frame_number = source.frame_number;
            result.start_time_ms = source.start_time_ms;
            result.interval_ms = source.interval_ms;
            result.active_ms = source.active_ms;
            result.has_gpu_duration = source.has_gpu_duration;
            result.gpu_duration_ms = source.gpu_duration_ms;
            result.target_interval_ms = source.target_interval_ms;
            result.deadline_lateness_ms = source.deadline_lateness_ms;
            result.missed_intervals = static_cast<std::uint32_t>(source.missed_intervals);
            result.sections_profiled = source.sections_profiled;
            return result;
        }

    } // namespace

    class RemoteProfilerTarget::Impl {
    public:
        explicit Impl(TargetServiceConfig target_config)
            : config(std::move(target_config)),
              command_queue(config.command_queue_capacity),
              outbound_queue(config.outbound_queue_capacity) {
            validate_config();
            capture = tc_profiler_capture_create(static_cast<int>(config.capture_capacity));
            if (!capture) {
                throw std::runtime_error("remote profiler target failed to create capture");
            }
            tc_profiler_capture_set_active(capture, false);
            tc_profiler_capture_set_profiling(capture, false);
            name_ids.emplace("<section-name-limit>", 1);
            names_by_id.emplace_back("<section-name-limit>");
            next_name_id = 2;
        }

        ~Impl() {
            stop();
            tc_profiler_capture_destroy(capture);
        }

        bool start() {
            if (running.load(std::memory_order_acquire)) {
                return true;
            }
            if (config.bind_address != "127.0.0.1") {
                tc_log_error("remote profiler target: non-loopback bind '%s' is forbidden",
                             config.bind_address.c_str());
                return false;
            }
            if (config.authentication_token.empty()) {
                tc_log_error("remote profiler target: authentication token must not be empty");
                return false;
            }
#if defined(_WIN32)
            WSADATA data{};
            if (WSAStartup(MAKEWORD(2, 2), &data) != 0) {
                tc_log_error("remote profiler target: WSAStartup failed");
                return false;
            }
            winsock_started = true;
#endif
            const Socket listener = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
            if (listener == invalid_socket) {
                tc_log_error("remote profiler target: socket creation failed (error=%d)", socket_error());
                cleanup_socket_runtime();
                return false;
            }
            int reuse = 1;
            setsockopt(listener, SOL_SOCKET, SO_REUSEADDR, reinterpret_cast<const char*>(&reuse), sizeof(reuse));
            sockaddr_in address{};
            address.sin_family = AF_INET;
            address.sin_port = htons(config.port);
            address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
            if (bind(listener, reinterpret_cast<const sockaddr*>(&address), sizeof(address)) != 0 ||
                listen(listener, 1) != 0 || !set_nonblocking(listener)) {
                tc_log_error("remote profiler target: loopback bind/listen failed "
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
            if (getsockname(listener, reinterpret_cast<sockaddr*>(&actual), &actual_size) != 0) {
                tc_log_error("remote profiler target: getsockname failed (error=%d)", socket_error());
                close_socket(listener);
                cleanup_socket_runtime();
                return false;
            }
            listening_port.store(ntohs(actual.sin_port), std::memory_order_release);
            listener_socket.store(listener, std::memory_order_release);
            running.store(true, std::memory_order_release);
            io_thread = std::thread([this] { io_main(); });
            tc_log_info("remote profiler target: listening on 127.0.0.1:%u",
                        static_cast<unsigned>(listening_port.load()));
            return true;
        }

        void stop() {
            if (!running.exchange(false, std::memory_order_acq_rel)) {
                return;
            }
            close_owned_socket(client_socket);
            close_owned_socket(listener_socket);
            if (io_thread.joinable()) {
                io_thread.join();
            }
            client_connected.store(false, std::memory_order_release);
            listening_port.store(0, std::memory_order_release);
            cleanup_socket_runtime();

            // The I/O producer is gone, so the frame thread can reset both handoff
            // queues and the profiler capture before a deterministic restart.
            FrameCommand command;
            while (command_queue.try_pop(command)) {
            }
            OutboundPacket packet;
            while (outbound_queue.try_pop(packet)) {
            }
            tc_profiler_capture_set_active(capture, false);
            tc_profiler_capture_set_profiling(capture, false);
            tc_profiler_capture_clear(capture);
            capturing.store(false, std::memory_order_release);
            profiling_sections.store(false, std::memory_order_release);
            last_frame_number = -1;
            sent_gpu_durations.clear();
            pending_dropped_batches = 0;
            pending_dropped_frames = 0;
            tc_log_info("remote profiler target: stopped");
        }

        void pump_frame_thread() {
            FrameCommand command;
            while (command_queue.try_pop(command)) {
                apply_command(command.control);
            }
            if (!capturing.load(std::memory_order_acquire)) {
                return;
            }

            tc_profiler_history_range range{};
            if (!tc_profiler_capture_after(capture, last_frame_number, &range)) {
                tc_log_error("remote profiler target: failed to query capture range");
                return;
            }
            std::size_t offset = 0;
            bool gap_pending = range.dropped_count > 0;
            while (offset < static_cast<std::size_t>(range.count)) {
                const std::size_t count =
                    std::min(config.frames_per_batch, static_cast<std::size_t>(range.count) - offset);
                OutboundPacket packet;
                FrameBatch batch;
                batch.frames.reserve(count);
                std::unordered_set<std::uint32_t> packet_names;
                if (gap_pending) {
                    packet.gap = GapEvent{
                        GapKind::capture_ring,
                        static_cast<std::int64_t>(last_frame_number + 1),
                        static_cast<std::int64_t>(range.oldest_frame_number - 1),
                        0,
                    };
                    gap_pending = false;
                }
                for (std::size_t index = 0; index < count; ++index) {
                    const tc_frame_profile* source =
                        tc_profiler_capture_at(capture, range.first_index + static_cast<int>(offset + index));
                    if (!source) {
                        tc_log_error("remote profiler target: capture returned a null frame");
                        continue;
                    }
                    append_wire_frame(packet, batch, packet_names, *source);
                    last_frame_number = source->frame_number;
                }
                offset += count;
                if (batch.frames.empty()) {
                    continue;
                }
                packet.frame_count = batch.frames.size();
                const std::uint64_t completed_count = packet.frame_count;
                packet.frames = std::move(batch);
                enqueue_frame_packet(std::move(packet));
                completed_frames.fetch_add(completed_count, std::memory_order_relaxed);
            }
            enqueue_late_gpu_updates();
        }

        TargetServiceStatus status() const {
            return {
                running.load(std::memory_order_acquire),
                client_connected.load(std::memory_order_acquire),
                capturing.load(std::memory_order_acquire),
                profiling_sections.load(std::memory_order_acquire),
                listening_port.load(std::memory_order_acquire),
                completed_frames.load(std::memory_order_relaxed),
                dropped_batches.load(std::memory_order_relaxed),
                dropped_frames.load(std::memory_order_relaxed),
                rejected_clients.load(std::memory_order_relaxed),
                transmitted_bytes.load(std::memory_order_relaxed),
            };
        }

    private:
        void validate_config() {
            if (config.capture_capacity == 0 || config.capture_capacity > INT_MAX) {
                throw std::invalid_argument("remote profiler target capture capacity is invalid");
            }
            if (config.frames_per_batch == 0 || config.frames_per_batch > WireLimits::max_frames_per_batch) {
                throw std::invalid_argument("remote profiler target frames-per-batch is invalid");
            }
            if (config.authentication_token.size() > WireLimits::max_token_bytes) {
                throw std::invalid_argument("remote profiler target token exceeds wire limit");
            }
            for (const auto* field : {&config.platform, &config.abi, &config.build_type, &config.build_id}) {
                if (field->size() > WireLimits::max_identity_bytes) {
                    throw std::invalid_argument("remote profiler target identity exceeds wire limit");
                }
            }
        }

        void close_owned_socket(std::atomic<Socket>& storage) {
            const Socket socket = storage.exchange(invalid_socket, std::memory_order_acq_rel);
            if (socket != invalid_socket) {
                shutdown_socket(socket);
                close_socket(socket);
            }
        }

        void cleanup_socket_runtime() {
#if defined(_WIN32)
            if (winsock_started) {
                WSACleanup();
                winsock_started = false;
            }
#endif
        }

        std::uint32_t intern_name(const std::string& name) {
            const auto found = name_ids.find(name);
            if (found != name_ids.end()) {
                return found->second;
            }
            if (name_ids.size() >= WireLimits::max_dictionary_entries) {
                if (!reported_name_limit) {
                    tc_log_error("remote profiler target: section-name dictionary reached "
                                 "its hard limit (%u); new names use the overflow entry",
                                 WireLimits::max_dictionary_entries);
                    reported_name_limit = true;
                }
                return 1;
            }
            const std::uint32_t id = next_name_id++;
            name_ids.emplace(name, id);
            names_by_id.push_back(name);
            return id;
        }

        void append_wire_frame(OutboundPacket& packet,
                               FrameBatch& batch,
                               std::unordered_set<std::uint32_t>& packet_names,
                               const tc_frame_profile& source) {
            WireFrame frame = copy_frame(source);
            frame.sections.reserve(static_cast<std::size_t>(source.section_count));
            for (int section_index = 0; section_index < source.section_count; ++section_index) {
                const tc_section_timing& section = source.sections[section_index];
                const std::uint32_t name_id = intern_name(section.name);
                frame.sections.push_back(WireSection{
                    name_id,
                    section.cpu_ms,
                    section.children_ms,
                    static_cast<std::uint32_t>(section.call_count),
                    section.parent_index,
                    section.first_child,
                    section.next_sibling,
                });
                if (packet_names.insert(name_id).second) {
                    packet.required_names.push_back(
                        DictionaryEntry{name_id, names_by_id[static_cast<std::size_t>(name_id - 1)]});
                }
            }
            if (source.has_gpu_duration) {
                sent_gpu_durations[source.frame_number] = source.gpu_duration_ms;
            }
            batch.frames.push_back(std::move(frame));
        }

        void enqueue_late_gpu_updates() {
            const int count = tc_profiler_capture_count(capture);
            for (int index = 0; index < count; ++index) {
                const tc_frame_profile* source = tc_profiler_capture_at(capture, index);
                if (!source || !source->has_gpu_duration || source->frame_number > last_frame_number) {
                    continue;
                }
                const auto sent = sent_gpu_durations.find(source->frame_number);
                if (sent != sent_gpu_durations.end() && sent->second == source->gpu_duration_ms) {
                    continue;
                }
                OutboundPacket packet;
                FrameBatch batch;
                batch.frames.reserve(1);
                std::unordered_set<std::uint32_t> packet_names;
                append_wire_frame(packet, batch, packet_names, *source);
                packet.frame_count = 1;
                packet.frames = std::move(batch);
                enqueue_frame_packet(std::move(packet));
            }

            // Bound the tracking map to the same lifetime as capture history.
            if (count > 0) {
                const tc_frame_profile* oldest = tc_profiler_capture_at(capture, 0);
                if (oldest) {
                    for (auto it = sent_gpu_durations.begin(); it != sent_gpu_durations.end();) {
                        if (it->first < oldest->frame_number)
                            it = sent_gpu_durations.erase(it);
                        else
                            ++it;
                    }
                }
            } else {
                sent_gpu_durations.clear();
            }
        }

        Status current_status(std::uint64_t request_id, const std::string& detail) const {
            return Status{
                request_id,
                capturing.load(std::memory_order_acquire),
                profiling_sections.load(std::memory_order_acquire),
                completed_frames.load(std::memory_order_relaxed),
                dropped_frames.load(std::memory_order_relaxed),
                static_cast<std::uint32_t>(outbound_queue.size_approximate()),
                now_ns(),
                detail,
            };
        }

        void apply_command(const Control& control) {
            std::string detail = "command applied";
            switch (control.kind) {
            case ControlKind::start_capture:
                tc_profiler_capture_set_active(capture, true);
                capturing.store(true, std::memory_order_release);
                detail = "capture started";
                break;
            case ControlKind::pause_capture:
                tc_profiler_capture_set_active(capture, false);
                capturing.store(false, std::memory_order_release);
                detail = "capture paused";
                break;
            case ControlKind::set_sections:
                tc_profiler_capture_set_profiling(capture, control.enabled);
                profiling_sections.store(control.enabled, std::memory_order_release);
                detail = control.enabled ? "section profiling enabled" : "section profiling disabled";
                break;
            case ControlKind::clear_capture:
                tc_profiler_capture_clear(capture);
                last_frame_number = -1;
                sent_gpu_durations.clear();
                detail = "capture cleared";
                break;
            case ControlKind::request_status:
                detail = "status";
                break;
            case ControlKind::ping:
                detail = "pong";
                break;
            case ControlKind::disconnect:
                detail = "disconnect handled by I/O thread";
                break;
            }
            OutboundPacket packet;
            packet.status = current_status(control.request_id, detail);
            if (!outbound_queue.try_push(std::move(packet))) {
                tc_log_error("remote profiler target: outbound queue full; status "
                             "acknowledgement dropped");
            }
        }

        void enqueue_frame_packet(OutboundPacket packet) {
            const std::uint64_t pending_batches = pending_dropped_batches;
            const std::uint64_t pending_frames = pending_dropped_frames;
            if (pending_batches != 0) {
                packet.drop = DropEvent{DropKind::producer_queue, pending_batches, pending_frames, 0};
            }
            const std::uint64_t frame_count = packet.frame_count;
            if (outbound_queue.try_push(std::move(packet))) {
                pending_dropped_batches = 0;
                pending_dropped_frames = 0;
                return;
            }
            ++pending_dropped_batches;
            pending_dropped_frames += frame_count;
            dropped_batches.fetch_add(1, std::memory_order_relaxed);
            dropped_frames.fetch_add(frame_count, std::memory_order_relaxed);
        }

        bool send_wire(Socket socket, const Message& message, std::uint64_t& sequence, std::uint64_t session_id) {
            auto encoded = encode_message(message, sequence++, session_id);
            if (!encoded) {
                tc_log_error("remote profiler target: failed to encode outgoing message: %s", encoded.detail.c_str());
                return false;
            }
            const bool sent = send_bytes(socket, *encoded.value, running);
            if (sent)
                transmitted_bytes.fetch_add(encoded.value->size(), std::memory_order_relaxed);
            return sent;
        }

        bool handshake(Socket socket, std::uint64_t& sequence, std::uint64_t session_id) {
            auto decoded = receive_message(socket, running);
            if (!decoded || !std::holds_alternative<ClientHello>(decoded.value->message)) {
                tc_log_error("remote profiler target: client handshake is malformed");
                return false;
            }
            const ClientHello& hello = std::get<ClientHello>(decoded.value->message);
            const bool version_ok = hello.minimum_major == protocol_major && hello.minimum_minor <= protocol_minor;
            if (!version_ok || !constant_time_equal(hello.authentication_token, config.authentication_token)) {
                const std::string detail =
                    !version_ok ? "client version range is incompatible" : "client authentication token is invalid";
                send_wire(socket, ErrorEvent{401, decoded.value->envelope.sequence, detail}, sequence, session_id);
                tc_log_error("remote profiler target: rejected client: %s", detail.c_str());
                return false;
            }
            TargetHello target;
            target.capabilities = static_cast<std::uint64_t>(Capability::cadence_capture) |
                                  static_cast<std::uint64_t>(Capability::hierarchical_sections) |
                                  static_cast<std::uint64_t>(Capability::clear_capture) |
                                  static_cast<std::uint64_t>(Capability::clock_correlation);
            target.process_id = config.process_id;
            target.capturing = capturing.load(std::memory_order_acquire);
            target.profiling_sections = profiling_sections.load(std::memory_order_acquire);
            target.platform = config.platform;
            target.abi = config.abi;
            target.build_type = config.build_type;
            target.build_id = config.build_id;
            return send_wire(socket, target, sequence, session_id);
        }

        bool send_packet(Socket socket,
                         OutboundPacket& packet,
                         std::unordered_set<std::uint32_t>& sent_names,
                         std::uint64_t& sequence,
                         std::uint64_t session_id) {
            DictionaryAdd additions;
            for (const DictionaryEntry& entry : packet.required_names) {
                if (sent_names.insert(entry.id).second) {
                    additions.entries.push_back(entry);
                }
            }
            if (!additions.entries.empty() && !send_wire(socket, additions, sequence, session_id)) {
                return false;
            }
            if (packet.drop && !send_wire(socket, *packet.drop, sequence, session_id)) {
                return false;
            }
            if (packet.gap && !send_wire(socket, *packet.gap, sequence, session_id)) {
                return false;
            }
            if (packet.status && !send_wire(socket, *packet.status, sequence, session_id)) {
                return false;
            }
            if (packet.frames && !send_wire(socket, *packet.frames, sequence, session_id)) {
                return false;
            }
            return true;
        }

        void io_main() {
            while (running.load(std::memory_order_acquire)) {
                const Socket listener = listener_socket.load(std::memory_order_acquire);
                if (listener == invalid_socket) {
                    break;
                }
                const WaitResult wait = wait_socket(listener, false, std::chrono::milliseconds(50));
                if (wait == WaitResult::timeout) {
                    continue;
                }
                if (wait == WaitResult::failed) {
                    if (running.load(std::memory_order_acquire)) {
                        tc_log_error("remote profiler target: listener wait failed");
                    }
                    break;
                }
                sockaddr_in peer{};
#if defined(_WIN32)
                int peer_size = sizeof(peer);
#else
                socklen_t peer_size = sizeof(peer);
#endif
                const Socket client = accept(listener, reinterpret_cast<sockaddr*>(&peer), &peer_size);
                if (client == invalid_socket) {
                    continue;
                }
                if (ntohl(peer.sin_addr.s_addr) != INADDR_LOOPBACK || !set_nonblocking(client)) {
                    tc_log_error("remote profiler target: rejected non-loopback client");
                    rejected_clients.fetch_add(1, std::memory_order_relaxed);
                    close_socket(client);
                    continue;
                }
                client_socket.store(client, std::memory_order_release);
                const std::uint64_t session_id = next_session_id.fetch_add(1);
                std::uint64_t sequence = 1;
                if (!handshake(client, sequence, session_id)) {
                    rejected_clients.fetch_add(1, std::memory_order_relaxed);
                    release_client(client);
                    continue;
                }
                client_connected.store(true, std::memory_order_release);
                tc_log_info("remote profiler target: client connected (session=%llu)",
                            static_cast<unsigned long long>(session_id));
                serve_client(client, sequence, session_id);
                client_connected.store(false, std::memory_order_release);
                release_client(client);
                tc_log_info("remote profiler target: client disconnected (session=%llu)",
                            static_cast<unsigned long long>(session_id));
            }
        }

        void serve_client(Socket socket, std::uint64_t sequence, std::uint64_t session_id) {
            std::unordered_set<std::uint32_t> sent_names;
            while (running.load(std::memory_order_acquire)) {
                OutboundPacket packet;
                while (outbound_queue.try_pop(packet)) {
                    if (!send_packet(socket, packet, sent_names, sequence, session_id)) {
                        return;
                    }
                }
                const WaitResult wait = wait_socket(socket, false, std::chrono::milliseconds(10));
                if (wait == WaitResult::timeout) {
                    continue;
                }
                if (wait == WaitResult::failed) {
                    return;
                }
                auto decoded = receive_message(socket, running);
                if (!decoded) {
                    if (decoded.detail != "connection closed while receiving envelope") {
                        tc_log_error("remote profiler target: malformed client message: %s", decoded.detail.c_str());
                    }
                    return;
                }
                if (!std::holds_alternative<Control>(decoded.value->message)) {
                    send_wire(socket,
                              ErrorEvent{400,
                                         decoded.value->envelope.sequence,
                                         "only Control messages are accepted after handshake"},
                              sequence,
                              session_id);
                    continue;
                }
                const Control& control = std::get<Control>(decoded.value->message);
                if (control.kind == ControlKind::disconnect) {
                    send_wire(socket, current_status(control.request_id, "disconnecting"), sequence, session_id);
                    return;
                }
                if (!command_queue.try_push(FrameCommand{control})) {
                    tc_log_error("remote profiler target: command queue full; command rejected");
                    if (!send_wire(socket,
                                   ErrorEvent{429, decoded.value->envelope.sequence, "target command queue is full"},
                                   sequence,
                                   session_id)) {
                        return;
                    }
                }
            }
        }

        void release_client(Socket socket) {
            Socket expected = socket;
            if (client_socket.compare_exchange_strong(expected, invalid_socket, std::memory_order_acq_rel)) {
                shutdown_socket(socket);
                close_socket(socket);
            }
        }

        TargetServiceConfig config;
        BoundedSpscQueue<FrameCommand> command_queue;
        BoundedSpscQueue<OutboundPacket> outbound_queue;
        tc_profiler_capture* capture = nullptr;
        std::thread io_thread;
        std::atomic<bool> running{false};
        std::atomic<bool> client_connected{false};
        std::atomic<bool> capturing{false};
        std::atomic<bool> profiling_sections{false};
        std::atomic<Socket> listener_socket{invalid_socket};
        std::atomic<Socket> client_socket{invalid_socket};
        std::atomic<std::uint16_t> listening_port{0};
        std::atomic<std::uint64_t> next_session_id{1};
        std::atomic<std::uint64_t> completed_frames{0};
        std::atomic<std::uint64_t> dropped_batches{0};
        std::atomic<std::uint64_t> dropped_frames{0};
        std::atomic<std::uint64_t> rejected_clients{0};
        std::atomic<std::uint64_t> transmitted_bytes{0};
        std::unordered_map<std::string, std::uint32_t> name_ids;
        std::vector<std::string> names_by_id;
        std::uint32_t next_name_id = 1;
        bool reported_name_limit = false;
        int last_frame_number = -1;
        std::unordered_map<int, double> sent_gpu_durations;
        std::uint64_t pending_dropped_batches = 0;
        std::uint64_t pending_dropped_frames = 0;
#if defined(_WIN32)
        bool winsock_started = false;
#endif
    };

    RemoteProfilerTarget::RemoteProfilerTarget(TargetServiceConfig config)
        : impl_(std::make_unique<Impl>(std::move(config))) {}

    RemoteProfilerTarget::~RemoteProfilerTarget() = default;

    bool RemoteProfilerTarget::start() {
        return impl_->start();
    }

    void RemoteProfilerTarget::stop() {
        impl_->stop();
    }

    void RemoteProfilerTarget::pump_frame_thread() {
        impl_->pump_frame_thread();
    }

    TargetServiceStatus RemoteProfilerTarget::status() const {
        return impl_->status();
    }

} // namespace termin::profiler_remote
