#include <termin/profiler_app/android_bridge.hpp>

#include <array>
#include <atomic>
#include <cctype>
#include <charconv>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <random>
#include <sstream>
#include <stop_token>
#include <thread>
#include <utility>

#if defined(_WIN32)
#define NOMINMAX
#include <windows.h>
#else
#include <cerrno>
#include <csignal>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

namespace termin::profiler_app {
    namespace {

        constexpr auto kCommandTimeout = std::chrono::seconds(8);
        constexpr std::size_t kOutputLimit = 64 * 1024;

        std::string trim(std::string value) {
            while (!value.empty() && std::isspace(static_cast<unsigned char>(value.back()))) {
                value.pop_back();
            }
            std::size_t first = 0;
            while (first < value.size() && std::isspace(static_cast<unsigned char>(value[first]))) {
                ++first;
            }
            return value.substr(first);
        }

        bool valid_component_part(std::string_view value) {
            if (value.empty()) {
                return false;
            }
            for (const unsigned char character : value) {
                if (!(std::isalnum(character) || character == '.' || character == '_' || character == '$')) {
                    return false;
                }
            }
            return true;
        }

        std::string random_token() {
            std::random_device source;
            static constexpr char hexadecimal[] = "0123456789abcdef";
            std::string token;
            token.reserve(32);
            for (int index = 0; index < 16; ++index) {
                const unsigned int value = source() & 0xffU;
                token.push_back(hexadecimal[value >> 4U]);
                token.push_back(hexadecimal[value & 0x0fU]);
            }
            return token;
        }

#if defined(_WIN32)
        std::wstring widen(std::string_view value) {
            if (value.empty()) {
                return {};
            }
            const int size = MultiByteToWideChar(CP_UTF8, 0, value.data(), static_cast<int>(value.size()), nullptr, 0);
            if (size <= 0) {
                return {};
            }
            std::wstring result(static_cast<std::size_t>(size), L'\0');
            MultiByteToWideChar(CP_UTF8, 0, value.data(), static_cast<int>(value.size()), result.data(), size);
            return result;
        }

        std::wstring quote_windows_argument(std::string_view argument) {
            const std::wstring value = widen(argument);
            if (value.find_first_of(L" \t\"") == std::wstring::npos) {
                return value;
            }
            std::wstring result = L"\"";
            std::size_t slashes = 0;
            for (const wchar_t character : value) {
                if (character == L'\\') {
                    ++slashes;
                } else if (character == L'\"') {
                    result.append(slashes * 2 + 1, L'\\');
                    result.push_back(character);
                    slashes = 0;
                } else {
                    result.append(slashes, L'\\');
                    slashes = 0;
                    result.push_back(character);
                }
            }
            result.append(slashes * 2, L'\\');
            result.push_back(L'\"');
            return result;
        }

        ProcessResult run_direct(const std::vector<std::string>& arguments, std::chrono::milliseconds timeout) {
            ProcessResult result;
            if (arguments.empty()) {
                result.error = "empty process command";
                return result;
            }
            SECURITY_ATTRIBUTES security{sizeof(SECURITY_ATTRIBUTES), nullptr, TRUE};
            HANDLE read_pipe = nullptr;
            HANDLE write_pipe = nullptr;
            if (!CreatePipe(&read_pipe, &write_pipe, &security, 0)) {
                result.error = "cannot create process output pipe";
                return result;
            }
            SetHandleInformation(read_pipe, HANDLE_FLAG_INHERIT, 0);
            std::wstring command_line;
            for (const std::string& argument : arguments) {
                if (!command_line.empty()) {
                    command_line.push_back(L' ');
                }
                command_line += quote_windows_argument(argument);
            }
            STARTUPINFOW startup{};
            startup.cb = sizeof(startup);
            startup.dwFlags = STARTF_USESTDHANDLES;
            startup.hStdOutput = write_pipe;
            startup.hStdError = write_pipe;
            startup.hStdInput = GetStdHandle(STD_INPUT_HANDLE);
            PROCESS_INFORMATION process{};
            std::vector<wchar_t> mutable_line(command_line.begin(), command_line.end());
            mutable_line.push_back(L'\0');
            const BOOL started = CreateProcessW(nullptr,
                                                mutable_line.data(),
                                                nullptr,
                                                nullptr,
                                                TRUE,
                                                CREATE_NO_WINDOW,
                                                nullptr,
                                                nullptr,
                                                &startup,
                                                &process);
            CloseHandle(write_pipe);
            if (!started) {
                CloseHandle(read_pipe);
                result.error = "cannot start adb";
                return result;
            }
            const auto deadline = std::chrono::steady_clock::now() + timeout;
            std::array<char, 4096> buffer{};
            while (true) {
                DWORD available = 0;
                if (PeekNamedPipe(read_pipe, nullptr, 0, nullptr, &available, nullptr) && available > 0) {
                    DWORD read = 0;
                    if (ReadFile(read_pipe,
                                 buffer.data(),
                                 static_cast<DWORD>(std::min<std::size_t>(buffer.size(), available)),
                                 &read,
                                 nullptr) &&
                        result.output.size() < kOutputLimit) {
                        result.output.append(buffer.data(),
                                             std::min<std::size_t>(read, kOutputLimit - result.output.size()));
                    }
                }
                if (WaitForSingleObject(process.hProcess, 10) == WAIT_OBJECT_0) {
                    break;
                }
                if (std::chrono::steady_clock::now() >= deadline) {
                    result.timed_out = true;
                    TerminateProcess(process.hProcess, 1);
                    WaitForSingleObject(process.hProcess, INFINITE);
                    break;
                }
            }
            DWORD exit_code = 1;
            GetExitCodeProcess(process.hProcess, &exit_code);
            result.exit_code = static_cast<int>(exit_code);
            CloseHandle(process.hThread);
            CloseHandle(process.hProcess);
            CloseHandle(read_pipe);
            return result;
        }
#else
        ProcessResult run_direct(const std::vector<std::string>& arguments, std::chrono::milliseconds timeout) {
            ProcessResult result;
            if (arguments.empty()) {
                result.error = "empty process command";
                return result;
            }
            std::vector<char*> argv;
            argv.reserve(arguments.size() + 1);
            for (const std::string& argument : arguments) {
                argv.push_back(const_cast<char*>(argument.c_str()));
            }
            argv.push_back(nullptr);
            int pipe_fds[2] = {-1, -1};
            if (pipe(pipe_fds) != 0) {
                result.error = "cannot create process output pipe";
                return result;
            }
            const pid_t child = fork();
            if (child < 0) {
                close(pipe_fds[0]);
                close(pipe_fds[1]);
                result.error = "cannot fork adb process";
                return result;
            }
            if (child == 0) {
                dup2(pipe_fds[1], STDOUT_FILENO);
                dup2(pipe_fds[1], STDERR_FILENO);
                close(pipe_fds[0]);
                close(pipe_fds[1]);
                execvp(argv[0], argv.data());
                _exit(127);
            }
            close(pipe_fds[1]);
            const int flags = fcntl(pipe_fds[0], F_GETFL, 0);
            fcntl(pipe_fds[0], F_SETFL, flags | O_NONBLOCK);
            const auto deadline = std::chrono::steady_clock::now() + timeout;
            std::array<char, 4096> buffer{};
            int status = 0;
            while (true) {
                const ssize_t count = read(pipe_fds[0], buffer.data(), buffer.size());
                if (count > 0 && result.output.size() < kOutputLimit) {
                    result.output.append(
                        buffer.data(),
                        std::min<std::size_t>(static_cast<std::size_t>(count), kOutputLimit - result.output.size()));
                }
                const pid_t waited = waitpid(child, &status, WNOHANG);
                if (waited == child) {
                    break;
                }
                if (waited < 0) {
                    result.error = "cannot wait for adb process";
                    break;
                }
                if (std::chrono::steady_clock::now() >= deadline) {
                    result.timed_out = true;
                    kill(child, SIGKILL);
                    waitpid(child, &status, 0);
                    break;
                }
                std::this_thread::sleep_for(std::chrono::milliseconds(10));
            }
            while (true) {
                const ssize_t count = read(pipe_fds[0], buffer.data(), buffer.size());
                if (count <= 0) {
                    break;
                }
                if (result.output.size() < kOutputLimit) {
                    result.output.append(
                        buffer.data(),
                        std::min<std::size_t>(static_cast<std::size_t>(count), kOutputLimit - result.output.size()));
                }
            }
            close(pipe_fds[0]);
            if (!result.timed_out && result.error.empty()) {
                result.exit_code = WIFEXITED(status) ? WEXITSTATUS(status) : 1;
            }
            return result;
        }
#endif

        std::string command_failure(std::string_view operation, const ProcessResult& result) {
            if (!result.error.empty()) {
                return std::string(operation) + ": " + result.error;
            }
            if (result.timed_out) {
                return std::string(operation) + " timed out";
            }
            const std::string detail = trim(result.output);
            if (!detail.empty() && detail.size() < 240) {
                return std::string(operation) + " failed: " + detail;
            }
            return std::string(operation) + " failed (exit " + std::to_string(result.exit_code) + ")";
        }

    } // namespace

    std::vector<AndroidDevice> parse_adb_devices(std::string_view output) {
        std::vector<AndroidDevice> devices;
        std::istringstream lines{std::string(output)};
        std::string line;
        while (std::getline(lines, line)) {
            line = trim(std::move(line));
            if (line.empty() || line.starts_with("List of devices attached") || line.front() == '*') {
                continue;
            }
            std::istringstream fields(line);
            AndroidDevice device;
            fields >> device.serial >> device.state;
            std::getline(fields, device.description);
            device.description = trim(std::move(device.description));
            if (!device.serial.empty() && !device.state.empty()) {
                devices.push_back(std::move(device));
            }
        }
        return devices;
    }

    struct AndroidProfilerBridge::Impl {
        explicit Impl(ProcessRunner configured_runner)
            : runner(configured_runner ? std::move(configured_runner) : ProcessRunner(run_direct)) {}

        ProcessResult run(const std::vector<std::string>& args) const {
            return runner(args, kCommandTimeout);
        }

        void publish(AndroidBridgePhase phase, std::string status, bool busy) {
            std::lock_guard lock(mutex);
            snapshot.phase = phase;
            snapshot.status = std::move(status);
            snapshot.busy = busy;
            ++snapshot.revision;
        }

        void join_finished() {
            if (worker.joinable()) {
                bool is_busy = false;
                {
                    std::lock_guard lock(mutex);
                    is_busy = snapshot.busy;
                }
                if (!is_busy) {
                    worker.join();
                }
            }
        }

        bool begin_operation(AndroidBridgePhase phase, std::string status) {
            join_finished();
            std::lock_guard lock(mutex);
            if (closed || snapshot.busy) {
                return false;
            }
            snapshot.phase = phase;
            snapshot.status = std::move(status);
            snapshot.busy = true;
            ++snapshot.revision;
            return true;
        }

        void remove_route(const std::string& adb_path, const std::string& serial, std::uint16_t port) const {
            if (serial.empty() || port == 0) {
                return;
            }
            const ProcessResult removed =
                run({adb_path, "-s", serial, "forward", "--remove", "tcp:" + std::to_string(port)});
            if (removed.exit_code != 0) {
                std::fprintf(stderr,
                             "termin_profiler: %s\n",
                             command_failure("removing owned Android forward", removed).c_str());
            }
        }

        mutable std::mutex mutex;
        ProcessRunner runner;
        std::jthread worker;
        AndroidBridgeSnapshot snapshot;
        std::optional<PendingProfilerConnection> pending;
        std::string route_adb_path;
        std::string route_serial;
        std::uint16_t route_port = 0;
        std::atomic_bool cancel_connect = false;
        bool closed = false;
    };

    AndroidProfilerBridge::AndroidProfilerBridge(ProcessRunner runner)
        : impl_(std::make_unique<Impl>(std::move(runner))) {}

    AndroidProfilerBridge::~AndroidProfilerBridge() {
        close();
    }

    bool AndroidProfilerBridge::refresh_devices(std::string adb_path) {
        if (!impl_->begin_operation(AndroidBridgePhase::Refreshing, "Discovering Android devices...")) {
            return false;
        }
        impl_->worker = std::jthread([this, adb_path = std::move(adb_path)] {
            const ProcessResult result = impl_->run({adb_path, "devices", "-l"});
            if (result.exit_code != 0) {
                const std::string failure = command_failure("ADB device discovery", result);
                std::fprintf(stderr, "termin_profiler: %s\n", failure.c_str());
                impl_->publish(AndroidBridgePhase::Error, failure, false);
                return;
            }
            std::vector<AndroidDevice> devices = parse_adb_devices(result.output);
            std::size_t ready = 0;
            for (const AndroidDevice& device : devices) {
                ready += device.ready() ? 1U : 0U;
            }
            std::string status;
            if (devices.empty()) {
                status = "No Android devices found. Check USB debugging and the headset connection.";
            } else if (ready == 0) {
                status = "Devices found, but none are ready. Authorize USB debugging in the headset.";
            } else {
                status = std::to_string(ready) + " ready device" + (ready == 1 ? "" : "s") + " found.";
            }
            std::lock_guard lock(impl_->mutex);
            impl_->snapshot.devices = std::move(devices);
            impl_->snapshot.phase = AndroidBridgePhase::Ready;
            impl_->snapshot.status = std::move(status);
            impl_->snapshot.busy = false;
            ++impl_->snapshot.revision;
        });
        return true;
    }

    bool AndroidProfilerBridge::connect(AndroidConnectRequest request) {
        const AndroidBridgeSnapshot current = snapshot();
        if (current.busy) {
            return false;
        }
        if (current.route_active) {
            impl_->publish(AndroidBridgePhase::Error,
                           "Disconnect the current Android profiler route before connecting again.",
                           false);
            return false;
        }
        if (!valid_component_part(request.package_name)) {
            impl_->publish(AndroidBridgePhase::Error, "Package must be a non-empty Android application id.", false);
            return false;
        }
        if (!valid_component_part(request.activity_name)) {
            impl_->publish(AndroidBridgePhase::Error, "Activity must be a non-empty Android class name.", false);
            return false;
        }
        if (request.serial.empty()) {
            impl_->publish(AndroidBridgePhase::Error, "Select a ready Android device first.", false);
            return false;
        }
        if (!impl_->begin_operation(AndroidBridgePhase::Connecting, "Preparing the Android profiler connection...")) {
            return false;
        }
        impl_->cancel_connect.store(false);
        impl_->worker = std::jthread([this, request = std::move(request)] {
            auto fail =
                [this](std::string failure, std::uint16_t forwarded_port, const AndroidConnectRequest& active_request) {
                    if (forwarded_port != 0) {
                        impl_->remove_route(active_request.adb_path, active_request.serial, forwarded_port);
                    }
                    std::fprintf(stderr, "termin_profiler: %s\n", failure.c_str());
                    impl_->publish(AndroidBridgePhase::Error, std::move(failure), false);
                };
            auto cancelled = [this, &request](std::uint16_t forwarded_port) {
                if (!impl_->cancel_connect.load()) {
                    return false;
                }
                if (forwarded_port != 0) {
                    impl_->remove_route(request.adb_path, request.serial, forwarded_port);
                }
                impl_->publish(AndroidBridgePhase::Ready, "Android profiler connection cancelled.", false);
                return true;
            };

            ProcessResult result = impl_->run({request.adb_path, "-s", request.serial, "get-state"});
            if (cancelled(0)) {
                return;
            }
            if (result.exit_code != 0 || trim(result.output) != "device") {
                fail(command_failure("checking the selected Android device", result), 0, request);
                return;
            }

            result = impl_->run({request.adb_path,
                                 "-s",
                                 request.serial,
                                 "forward",
                                 "tcp:0",
                                 "tcp:" + std::to_string(request.device_port)});
            std::uint16_t host_port = 0;
            const std::string port_text = trim(result.output);
            unsigned int parsed_port = 0;
            const auto parsed = std::from_chars(port_text.data(), port_text.data() + port_text.size(), parsed_port);
            if (result.exit_code != 0 || parsed.ec != std::errc{} ||
                parsed.ptr != port_text.data() + port_text.size() || parsed_port == 0 || parsed_port > 65535) {
                fail(command_failure("creating the Android port forward", result), 0, request);
                return;
            }
            host_port = static_cast<std::uint16_t>(parsed_port);
            if (cancelled(host_port)) {
                return;
            }

            result =
                impl_->run({request.adb_path, "-s", request.serial, "shell", "am", "force-stop", request.package_name});
            if (cancelled(host_port)) {
                return;
            }
            if (result.exit_code != 0) {
                fail(command_failure("stopping the Android application", result), host_port, request);
                return;
            }

            std::string token = random_token();
            result = impl_->run({request.adb_path,
                                 "-s",
                                 request.serial,
                                 "shell",
                                 "am",
                                 "start",
                                 "-n",
                                 request.package_name + "/" + request.activity_name,
                                 "--ez",
                                 "termin.profiler.remote",
                                 "true",
                                 "--ei",
                                 "termin.profiler.port",
                                 std::to_string(request.device_port),
                                 "--es",
                                 "termin.profiler.token",
                                 token});
            if (cancelled(host_port)) {
                return;
            }
            if (result.exit_code != 0) {
                fail("Starting the Android application with remote profiling failed.", host_port, request);
                return;
            }

            {
                std::lock_guard lock(impl_->mutex);
                if (!impl_->cancel_connect.load()) {
                    impl_->route_adb_path = request.adb_path;
                    impl_->route_serial = request.serial;
                    impl_->route_port = host_port;
                    impl_->pending = PendingProfilerConnection{host_port, std::move(token)};
                    impl_->snapshot.phase = AndroidBridgePhase::Routed;
                    impl_->snapshot.status = "Android application started; connecting to its profiler...";
                    impl_->snapshot.busy = false;
                    impl_->snapshot.route_active = true;
                    impl_->snapshot.routed_serial = request.serial;
                    impl_->snapshot.host_port = host_port;
                    ++impl_->snapshot.revision;
                    return;
                }
            }
            impl_->remove_route(request.adb_path, request.serial, host_port);
            impl_->publish(AndroidBridgePhase::Ready, "Android profiler connection cancelled.", false);
        });
        return true;
    }

    bool AndroidProfilerBridge::disconnect() {
        {
            std::lock_guard lock(impl_->mutex);
            if (impl_->snapshot.busy && impl_->snapshot.phase == AndroidBridgePhase::Connecting) {
                impl_->cancel_connect.store(true);
                impl_->snapshot.status = "Cancelling the Android profiler connection...";
                ++impl_->snapshot.revision;
                return true;
            }
        }
        if (!impl_->begin_operation(AndroidBridgePhase::Disconnecting, "Removing the Android profiler route...")) {
            return false;
        }
        std::string adb_path;
        std::string serial;
        std::uint16_t port = 0;
        {
            std::lock_guard lock(impl_->mutex);
            adb_path = impl_->route_adb_path;
            serial = impl_->route_serial;
            port = impl_->route_port;
            impl_->pending.reset();
        }
        impl_->worker = std::jthread([this, adb_path = std::move(adb_path), serial = std::move(serial), port] {
            impl_->remove_route(adb_path, serial, port);
            std::lock_guard lock(impl_->mutex);
            impl_->route_adb_path.clear();
            impl_->route_serial.clear();
            impl_->route_port = 0;
            impl_->snapshot.phase = AndroidBridgePhase::Ready;
            impl_->snapshot.status = "Android profiler disconnected.";
            impl_->snapshot.busy = false;
            impl_->snapshot.route_active = false;
            impl_->snapshot.routed_serial.clear();
            impl_->snapshot.host_port = 0;
            ++impl_->snapshot.revision;
        });
        return true;
    }

    void AndroidProfilerBridge::close() {
        if (!impl_) {
            return;
        }
        {
            std::lock_guard lock(impl_->mutex);
            if (impl_->closed) {
                return;
            }
            impl_->closed = true;
            impl_->cancel_connect.store(true);
        }
        if (impl_->worker.joinable()) {
            impl_->worker.join();
        }
        std::string adb_path;
        std::string serial;
        std::uint16_t port = 0;
        {
            std::lock_guard lock(impl_->mutex);
            adb_path = impl_->route_adb_path;
            serial = impl_->route_serial;
            port = impl_->route_port;
            impl_->route_adb_path.clear();
            impl_->route_serial.clear();
            impl_->route_port = 0;
            impl_->pending.reset();
        }
        impl_->remove_route(adb_path, serial, port);
        std::lock_guard lock(impl_->mutex);
        impl_->snapshot.phase = AndroidBridgePhase::Closed;
        impl_->snapshot.status = "Android bridge closed.";
        impl_->snapshot.busy = false;
        impl_->snapshot.route_active = false;
        ++impl_->snapshot.revision;
    }

    AndroidBridgeSnapshot AndroidProfilerBridge::snapshot() const {
        std::lock_guard lock(impl_->mutex);
        return impl_->snapshot;
    }

    std::optional<PendingProfilerConnection> AndroidProfilerBridge::take_pending_connection() {
        std::lock_guard lock(impl_->mutex);
        std::optional<PendingProfilerConnection> pending = std::move(impl_->pending);
        impl_->pending.reset();
        return pending;
    }

} // namespace termin::profiler_app
