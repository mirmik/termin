#include <termin/framegraph_remote_client/client.hpp>

#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <map>
#include <mutex>
#include <optional>
#include <set>
#include <string>
#include <thread>
#include <utility>

using namespace std::chrono_literals;
using namespace termin::framegraph_remote;
using namespace termin::framegraph_remote_client;

namespace {

    struct PendingBlob {
        CaptureMetadata metadata;
        std::uint64_t received_bytes = 0;
    };

    struct ObservedState {
        std::mutex mutex;
        std::condition_variable changed;
        std::optional<TargetHello> hello;
        std::optional<TopologySnapshot> topology;
        std::map<std::uint64_t, Status> statuses;
        std::map<std::uint64_t, std::set<StatusCode>> status_codes;
        std::map<std::uint64_t, PendingBlob> blobs;
        std::set<std::uint64_t> completed_snapshot_requests;
        std::set<std::uint64_t> completed_preview_requests;
        std::map<std::uint64_t, std::set<std::uint16_t>> completed_burst_indices;
        std::uint64_t drop_events = 0;
        std::string error;
        std::string disconnect_detail;
        std::atomic<bool> slow_receiver = false;
    };

    bool parse_port(const char* text, std::uint16_t& port) {
        char* end = nullptr;
        const unsigned long parsed = std::strtoul(text, &end, 10);
        if (!text[0] || !end || *end || parsed == 0 || parsed > 65535) {
            return false;
        }
        port = static_cast<std::uint16_t>(parsed);
        return true;
    }

    bool wait_for(ObservedState& state, const auto& predicate, std::chrono::milliseconds timeout = 8s) {
        std::unique_lock lock(state.mutex);
        return state.changed.wait_for(lock, timeout, predicate);
    }

    bool status_is(const ObservedState& state, std::uint64_t request_id, StatusCode code) {
        const auto found = state.status_codes.find(request_id);
        return found != state.status_codes.end() && found->second.contains(code);
    }

    Command topology_command(std::uint64_t request_id, CommandKind kind, const TopologySnapshot& topology) {
        Command command;
        command.request_id = request_id;
        command.kind = kind;
        command.target_id = topology.selected_target_id;
        command.graph_revision = topology.graph_revision;
        command.selector_kind = CaptureSelectorKind::resource;
        command.resource = topology.resources.front();
        return command;
    }

    void observe_message(ObservedState& observed, const DecodedMessage& decoded) {
        const bool slow_capture = std::holds_alternative<CaptureMetadata>(decoded.message) ||
                                  std::holds_alternative<BlobChunk>(decoded.message);
        if (slow_capture && observed.slow_receiver.load()) {
            std::this_thread::sleep_for(300ms);
        }

        std::lock_guard lock(observed.mutex);
        if (const auto* hello = std::get_if<TargetHello>(&decoded.message)) {
            observed.hello = *hello;
        } else if (const auto* topology = std::get_if<TopologySnapshot>(&decoded.message)) {
            observed.topology = *topology;
        } else if (const auto* status = std::get_if<Status>(&decoded.message)) {
            observed.statuses[status->request_id] = *status;
            observed.status_codes[status->request_id].insert(status->code);
        } else if (const auto* metadata = std::get_if<CaptureMetadata>(&decoded.message)) {
            observed.blobs[metadata->blob_id] = {*metadata, 0};
        } else if (const auto* chunk = std::get_if<BlobChunk>(&decoded.message)) {
            const auto found = observed.blobs.find(chunk->blob_id);
            if (found == observed.blobs.end()) {
                observed.error = "blob chunk arrived before metadata";
            } else {
                found->second.received_bytes += chunk->bytes.size();
                if (found->second.received_bytes == found->second.metadata.byte_count) {
                    const CaptureMetadata metadata = found->second.metadata;
                    if (metadata.kind == CaptureKind::snapshot) {
                        observed.completed_snapshot_requests.insert(metadata.request_id);
                    } else if (metadata.kind == CaptureKind::preview) {
                        observed.completed_preview_requests.insert(metadata.request_id);
                    } else if (metadata.kind == CaptureKind::burst) {
                        observed.completed_burst_indices[metadata.request_id].insert(metadata.burst_index);
                    }
                    observed.blobs.erase(found);
                } else if (found->second.received_bytes > found->second.metadata.byte_count) {
                    observed.error = "blob exceeds advertised byte count";
                }
            }
        } else if (const auto* drop = std::get_if<DropEvent>(&decoded.message)) {
            observed.drop_events += drop->dropped_items;
        } else if (const auto* error = std::get_if<ErrorEvent>(&decoded.message)) {
            observed.error = error->detail;
        }
        observed.changed.notify_all();
    }

    bool send_and_wait(RemoteFrameGraphClient& client,
                       ObservedState& observed,
                       const Command& command,
                       StatusCode code,
                       std::chrono::milliseconds timeout = 8s) {
        if (!client.send_command(command)) {
            return false;
        }
        return wait_for(
            observed,
            [&] { return status_is(observed, command.request_id, code) || !observed.error.empty(); },
            timeout);
    }

    int run_client(std::uint16_t port, const std::string& token) {
        ObservedState observed;
        ClientConfig config;
        config.port = port;
        config.authentication_token = token;
        config.reconnect = false;
        RemoteFrameGraphClient client(
            config,
            [&](const DecodedMessage& decoded) { observe_message(observed, decoded); },
            [&](std::string detail) {
                std::lock_guard lock(observed.mutex);
                observed.disconnect_detail = std::move(detail);
                observed.changed.notify_all();
            });

        if (!client.start() ||
            !wait_for(observed, [&] { return observed.hello.has_value() || !observed.error.empty(); })) {
            std::cerr << "Remote target handshake timed out\n";
            client.stop();
            return 1;
        }

        Command refresh;
        refresh.request_id = 1;
        refresh.kind = CommandKind::refresh_topology;
        if (!client.send_command(refresh) || !wait_for(observed, [&] {
                return (observed.topology.has_value() && status_is(observed, 1, StatusCode::completed)) ||
                       !observed.error.empty();
            })) {
            std::cerr << "Topology refresh timed out\n";
            client.stop();
            return 1;
        }

        TopologySnapshot topology;
        std::uint64_t first_session = 0;
        {
            std::lock_guard lock(observed.mutex);
            topology = *observed.topology;
            if (!observed.error.empty() || topology.targets.empty() || topology.passes.empty() ||
                topology.resources.empty() || topology.selected_target_id == 0) {
                std::cerr << "Target returned an incomplete topology: " << observed.error << '\n';
                client.stop();
                return 1;
            }
            first_session = client.status().sessions;
        }

        Command stale = topology_command(2, CommandKind::select_target, topology);
        stale.graph_revision += 1;
        if (!send_and_wait(client, observed, stale, StatusCode::stale_revision)) {
            std::cerr << "Stale revision check timed out\n";
            client.stop();
            return 1;
        }

        Command snapshot = topology_command(3, CommandKind::capture_snapshot, topology);
        snapshot.encoding = CaptureEncoding::native_pixels;
        if (!send_and_wait(client, observed, snapshot, StatusCode::accepted) || !wait_for(observed, [&] {
                return (observed.completed_snapshot_requests.contains(3) &&
                        status_is(observed, 3, StatusCode::completed)) ||
                       !observed.error.empty();
            })) {
            {
                std::lock_guard lock(observed.mutex);
                std::cerr << "Exact snapshot timed out: error='" << observed.error
                          << "' pending_blobs=" << observed.blobs.size()
                          << " completed=" << observed.completed_snapshot_requests.contains(3);
                const auto found = observed.status_codes.find(3);
                if (found != observed.status_codes.end()) {
                    std::cerr << " status_codes=";
                    for (StatusCode code : found->second) {
                        std::cerr << static_cast<int>(code) << ',';
                    }
                }
                const auto latest = observed.statuses.find(3);
                if (latest != observed.statuses.end()) {
                    std::cerr << " detail='" << latest->second.detail << "'";
                }
                std::cerr << '\n';
            }
            client.stop();
            return 1;
        }

        Command stream = topology_command(4, CommandKind::start_stream, topology);
        stream.encoding = CaptureEncoding::rgba8;
        stream.max_preview_millifps = 20'000;
        stream.max_preview_long_edge = 256;
        if (!send_and_wait(client, observed, stream, StatusCode::accepted) || !wait_for(observed, [&] {
                return observed.completed_preview_requests.contains(4) || !observed.error.empty();
            })) {
            std::cerr << "Live preview timed out\n";
            client.stop();
            return 1;
        }
        Command stop = topology_command(5, CommandKind::stop_stream, topology);
        if (!send_and_wait(client, observed, stop, StatusCode::completed)) {
            std::cerr << "Live preview stop timed out\n";
            client.stop();
            return 1;
        }

        Command burst = topology_command(6, CommandKind::capture_burst, topology);
        burst.encoding = CaptureEncoding::native_pixels;
        burst.burst_frames = 3;
        if (!send_and_wait(client, observed, burst, StatusCode::accepted) ||
            !wait_for(
                observed,
                [&] {
                    const auto found = observed.completed_burst_indices.find(6);
                    return (found != observed.completed_burst_indices.end() && found->second.size() == 3 &&
                            status_is(observed, 6, StatusCode::completed)) ||
                           !observed.error.empty();
                },
                12s)) {
            std::cerr << "Burst capture timed out\n";
            client.stop();
            return 1;
        }

        Command cancelled = topology_command(7, CommandKind::capture_burst, topology);
        cancelled.encoding = CaptureEncoding::native_pixels;
        cancelled.burst_frames = 6;
        Command cancel;
        cancel.request_id = 8;
        cancel.kind = CommandKind::cancel;
        if (!client.send_command(cancelled) || !client.send_command(cancel) || !wait_for(observed, [&] {
                return (status_is(observed, 7, StatusCode::cancelled) &&
                        status_is(observed, 8, StatusCode::cancelled)) ||
                       !observed.error.empty();
            })) {
            std::cerr << "Capture cancellation timed out\n";
            client.stop();
            return 1;
        }

        Command slow_stream = topology_command(9, CommandKind::start_stream, topology);
        slow_stream.encoding = CaptureEncoding::rgba8;
        slow_stream.max_preview_millifps = 60'000;
        slow_stream.max_preview_long_edge = 256;
        observed.slow_receiver = true;
        if (!send_and_wait(client, observed, slow_stream, StatusCode::accepted)) {
            observed.slow_receiver = false;
            std::cerr << "Slow receiver stream start timed out\n";
            client.stop();
            return 1;
        }
        std::this_thread::sleep_for(4s);
        observed.slow_receiver = false;
        if (!wait_for(observed, [&] { return observed.drop_events > 0 || !observed.error.empty(); }, 12s)) {
            std::cerr << "Slow receiver did not observe bounded drops\n";
            client.stop();
            return 1;
        }
        Command slow_stop = topology_command(10, CommandKind::stop_stream, topology);
        if (!send_and_wait(client, observed, slow_stop, StatusCode::completed)) {
            std::cerr << "Slow receiver stream stop timed out\n";
            client.stop();
            return 1;
        }

        client.stop();

        ObservedState reconnected;
        RemoteFrameGraphClient second(std::move(config),
                                      [&](const DecodedMessage& decoded) { observe_message(reconnected, decoded); });
        if (!second.start() ||
            !wait_for(reconnected, [&] { return reconnected.hello.has_value() || !reconnected.error.empty(); })) {
            std::cerr << "Reconnect handshake timed out\n";
            second.stop();
            return 1;
        }
        Command second_refresh;
        second_refresh.request_id = 12;
        second_refresh.kind = CommandKind::refresh_topology;
        if (!second.send_command(second_refresh) || !wait_for(reconnected, [&] {
                return (reconnected.topology.has_value() && status_is(reconnected, 12, StatusCode::completed)) ||
                       !reconnected.error.empty();
            })) {
            std::cerr << "Reconnect topology refresh timed out\n";
            second.stop();
            return 1;
        }
        second.stop();

        std::uint64_t drops = 0;
        {
            std::lock_guard lock(observed.mutex);
            if (!observed.error.empty()) {
                std::cerr << observed.error << '\n';
                return 1;
            }
            drops = observed.drop_events;
        }
        const auto hello = *observed.hello;
        std::cout << "target=" << hello.platform << '/' << hello.abi << " pid=" << hello.process_id
                  << " topology_revision=" << topology.graph_revision << " targets=" << topology.targets.size()
                  << " passes=" << topology.passes.size() << " resources=" << topology.resources.size()
                  << " drops=" << drops << " reconnect_sessions=" << first_session + 1 << '\n';
        return 0;
    }

} // namespace

int main(int argc, char** argv) {
    if (argc != 3) {
        std::cerr << "Usage: " << argv[0] << " PORT TOKEN\n";
        return 2;
    }
    std::uint16_t port = 0;
    if (!parse_port(argv[1], port) || !argv[2][0]) {
        std::cerr << "PORT must be in 1..65535 and TOKEN must be non-empty\n";
        return 2;
    }
    return run_client(port, argv[2]);
}
