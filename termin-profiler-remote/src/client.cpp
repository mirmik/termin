#include <termin/profiler_remote/client.hpp>

#include <termin/profiler_remote/bounded_spsc_queue.hpp>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstring>
#include <stdexcept>
#include <thread>
#include <utility>
#include <vector>

#include <tcbase/tc_log.h>

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

        void close_socket(Socket socket) {
            if (socket == invalid_socket)
                return;
#if defined(_WIN32)
            closesocket(socket);
#else
            close(socket);
#endif
        }

        void shutdown_socket(Socket socket) {
            if (socket == invalid_socket)
                return;
#if defined(_WIN32)
            shutdown(socket, SD_BOTH);
#else
            shutdown(socket, SHUT_RDWR);
#endif
        }

        enum class WaitResult {
            ready,
            timeout,
            failed
        };

        WaitResult wait_readable(Socket socket, std::chrono::milliseconds timeout) {
            fd_set set;
            FD_ZERO(&set);
            FD_SET(socket, &set);
            timeval value{};
            value.tv_sec = static_cast<long>(timeout.count() / 1000);
            value.tv_usec = static_cast<long>((timeout.count() % 1000) * 1000);
#if defined(_WIN32)
            const int result = select(0, &set, nullptr, nullptr, &value);
#else
            const int result = select(socket + 1, &set, nullptr, nullptr, &value);
#endif
            if (result > 0)
                return WaitResult::ready;
            return result == 0 ? WaitResult::timeout : WaitResult::failed;
        }

        WaitResult wait_writable(Socket socket, std::chrono::milliseconds timeout) {
            fd_set set;
            FD_ZERO(&set);
            FD_SET(socket, &set);
            timeval value{};
            value.tv_sec = static_cast<long>(timeout.count() / 1000);
            value.tv_usec = static_cast<long>((timeout.count() % 1000) * 1000);
#if defined(_WIN32)
            const int result = select(0, nullptr, &set, nullptr, &value);
#else
            const int result = select(socket + 1, nullptr, &set, nullptr, &value);
#endif
            if (result > 0)
                return WaitResult::ready;
            return result == 0 ? WaitResult::timeout : WaitResult::failed;
        }

        bool set_socket_blocking(Socket socket, bool blocking) {
#if defined(_WIN32)
            u_long mode = blocking ? 0UL : 1UL;
            return ioctlsocket(socket, FIONBIO, &mode) == 0;
#else
            const int flags = fcntl(socket, F_GETFL, 0);
            if (flags < 0)
                return false;
            const int updated = blocking ? (flags & ~O_NONBLOCK) : (flags | O_NONBLOCK);
            return fcntl(socket, F_SETFL, updated) == 0;
#endif
        }

        bool connect_is_in_progress() {
#if defined(_WIN32)
            const int error = WSAGetLastError();
            return error == WSAEWOULDBLOCK || error == WSAEINPROGRESS;
#else
            return errno == EINPROGRESS;
#endif
        }

        bool socket_has_no_error(Socket socket) {
            int error = 0;
#if defined(_WIN32)
            int length = sizeof(error);
            return getsockopt(socket, SOL_SOCKET, SO_ERROR, reinterpret_cast<char*>(&error), &length) == 0 &&
                   error == 0;
#else
            socklen_t length = sizeof(error);
            return getsockopt(socket, SOL_SOCKET, SO_ERROR, &error, &length) == 0 && error == 0;
#endif
        }

        template <typename Bytes, typename Transfer>
        bool transfer_exact(Bytes bytes, const std::atomic<bool>& running, Transfer transfer) {
            std::size_t offset = 0;
            while (offset < bytes.size() && running.load(std::memory_order_acquire)) {
                const int count = transfer(bytes.subspan(offset));
                if (count <= 0)
                    return false;
                offset += static_cast<std::size_t>(count);
            }
            return offset == bytes.size();
        }

        bool send_bytes(Socket socket, std::span<const std::uint8_t> bytes, const std::atomic<bool>& running) {
            return transfer_exact(bytes, running, [socket](std::span<const std::uint8_t> remaining) {
                return send(
                    socket, reinterpret_cast<const char*>(remaining.data()), static_cast<int>(remaining.size()), 0);
            });
        }

        bool receive_bytes(Socket socket, std::span<std::uint8_t> bytes, const std::atomic<bool>& running) {
            return transfer_exact(bytes, running, [socket](std::span<std::uint8_t> remaining) {
                return recv(socket, reinterpret_cast<char*>(remaining.data()), static_cast<int>(remaining.size()), 0);
            });
        }

        CodecResult<DecodedMessage> receive_message(Socket socket, const std::atomic<bool>& running) {
            std::vector<std::uint8_t> bytes(envelope_size);
            if (!receive_bytes(socket, bytes, running))
                return {.value = std::nullopt,
                        .error = CodecError::truncated,
                        .detail = "connection closed while receiving envelope"};
            auto envelope = decode_envelope(bytes);
            if (!envelope)
                return {.value = std::nullopt, .error = envelope.error, .detail = std::move(envelope.detail)};
            bytes.resize(envelope_size + envelope.value->payload_length);
            auto payload = std::span<std::uint8_t>(bytes).subspan(envelope_size);
            if (!payload.empty() && !receive_bytes(socket, payload, running))
                return {.value = std::nullopt,
                        .error = CodecError::truncated,
                        .detail = "connection closed while receiving payload"};
            return decode_message(bytes);
        }

    } // namespace

    class RemoteProfilerClient::Impl {
    public:
        Impl(ClientConfig target_config, MessageHandler target_handler, DisconnectHandler target_disconnect_handler)
            : config(std::move(target_config)),
              handler(std::move(target_handler)),
              disconnect_handler(std::move(target_disconnect_handler)),
              commands(config.command_queue_capacity) {
            if (config.address != "127.0.0.1" || config.port == 0 || config.authentication_token.empty() || !handler)
                throw std::invalid_argument("invalid remote profiler client config");
        }

        ~Impl() {
            stop();
        }

        bool start() {
            if (running.exchange(true, std::memory_order_acq_rel))
                return true;
            if (worker.joinable())
                worker.join();
#if defined(_WIN32)
            if (winsock_started) {
                WSACleanup();
                winsock_started = false;
            }
            WSADATA data{};
            if (WSAStartup(MAKEWORD(2, 2), &data) != 0) {
                running.store(false, std::memory_order_release);
                tc_log_error("remote profiler client: WSAStartup failed");
                return false;
            }
            winsock_started = true;
#endif
            worker = std::thread([this] { run(); });
            return true;
        }

        void stop() {
            running.store(false, std::memory_order_release);
            const Socket socket = active_socket.exchange(invalid_socket);
            shutdown_socket(socket);
            close_socket(socket);
            if (worker.joinable())
                worker.join();
            connected.store(false, std::memory_order_release);
#if defined(_WIN32)
            if (winsock_started) {
                WSACleanup();
                winsock_started = false;
            }
#endif
        }

        bool enqueue(const Control& control) {
            if (!running.load(std::memory_order_acquire) || !commands.try_push(control)) {
                rejected_commands.fetch_add(1, std::memory_order_relaxed);
                tc_log_error("remote profiler client: command queue is unavailable");
                return false;
            }
            return true;
        }

        bool send_message(Socket socket, const Message& message, std::uint64_t& sequence, std::uint64_t session_id) {
            auto encoded = encode_message(message, sequence++, session_id);
            if (!encoded) {
                tc_log_error("remote profiler client: encode failed: %s", encoded.detail.c_str());
                return false;
            }
            return send_bytes(socket, *encoded.value, running);
        }

        Socket connect_once() {
            connection_attempts.fetch_add(1, std::memory_order_relaxed);
            const Socket socket = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
            if (socket == invalid_socket)
                return invalid_socket;
            active_socket.store(socket, std::memory_order_release);
            if (!set_socket_blocking(socket, false)) {
                release(socket);
                return invalid_socket;
            }
            sockaddr_in address{};
            address.sin_family = AF_INET;
            address.sin_port = htons(config.port);
            address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
            bool connected = connect(socket, reinterpret_cast<const sockaddr*>(&address), sizeof(address)) == 0;
            if (!connected && connect_is_in_progress()) {
                const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(500);
                while (running.load(std::memory_order_acquire) && std::chrono::steady_clock::now() < deadline) {
                    const WaitResult wait = wait_writable(socket, std::chrono::milliseconds(20));
                    if (wait == WaitResult::ready) {
                        connected = socket_has_no_error(socket);
                        break;
                    }
                    if (wait == WaitResult::failed)
                        break;
                }
            }
            if (!connected || !running.load(std::memory_order_acquire) || !set_socket_blocking(socket, true)) {
                release(socket);
                return invalid_socket;
            }
            return socket;
        }

        void run() {
            bool reported_unavailable = false;
            while (running.load(std::memory_order_acquire)) {
                const Socket socket = connect_once();
                if (socket == invalid_socket) {
                    if (!reported_unavailable) {
                        tc_log_error("remote profiler client: target is unavailable at "
                                     "127.0.0.1:%u",
                                     static_cast<unsigned>(config.port));
                        notify_disconnect("remote target is unavailable at 127.0.0.1:" + std::to_string(config.port));
                        reported_unavailable = true;
                    }
                    if (!config.reconnect)
                        break;
                    std::this_thread::sleep_for(std::chrono::milliseconds(200));
                    continue;
                }
                reported_unavailable = false;
                active_socket.store(socket, std::memory_order_release);
                std::uint64_t sequence = 1;
                ClientHello hello;
                hello.authentication_token = config.authentication_token;
                if (!send_message(socket, hello, sequence, 0)) {
                    release(socket);
                    notify_disconnect("target handshake send failed");
                    if (!config.reconnect)
                        break;
                    std::this_thread::sleep_for(std::chrono::milliseconds(200));
                    continue;
                }
                auto response = receive_message(socket, running);
                if (!response || !std::holds_alternative<TargetHello>(response.value->message)) {
                    std::string detail = response.detail;
                    if (response && std::holds_alternative<ErrorEvent>(response.value->message))
                        detail = std::get<ErrorEvent>(response.value->message).detail;
                    if (detail.empty())
                        detail = "unexpected handshake response";
                    tc_log_error("remote profiler client: target handshake failed: %s", detail.c_str());
                    release(socket);
                    notify_disconnect("target handshake failed: " + detail);
                    if (!config.reconnect)
                        break;
                    std::this_thread::sleep_for(std::chrono::milliseconds(200));
                    continue;
                }
                connected.store(true, std::memory_order_release);
                sessions.fetch_add(1, std::memory_order_relaxed);
                tc_log_info("remote profiler client: connected to 127.0.0.1:%u", static_cast<unsigned>(config.port));
                handler(*response.value);
                const std::uint64_t session_id = response.value->envelope.session_id;
                serve(socket, sequence, session_id);
                connected.store(false, std::memory_order_release);
                release(socket);
                discard_pending_commands();
                notify_disconnect("remote target disconnected");
                if (!config.reconnect)
                    break;
            }
            running.store(false, std::memory_order_release);
        }

        void serve(Socket socket, std::uint64_t sequence, std::uint64_t session_id) {
            while (running.load(std::memory_order_acquire)) {
                Control control;
                while (commands.try_pop(control))
                    if (!send_message(socket, control, sequence, session_id))
                        return;
                const auto wait = wait_readable(socket, std::chrono::milliseconds(20));
                if (wait == WaitResult::timeout)
                    continue;
                if (wait == WaitResult::failed) {
                    if (running.load(std::memory_order_acquire))
                        tc_log_error("remote profiler client: socket wait failed");
                    return;
                }
                auto message = receive_message(socket, running);
                if (!message) {
                    if (running.load(std::memory_order_acquire))
                        tc_log_error("remote profiler client: malformed/closed stream: %s", message.detail.c_str());
                    return;
                }
                handler(*message.value);
            }
        }

        void release(Socket socket) {
            Socket expected = socket;
            if (active_socket.compare_exchange_strong(expected, invalid_socket)) {
                shutdown_socket(socket);
                close_socket(socket);
            }
        }

        void notify_disconnect(std::string detail) {
            if (disconnect_handler)
                disconnect_handler(std::move(detail));
        }

        void discard_pending_commands() {
            Control discarded;
            std::size_t count = 0;
            while (commands.try_pop(discarded))
                ++count;
            if (count != 0)
                tc_log_error("remote profiler client: discarded %zu stale commands", count);
        }

        ClientConfig config;
        MessageHandler handler;
        DisconnectHandler disconnect_handler;
        BoundedSpscQueue<Control> commands;
        std::thread worker;
        std::atomic<bool> running{false};
        std::atomic<bool> connected{false};
        std::atomic<Socket> active_socket{invalid_socket};
        std::atomic<std::uint64_t> connection_attempts{0};
        std::atomic<std::uint64_t> sessions{0};
        std::atomic<std::uint64_t> rejected_commands{0};
#if defined(_WIN32)
        bool winsock_started = false;
#endif
    };

    RemoteProfilerClient::RemoteProfilerClient(ClientConfig config,
                                               MessageHandler message_handler,
                                               DisconnectHandler disconnect_handler)
        : impl_(std::make_unique<Impl>(std::move(config), std::move(message_handler), std::move(disconnect_handler))) {}
    RemoteProfilerClient::~RemoteProfilerClient() = default;
    bool RemoteProfilerClient::start() {
        return impl_->start();
    }
    void RemoteProfilerClient::stop() {
        impl_->stop();
    }
    bool RemoteProfilerClient::send_control(const Control& control) {
        return impl_->enqueue(control);
    }
    ClientStatus RemoteProfilerClient::status() const {
        return {
            .running = impl_->running.load(std::memory_order_acquire),
            .connected = impl_->connected.load(std::memory_order_acquire),
            .connection_attempts = impl_->connection_attempts.load(std::memory_order_relaxed),
            .sessions = impl_->sessions.load(std::memory_order_relaxed),
            .rejected_commands = impl_->rejected_commands.load(std::memory_order_relaxed),
        };
    }
} // namespace termin::profiler_remote
