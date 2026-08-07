#include <termin/framegraph_remote_client/client.hpp>

#include <termin/framegraph_remote/bounded_spsc_queue.hpp>

#include <algorithm>
#include <atomic>
#include <cerrno>
#include <chrono>
#include <span>
#include <stdexcept>
#include <thread>
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

namespace termin::framegraph_remote_client
{
    namespace
    {

        using namespace framegraph_remote;
        using Clock = std::chrono::steady_clock;

#if defined(_WIN32)
        using Socket = SOCKET;
        constexpr Socket invalid_socket = INVALID_SOCKET;
#else
        using Socket = int;
        constexpr Socket invalid_socket = -1;
#endif

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

        bool connect_in_progress_error(int error)
        {
#if defined(_WIN32)
            return error == WSAEWOULDBLOCK || error == WSAEINPROGRESS;
#else
            return error == EINPROGRESS;
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

        bool socket_has_no_error(Socket socket)
        {
            int error = 0;
#if defined(_WIN32)
            int size = sizeof(error);
            return getsockopt(socket,
                              SOL_SOCKET,
                              SO_ERROR,
                              reinterpret_cast<char*>(&error),
                              &size) == 0 &&
                   error == 0;
#else
            socklen_t size = sizeof(error);
            return getsockopt(socket, SOL_SOCKET, SO_ERROR, &error, &size) ==
                       0 &&
                   error == 0;
#endif
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
                        "remote framegraph client: socket transfer timed out");
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
                    tc_log_error("remote framegraph client: socket wait failed "
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
                    "remote framegraph client: socket %s failed (error=%d)",
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

    } // namespace

    class RemoteFrameGraphClient::Impl
    {
    public:
        Impl(ClientConfig target_config,
             MessageHandler target_handler,
             DisconnectHandler target_disconnect_handler)
            : config(std::move(target_config)),
              message_handler(std::move(target_handler)),
              disconnect_handler(std::move(target_disconnect_handler)),
              commands(config.command_queue_capacity)
        {
            if (config.address != "127.0.0.1" || config.port == 0 ||
                config.authentication_token.empty() || !message_handler ||
                config.authentication_token.size() >
                    WireLimits::max_token_bytes)
            {
                throw std::invalid_argument(
                    "invalid remote framegraph client config");
            }
        }

        ~Impl()
        {
            stop();
        }

        bool start()
        {
            if (running.exchange(true, std::memory_order_acq_rel))
                return true;
            if (worker.joinable())
                worker.join();
#if defined(_WIN32)
            if (winsock_started)
            {
                WSACleanup();
                winsock_started = false;
            }
            WSADATA data{};
            if (WSAStartup(MAKEWORD(2, 2), &data) != 0)
            {
                running.store(false, std::memory_order_release);
                tc_log_error("remote framegraph client: WSAStartup failed");
                return false;
            }
            winsock_started = true;
#endif
            worker = std::thread([this] { run(); });
            return true;
        }

        void stop()
        {
            running.store(false, std::memory_order_release);
            const Socket socket = active_socket.exchange(
                invalid_socket, std::memory_order_acq_rel);
            if (socket != invalid_socket)
            {
                shutdown_socket(socket);
                close_socket(socket);
            }
            if (worker.joinable())
                worker.join();
            connected.store(false, std::memory_order_release);
            discard_pending_commands();
#if defined(_WIN32)
            if (winsock_started)
            {
                WSACleanup();
                winsock_started = false;
            }
#endif
        }

        bool enqueue(const Command& command)
        {
            if (!running.load(std::memory_order_acquire) ||
                !connected.load(std::memory_order_acquire) ||
                !commands.try_push(command))
            {
                rejected_commands.fetch_add(1, std::memory_order_relaxed);
                tc_log_error(
                    "remote framegraph client: command queue is unavailable");
                return false;
            }
            return true;
        }

        bool send_message(Socket socket,
                          const Message& message,
                          std::uint64_t& sequence,
                          std::uint64_t session_id)
        {
            auto encoded = encode_message(message, sequence++, session_id);
            if (!encoded)
            {
                tc_log_error(
                    "remote framegraph client: message encode failed: %s",
                    encoded.detail.c_str());
                return false;
            }
            return send_bytes(socket, *encoded.value, running);
        }

        Socket connect_once()
        {
            connection_attempts.fetch_add(1, std::memory_order_relaxed);
            const Socket socket = ::socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
            if (socket == invalid_socket)
            {
                tc_log_error("remote framegraph client: socket creation failed "
                             "(error=%d)",
                             socket_error());
                return invalid_socket;
            }
            active_socket.store(socket, std::memory_order_release);
            if (!set_nonblocking(socket))
            {
                tc_log_error("remote framegraph client: failed to make socket "
                             "nonblocking");
                release(socket);
                return invalid_socket;
            }
            sockaddr_in address{};
            address.sin_family = AF_INET;
            address.sin_port = htons(config.port);
            address.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
            bool established =
                connect(socket,
                        reinterpret_cast<const sockaddr*>(&address),
                        sizeof(address)) == 0;
            if (!established && connect_in_progress_error(socket_error()))
            {
                const auto deadline =
                    Clock::now() + std::chrono::milliseconds(500);
                while (running.load(std::memory_order_acquire) &&
                       Clock::now() < deadline)
                {
                    const WaitResult wait = wait_socket(
                        socket, true, std::chrono::milliseconds(20));
                    if (wait == WaitResult::ready)
                    {
                        established = socket_has_no_error(socket);
                        break;
                    }
                    if (wait == WaitResult::failed)
                        break;
                }
            }
            if (!established || !running.load(std::memory_order_acquire))
            {
                release(socket);
                return invalid_socket;
            }
            return socket;
        }

        void run()
        {
            bool reported_unavailable = false;
            while (running.load(std::memory_order_acquire))
            {
                const Socket socket = connect_once();
                if (socket == invalid_socket)
                {
                    if (!reported_unavailable)
                    {
                        const std::string detail =
                            "remote target is unavailable at 127.0.0.1:" +
                            std::to_string(config.port);
                        tc_log_error("remote framegraph client: %s",
                                     detail.c_str());
                        notify_disconnect(detail);
                        reported_unavailable = true;
                    }
                    if (!config.reconnect)
                        break;
                    std::this_thread::sleep_for(std::chrono::milliseconds(200));
                    continue;
                }
                reported_unavailable = false;
                std::uint64_t sequence = 1;
                ClientHello hello;
                hello.capabilities =
                    static_cast<std::uint64_t>(Capability::topology);
                hello.authentication_token = config.authentication_token;
                if (!send_message(socket, hello, sequence, 0))
                {
                    release(socket);
                    notify_disconnect("target handshake send failed");
                    if (!config.reconnect)
                        break;
                    continue;
                }
                auto response = receive_message(socket, running);
                if (!response ||
                    !std::holds_alternative<TargetHello>(
                        response.value->message) ||
                    response.value->envelope.session_id == 0)
                {
                    std::string detail = response.detail;
                    if (response && std::holds_alternative<ErrorEvent>(
                                        response.value->message))
                    {
                        detail = std::get<ErrorEvent>(response.value->message)
                                     .detail;
                    }
                    if (detail.empty())
                        detail = "unexpected handshake response";
                    tc_log_error(
                        "remote framegraph client: target handshake failed: %s",
                        detail.c_str());
                    release(socket);
                    notify_disconnect("target handshake failed: " + detail);
                    if (!config.reconnect)
                        break;
                    std::this_thread::sleep_for(std::chrono::milliseconds(200));
                    continue;
                }
                connected.store(true, std::memory_order_release);
                sessions.fetch_add(1, std::memory_order_relaxed);
                const std::uint64_t session_id =
                    response.value->envelope.session_id;
                tc_log_info(
                    "remote framegraph client: connected to 127.0.0.1:%u "
                    "(session=%llu)",
                    static_cast<unsigned>(config.port),
                    static_cast<unsigned long long>(session_id));
                if (!notify_message(*response.value))
                {
                    release(socket);
                    break;
                }
                serve(socket,
                      sequence,
                      session_id,
                      response.value->envelope.sequence);
                connected.store(false, std::memory_order_release);
                release(socket);
                discard_pending_commands();
                notify_disconnect("remote target disconnected");
                if (!config.reconnect)
                    break;
            }
            connected.store(false, std::memory_order_release);
            running.store(false, std::memory_order_release);
        }

        void serve(Socket socket,
                   std::uint64_t sequence,
                   std::uint64_t session_id,
                   std::uint64_t last_sequence)
        {
            while (running.load(std::memory_order_acquire))
            {
                Command command;
                while (commands.try_pop(command))
                {
                    if (!send_message(socket, command, sequence, session_id))
                        return;
                }
                const WaitResult wait =
                    wait_socket(socket, false, std::chrono::milliseconds(20));
                if (wait == WaitResult::timeout)
                    continue;
                if (wait == WaitResult::failed)
                {
                    if (running.load(std::memory_order_acquire))
                    {
                        tc_log_error(
                            "remote framegraph client: socket wait failed");
                    }
                    return;
                }
                auto decoded = receive_message(socket, running);
                if (!decoded)
                {
                    if (running.load(std::memory_order_acquire))
                    {
                        tc_log_error("remote framegraph client: "
                                     "malformed/closed stream: %s",
                                     decoded.detail.c_str());
                    }
                    return;
                }
                if (decoded.value->envelope.session_id != session_id ||
                    decoded.value->envelope.sequence <= last_sequence)
                {
                    tc_log_error("remote framegraph client: invalid session or "
                                 "sequence");
                    return;
                }
                last_sequence = decoded.value->envelope.sequence;
                if (!notify_message(*decoded.value))
                    return;
            }
        }

        bool notify_message(const DecodedMessage& message)
        {
            try
            {
                message_handler(message);
                return true;
            }
            catch (const std::exception& error)
            {
                tc_log_error(
                    "remote framegraph client: message callback failed: %s",
                    error.what());
            }
            catch (...)
            {
                tc_log_error(
                    "remote framegraph client: message callback failed");
            }
            return false;
        }

        void notify_disconnect(std::string detail)
        {
            if (!disconnect_handler)
                return;
            try
            {
                disconnect_handler(std::move(detail));
            }
            catch (const std::exception& error)
            {
                tc_log_error(
                    "remote framegraph client: disconnect callback failed: %s",
                    error.what());
            }
            catch (...)
            {
                tc_log_error(
                    "remote framegraph client: disconnect callback failed");
            }
        }

        void release(Socket socket)
        {
            Socket expected = socket;
            if (active_socket.compare_exchange_strong(
                    expected, invalid_socket, std::memory_order_acq_rel))
            {
                shutdown_socket(socket);
                close_socket(socket);
            }
        }

        void discard_pending_commands()
        {
            Command discarded;
            std::size_t count = 0;
            while (commands.try_pop(discarded))
                ++count;
            if (count != 0)
            {
                tc_log_error(
                    "remote framegraph client: discarded %zu stale commands",
                    count);
            }
        }

        ClientConfig config;
        MessageHandler message_handler;
        DisconnectHandler disconnect_handler;
        BoundedSpscQueue<Command> commands;
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

    RemoteFrameGraphClient::RemoteFrameGraphClient(
        ClientConfig config,
        MessageHandler message_handler,
        DisconnectHandler disconnect_handler)
        : impl_(std::make_unique<Impl>(std::move(config),
                                       std::move(message_handler),
                                       std::move(disconnect_handler)))
    {
    }

    RemoteFrameGraphClient::~RemoteFrameGraphClient() = default;

    bool RemoteFrameGraphClient::start()
    {
        return impl_->start();
    }

    void RemoteFrameGraphClient::stop()
    {
        impl_->stop();
    }

    bool RemoteFrameGraphClient::send_command(const Command& command)
    {
        return impl_->enqueue(command);
    }

    ClientStatus RemoteFrameGraphClient::status() const
    {
        return {
            impl_->running.load(std::memory_order_acquire),
            impl_->connected.load(std::memory_order_acquire),
            impl_->connection_attempts.load(std::memory_order_relaxed),
            impl_->sessions.load(std::memory_order_relaxed),
            impl_->rejected_commands.load(std::memory_order_relaxed),
        };
    }

} // namespace termin::framegraph_remote_client
