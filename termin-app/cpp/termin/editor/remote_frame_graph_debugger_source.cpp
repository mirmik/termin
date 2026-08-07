#include "termin/editor/remote_frame_graph_debugger_source.hpp"

#include <termin/framegraph_remote_client/client.hpp>
#include <termin/render/frame_graph_capture.hpp>
#include <tgfx2/descriptors.hpp>
#include <tgfx2/i_render_device.hpp>
#include <tgfx2/render_context.hpp>

#include <algorithm>
#include <chrono>
#include <cstring>
#include <iomanip>
#include <limits>
#include <mutex>
#include <sstream>
#include <stdexcept>
#include <unordered_map>
#include <utility>
#include <variant>

#include <tcbase/tc_log.h>

namespace termin
{
    namespace
    {

        using namespace framegraph_remote;
        using Clock = std::chrono::steady_clock;

        framegraph_remote_client::ClientConfig
        project_client_config(RemoteFrameGraphConnectionConfig config)
        {
            framegraph_remote_client::ClientConfig result;
            result.port = config.port;
            result.authentication_token =
                std::move(config.authentication_token);
            result.command_queue_capacity = config.command_queue_capacity;
            result.max_blob_bytes = config.capture_memory_budget_bytes;
            result.reconnect = config.reconnect;
            return result;
        }

        FrameGraphDebuggerState project_state(SessionState state)
        {
            switch (state)
            {
            case SessionState::waiting_capture:
                return FrameGraphDebuggerState::WaitingFrame;
            case SessionState::suspended:
                return FrameGraphDebuggerState::Suspended;
            case SessionState::error:
                return FrameGraphDebuggerState::Error;
            case SessionState::idle:
            case SessionState::waiting_topology:
            case SessionState::streaming:
                return FrameGraphDebuggerState::Bound;
            }
            return FrameGraphDebuggerState::Error;
        }

        FrameGraphDebuggerPixelFormat project_pixel_format(PixelFormat format)
        {
            switch (format)
            {
            case PixelFormat::rgba8_unorm:
                return FrameGraphDebuggerPixelFormat::Rgba8Unorm;
            case PixelFormat::rgba16_float:
                return FrameGraphDebuggerPixelFormat::Rgba16Float;
            case PixelFormat::rgba32_float:
                return FrameGraphDebuggerPixelFormat::Rgba32Float;
            case PixelFormat::depth16_unorm:
                return FrameGraphDebuggerPixelFormat::Depth16Unorm;
            case PixelFormat::depth32_float:
                return FrameGraphDebuggerPixelFormat::Depth32Float;
            case PixelFormat::unknown:
                return FrameGraphDebuggerPixelFormat::Unknown;
            }
            return FrameGraphDebuggerPixelFormat::Unknown;
        }

        std::string topology_summary(const TopologySnapshot& topology)
        {
            std::ostringstream stream;
            stream << "Remote graph revision " << topology.graph_revision
                   << ": " << topology.passes.size() << " passes, "
                   << topology.resources.size() << " resources\nSchedule:";
            for (std::uint64_t id : topology.schedule)
                stream << ' ' << id;
            return stream.str();
        }

        std::string pass_summary(const FrameGraphDebuggerPassSnapshot* pass)
        {
            if (!pass)
                return {};
            std::ostringstream stream;
            stream << "{\n  \"id\": " << pass->id
                   << ",\n  \"authored_index\": " << pass->authored_index
                   << ",\n  \"name\": \"" << pass->name << "\",\n  \"type\": \""
                   << pass->type << "\",\n  \"enabled\": "
                   << (pass->enabled ? "true" : "false")
                   << ",\n  \"passthrough\": "
                   << (pass->passthrough ? "true" : "false") << "\n}";
            return stream.str();
        }

    } // namespace

    class RemoteFrameGraphDebuggerSource::Impl
    {
    public:
        Impl(std::size_t target_gap_capacity, CommandSender target_sender)
            : gap_capacity(target_gap_capacity),
              sender(std::move(target_sender))
        {
            if (gap_capacity == 0)
            {
                throw std::invalid_argument(
                    "remote framegraph gap capacity must be positive");
            }
            state = std::make_shared<FrameGraphDebuggerSnapshot>();
            state->revision = 1;
            state->source_kind = FrameGraphDebuggerSourceKind::Remote;
            state->source_label = "Remote / pending";
            state->connected = false;
            state->stale = true;
            state->status_detail = "waiting for remote target handshake";
            state->capture_info =
                "Remote topology connected; image capture is not enabled";
        }

        ~Impl()
        {
            disconnect_live();
            release_gpu();
        }

        std::shared_ptr<const FrameGraphDebuggerSnapshot> snapshot() const
        {
            std::lock_guard lock(mutex);
            return state;
        }

        bool send(Command command)
        {
            std::lock_guard lock(mutex);
            if (closed || !sender || !state->connected)
                return false;
            command.request_id = next_request_id++;
            if (!sender(command))
            {
                publish_error_locked("remote command queue is full");
                return false;
            }
            pending_commands.emplace(command.request_id, command.kind);
            if (command.kind == CommandKind::refresh_topology)
            {
                refresh_pending = true;
                needs_refresh = false;
                last_refresh_request = Clock::now();
            }
            return true;
        }

        bool refresh()
        {
            {
                std::lock_guard lock(mutex);
                if (closed || !sender || !state->connected || refresh_pending)
                {
                    return false;
                }
                const bool cadence_elapsed =
                    last_refresh_request == Clock::time_point{} ||
                    Clock::now() - last_refresh_request >=
                        std::chrono::milliseconds(500);
                if (!needs_refresh && !cadence_elapsed)
                    return false;
            }
            Command command;
            command.kind = CommandKind::refresh_topology;
            return send(std::move(command));
        }

        bool select_target(std::uint64_t target_id)
        {
            Command command;
            {
                std::lock_guard lock(mutex);
                if (pending_target_id == target_id)
                    return true;
                const auto found =
                    std::find_if(state->targets.begin(),
                                 state->targets.end(),
                                 [target_id](const auto& target)
                                 { return target.id == target_id; });
                if (found == state->targets.end())
                {
                    tc_log_error(
                        "remote framegraph source: unknown target id %llu",
                        static_cast<unsigned long long>(target_id));
                    return false;
                }
                command.kind = CommandKind::select_target;
                command.target_id = target_id;
                command.graph_revision = state->graph_revision;
            }
            if (!send(std::move(command)))
                return false;
            {
                std::lock_guard lock(mutex);
                pending_target_id = target_id;
            }
            return true;
        }

        bool select_pass(std::optional<std::uint64_t> pass_id)
        {
            std::lock_guard lock(mutex);
            auto next = std::make_shared<FrameGraphDebuggerSnapshot>(*state);
            const FrameGraphDebuggerPassSnapshot* selected = nullptr;
            if (pass_id)
            {
                const auto found =
                    std::find_if(next->passes.begin(),
                                 next->passes.end(),
                                 [pass_id](const auto& pass)
                                 { return pass.id == *pass_id; });
                if (found == next->passes.end())
                {
                    tc_log_error(
                        "remote framegraph source: unknown pass id %llu",
                        static_cast<unsigned long long>(*pass_id));
                    return false;
                }
                selected = &*found;
            }
            next->selected_pass_id = pass_id;
            next->symbols = selected ? selected->internal_symbols
                                     : std::vector<std::string>{};
            if (std::find(next->symbols.begin(),
                          next->symbols.end(),
                          next->selected_symbol) == next->symbols.end())
            {
                next->selected_symbol.clear();
            }
            next->pass_json = pass_summary(selected);
            publish_locked(std::move(next));
            return true;
        }

        bool request_exact_capture()
        {
            Command command;
            {
                std::lock_guard lock(mutex);
                if (!state->connected || !state->selected_target_id ||
                    state->graph_revision == 0 || !exact_capture_supported ||
                    state->paused || assembler ||
                    std::any_of(pending_commands.begin(),
                                pending_commands.end(),
                                [](const auto& pending)
                                {
                                    return pending.second ==
                                        CommandKind::capture_snapshot;
                                }))
                    return false;
                command.kind = CommandKind::capture_snapshot;
                command.target_id = *state->selected_target_id;
                command.graph_revision = state->graph_revision;
                command.encoding = CaptureEncoding::native_pixels;
                if (state->mode == FrameGraphDebuggerMode::BetweenPasses)
                {
                    if (state->selected_resource.empty())
                        return false;
                    command.selector_kind = CaptureSelectorKind::resource;
                    command.resource = state->selected_resource;
                }
                else
                {
                    if (!state->selected_pass_id ||
                        state->selected_symbol.empty())
                        return false;
                    command.selector_kind =
                        CaptureSelectorKind::internal_symbol;
                    command.pass_id = *state->selected_pass_id;
                    command.symbol = state->selected_symbol;
                }
            }
            return send(std::move(command));
        }

        bool cancel_capture()
        {
            {
                std::lock_guard lock(mutex);
                const bool pending = assembler ||
                    std::any_of(pending_commands.begin(),
                                pending_commands.end(),
                                [](const auto& item)
                                {
                                    return item.second ==
                                        CommandKind::capture_snapshot;
                                });
                if (!pending)
                    return false;
            }
            Command command;
            command.kind = CommandKind::cancel;
            return send(std::move(command));
        }

        template <typename Mutation> void mutate(Mutation mutation)
        {
            std::lock_guard lock(mutex);
            if (closed)
                return;
            auto next = std::make_shared<FrameGraphDebuggerSnapshot>(*state);
            mutation(*next);
            publish_locked(std::move(next));
        }

        bool ingest(const DecodedMessage& decoded)
        {
            std::lock_guard lock(mutex);
            const bool starts_session =
                std::holds_alternative<TargetHello>(decoded.message);
            if (decoded.envelope.session_id == 0 ||
                decoded.envelope.sequence == 0 ||
                (starts_session &&
                 decoded.envelope.session_id == active_session_id) ||
                (!starts_session &&
                 (decoded.envelope.session_id != active_session_id ||
                  decoded.envelope.sequence <= last_sequence)))
            {
                tc_log_error(
                    "remote framegraph source: invalid session or sequence");
                return false;
            }
            auto next = std::make_shared<FrameGraphDebuggerSnapshot>(*state);
            const bool changed =
                std::visit([&](const auto& message)
                           { return apply(*next, decoded, message); },
                           decoded.message);
            if (!changed)
                return false;
            active_session_id = decoded.envelope.session_id;
            last_sequence = decoded.envelope.sequence;
            publish_locked(std::move(next));
            return true;
        }

        bool connect_live(RemoteFrameGraphConnectionConfig config)
        {
            disconnect_live();
            {
                std::lock_guard lock(mutex);
                configured_client = config;
                capture_memory_budget_bytes =
                    config.capture_memory_budget_bytes;
                closed = false;
            }
            auto next_client = std::make_unique<
                framegraph_remote_client::RemoteFrameGraphClient>(
                project_client_config(std::move(config)),
                [this](const DecodedMessage& message) { ingest(message); },
                [this](std::string detail)
                { disconnected(std::move(detail)); });
            auto* client_view = next_client.get();
            {
                std::lock_guard lock(mutex);
                client = std::move(next_client);
                sender = [client_view](const Command& command)
                { return client_view->send_command(command); };
                auto next =
                    std::make_shared<FrameGraphDebuggerSnapshot>(*state);
                next->status_detail = "connecting to remote target";
                next->stale = true;
                publish_locked(std::move(next));
            }
            if (client_view->start())
                return true;
            disconnect_live();
            disconnected("failed to start remote client");
            return false;
        }

        void connect_configured()
        {
            std::optional<RemoteFrameGraphConnectionConfig> config;
            {
                std::lock_guard lock(mutex);
                if (closed || client || !configured_client)
                    return;
                config = configured_client;
            }
            connect_live(std::move(*config));
        }

        void disconnect_live()
        {
            std::unique_ptr<framegraph_remote_client::RemoteFrameGraphClient>
                stopped;
            {
                std::lock_guard lock(mutex);
                sender = {};
                stopped = std::move(client);
            }
            if (stopped)
                stopped->stop();
        }

        void disconnected(std::string detail)
        {
            std::lock_guard lock(mutex);
            if (!state->connected && state->status_detail == detail)
                return;
            auto next = std::make_shared<FrameGraphDebuggerSnapshot>(*state);
            const bool was_connected = next->connected;
            next->connected = false;
            next->stale = true;
            next->state = FrameGraphDebuggerState::Unbound;
            next->status_detail = std::move(detail);
            next->cpu_capture.reset();
            next->main_image = {};
            next->depth_image = {};
            gpu_release_requested.store(true, std::memory_order_release);
            if (was_connected)
            {
                if (assembler)
                {
                    append_gap(*next,
                               FrameGraphDebuggerGapKind::TransportDrop,
                               1,
                               "incomplete remote capture discarded on disconnect");
                    ++next->dropped_messages;
                }
                append_gap(
                    *next,
                    FrameGraphDebuggerGapKind::Disconnect,
                    0,
                    "transport disconnected; retained topology is stale");
            }
            pending_commands.clear();
            assembler.reset();
            exact_capture_supported = false;
            pending_target_id.reset();
            refresh_pending = false;
            needs_refresh = true;
            publish_locked(std::move(next));
        }

        void close()
        {
            disconnect_live();
            {
                std::lock_guard lock(mutex);
                closed = true;
                configured_client.reset();
            }
            disconnected("remote source closed");
        }

    private:
        template <typename T>
        bool apply(FrameGraphDebuggerSnapshot&, const DecodedMessage&, const T&)
        {
            tc_log_error("remote framegraph source: unexpected message type "
                         "from target");
            return false;
        }

        bool apply(FrameGraphDebuggerSnapshot& next,
                   const DecodedMessage& decoded,
                   const TargetHello& hello)
        {
            pending_commands.clear();
            assembler.reset();
            exact_capture_supported =
                (hello.capabilities & static_cast<std::uint64_t>(
                    Capability::exact_snapshot)) != 0;
            pending_target_id.reset();
            refresh_pending = false;
            needs_refresh = true;
            next = FrameGraphDebuggerSnapshot{};
            next.source_kind = FrameGraphDebuggerSourceKind::Remote;
            next.source_label =
                "Remote / " + hello.platform + " / " + hello.abi;
            next.session_id = decoded.envelope.session_id;
            next.connected = true;
            next.stale = true;
            next.state = FrameGraphDebuggerState::Bound;
            if ((hello.capabilities &
                 static_cast<std::uint64_t>(Capability::topology)) == 0)
            {
                next.state = FrameGraphDebuggerState::Error;
                next.status_detail =
                    "remote target does not advertise topology capability";
                tc_log_error("remote framegraph source: %s",
                             next.status_detail.c_str());
            }
            else
            {
                next.status_detail =
                    "remote target connected; waiting for topology";
            }
            next.capture_info =
                "Remote topology connected; image capture is not enabled";
            return true;
        }

        bool apply(FrameGraphDebuggerSnapshot& next,
                   const DecodedMessage&,
                   const TopologySnapshot& topology)
        {
            if (next.graph_revision != 0 &&
                topology.graph_revision < next.graph_revision)
            {
                tc_log_error(
                    "remote framegraph source: topology revision regressed "
                    "from %llu to %llu",
                    static_cast<unsigned long long>(next.graph_revision),
                    static_cast<unsigned long long>(topology.graph_revision));
                return false;
            }
            pending_target_id.reset();
            next.graph_revision = topology.graph_revision;
            next.targets.clear();
            next.targets.reserve(topology.targets.size());
            for (const auto& target : topology.targets)
            {
                next.targets.push_back(
                    {target.id, target.label, target.renderable});
            }
            next.selected_target_id =
                topology.selected_target_id == 0
                    ? std::optional<std::uint64_t>{}
                    : std::optional<std::uint64_t>{topology.selected_target_id};
            next.passes.clear();
            next.passes.reserve(topology.passes.size());
            for (const auto& pass : topology.passes)
            {
                next.passes.push_back({pass.id,
                                       pass.authored_index,
                                       pass.name,
                                       pass.type,
                                       pass.enabled,
                                       pass.passthrough,
                                       pass.reads,
                                       pass.writes,
                                       pass.internal_symbols});
            }
            const auto selected_pass =
                std::find_if(next.passes.begin(),
                             next.passes.end(),
                             [&](const auto& pass)
                             { return next.selected_pass_id == pass.id; });
            if (selected_pass == next.passes.end())
            {
                next.selected_pass_id.reset();
                next.symbols.clear();
                next.selected_symbol.clear();
                next.pass_json.clear();
            }
            else
            {
                next.symbols = selected_pass->internal_symbols;
                next.pass_json = pass_summary(&*selected_pass);
            }
            next.resources = topology.resources;
            if (std::find(next.resources.begin(),
                          next.resources.end(),
                          next.selected_resource) == next.resources.end())
            {
                next.selected_resource.clear();
            }
            next.render_stats = topology.render_stats;
            next.pipeline_info = topology_summary(topology);
            next.connected = true;
            next.stale = false;
            next.state = FrameGraphDebuggerState::Bound;
            next.status_detail = "remote topology updated";
            return true;
        }

        bool apply(FrameGraphDebuggerSnapshot& next,
                   const DecodedMessage&,
                   const Status& status)
        {
            if (status.graph_revision < next.graph_revision)
            {
                tc_log_error("remote framegraph source: status revision "
                             "regressed from %llu to %llu",
                             static_cast<unsigned long long>(
                                 next.graph_revision),
                             static_cast<unsigned long long>(
                                 status.graph_revision));
                return false;
            }
            next.graph_revision = status.graph_revision;
            next.state = project_state(status.state);
            next.status_detail = status.detail;
            next.timing =
                "Target time: " + std::to_string(status.target_time_ns) +
                " ns; remote queue: " + std::to_string(status.queue_depth);
            next.dropped_messages =
                std::max(next.dropped_messages, status.dropped_captures);
            if (assembler &&
                assembler->metadata().request_id == status.request_id &&
                status.code != StatusCode::accepted)
            {
                assembler.reset();
                if (status.code != StatusCode::cancelled)
                {
                    append_gap(next,
                               FrameGraphDebuggerGapKind::TransportDrop,
                               1,
                               "capture ended before all chunks arrived");
                    ++next.dropped_messages;
                    next.state = FrameGraphDebuggerState::Error;
                    next.status_detail =
                        "capture ended before all chunks arrived";
                    tc_log_error("remote framegraph source: capture request "
                                 "%llu ended before blob completion",
                                 static_cast<unsigned long long>(
                                     status.request_id));
                }
                else
                {
                    next.capture_info = "Remote capture cancelled";
                }
            }
            const auto pending = pending_commands.find(status.request_id);
            if (pending != pending_commands.end() &&
                status.code != StatusCode::accepted)
            {
                if (pending->second == CommandKind::select_target)
                    pending_target_id.reset();
                if (pending->second == CommandKind::refresh_topology)
                {
                    refresh_pending = false;
                }
                pending_commands.erase(pending);
            }
            if (status.code == StatusCode::stale_revision)
            {
                needs_refresh = true;
                next.stale = true;
                next.status_detail =
                    "remote topology revision is stale; refreshing";
            }
            return true;
        }

        bool apply(FrameGraphDebuggerSnapshot& next,
                   const DecodedMessage&,
                   const CaptureMetadata& metadata)
        {
            const auto pending = pending_commands.find(metadata.request_id);
            if (pending == pending_commands.end() ||
                pending->second != CommandKind::capture_snapshot ||
                metadata.kind != CaptureKind::snapshot ||
                metadata.graph_revision != next.graph_revision ||
                metadata.byte_count > capture_memory_budget_bytes ||
                assembler)
            {
                tc_log_error("remote framegraph source: rejected capture "
                             "metadata for request %llu",
                             static_cast<unsigned long long>(
                                 metadata.request_id));
                return false;
            }
            assembler.emplace(metadata);
            next.state = FrameGraphDebuggerState::WaitingFrame;
            next.capture_info = "Receiving exact remote capture: 0 / " +
                std::to_string(metadata.byte_count) + " bytes";
            return true;
        }

        bool apply(FrameGraphDebuggerSnapshot& next,
                   const DecodedMessage&,
                   const BlobChunk& chunk)
        {
            if (!assembler)
            {
                tc_log_error("remote framegraph source: blob chunk arrived "
                             "without capture metadata");
                return false;
            }
            const CaptureMetadata metadata = assembler->metadata();
            const BlobAssemblyResult result = assembler->append(chunk);
            if (!result)
            {
                tc_log_error("remote framegraph source: capture assembly "
                             "failed: %s", result.detail.c_str());
                append_gap(next,
                           FrameGraphDebuggerGapKind::TransportDrop,
                           1,
                           "capture assembly failed: " + result.detail);
                next.state = FrameGraphDebuggerState::Error;
                next.status_detail = result.detail;
                pending_commands.erase(metadata.request_id);
                assembler.reset();
                return true;
            }
            next.capture_info = "Receiving exact remote capture: " +
                std::to_string(chunk.offset + chunk.bytes.size()) + " / " +
                std::to_string(metadata.byte_count) + " bytes";
            if (!result.complete)
                return true;

            auto bytes = std::make_shared<const std::vector<std::uint8_t>>(
                assembler->take_bytes());
            assembler.reset();
            pending_commands.erase(metadata.request_id);
            next.cpu_capture = FrameGraphDebuggerCpuCaptureSnapshot{
                metadata.request_id,
                metadata.graph_revision,
                metadata.frame_number,
                project_pixel_format(metadata.pixel_format),
                metadata.width,
                metadata.height,
                metadata.is_depth,
                metadata.exact,
                std::move(bytes),
            };
            next.main_image = {
                true,
                metadata.width,
                metadata.height,
                upload_format(project_pixel_format(metadata.pixel_format)),
                metadata.is_depth,
                metadata.request_id,
            };
            next.depth_image = metadata.is_depth ? next.main_image
                                                 : FrameGraphDebuggerImageSnapshot{};
            next.state = FrameGraphDebuggerState::Captured;
            next.capture_info = "Exact remote capture: " +
                std::to_string(metadata.width) + "x" +
                std::to_string(metadata.height) + ", " +
                std::to_string(metadata.byte_count) + " bytes";
            next.status_detail = "exact remote capture received";
            return true;
        }

        bool apply(FrameGraphDebuggerSnapshot& next,
                   const DecodedMessage&,
                   const DropEvent& drop)
        {
            next.dropped_messages += drop.dropped_items;
            append_gap(next,
                       FrameGraphDebuggerGapKind::TransportDrop,
                       drop.dropped_items,
                       "remote " +
                           std::to_string(static_cast<unsigned>(drop.kind)) +
                           " queue drop");
            next.status_detail = "remote transport reported dropped messages";
            return true;
        }

        bool apply(FrameGraphDebuggerSnapshot& next,
                   const DecodedMessage&,
                   const ErrorEvent& error)
        {
            next.status_detail = "target error " + std::to_string(error.code) +
                                 ": " + error.detail;
            next.state = FrameGraphDebuggerState::Error;
            tc_log_error("remote framegraph source: target error %u: %s",
                         error.code,
                         error.detail.c_str());
            const auto pending =
                pending_commands.find(error.related_request_id);
            if (pending != pending_commands.end())
            {
                if (pending->second == CommandKind::select_target)
                    pending_target_id.reset();
                if (pending->second == CommandKind::refresh_topology)
                {
                    refresh_pending = false;
                }
                pending_commands.erase(pending);
            }
            if (assembler && assembler->metadata().request_id ==
                                 error.related_request_id)
                assembler.reset();
            return true;
        }

        void append_gap(FrameGraphDebuggerSnapshot& next,
                        FrameGraphDebuggerGapKind kind,
                        std::uint64_t count,
                        std::string detail)
        {
            if (next.gaps.size() == gap_capacity)
            {
                next.gaps.erase(next.gaps.begin());
            }
            next.gaps.push_back({kind, count, std::move(detail)});
        }

        void publish_error_locked(std::string detail)
        {
            auto next = std::make_shared<FrameGraphDebuggerSnapshot>(*state);
            next->status_detail = std::move(detail);
            next->state = FrameGraphDebuggerState::Error;
            publish_locked(std::move(next));
        }

        void publish_locked(std::shared_ptr<FrameGraphDebuggerSnapshot> next)
        {
            next->revision = state->revision + 1;
            state = std::move(next);
        }

        std::size_t gap_capacity = 0;
        CommandSender sender;
        mutable std::mutex mutex;
        std::shared_ptr<FrameGraphDebuggerSnapshot> state;
        std::unordered_map<std::uint64_t, CommandKind> pending_commands;
        std::optional<std::uint64_t> pending_target_id;
        std::uint64_t next_request_id = 1;
        std::uint64_t active_session_id = 0;
        std::uint64_t last_sequence = 0;
        bool refresh_pending = false;
        bool needs_refresh = true;
        bool exact_capture_supported = false;
        bool closed = false;
        Clock::time_point last_refresh_request{};
        std::optional<RemoteFrameGraphConnectionConfig> configured_client;
        std::uint64_t capture_memory_budget_bytes = WireLimits::max_blob_bytes;
        std::optional<BlobAssembler> assembler;
        tgfx::IRenderDevice* upload_device = nullptr;
        tgfx::TextureHandle upload_texture;
        std::uint64_t uploaded_request_id = 0;
        FrameGraphPresenter presenter;
        std::atomic<bool> gpu_release_requested{false};
        std::unique_ptr<framegraph_remote_client::RemoteFrameGraphClient>
            client;

    public:
        static tgfx::PixelFormat upload_format(
            FrameGraphDebuggerPixelFormat format)
        {
            switch (format)
            {
            case FrameGraphDebuggerPixelFormat::Rgba8Unorm:
                return tgfx::PixelFormat::RGBA8_UNorm;
            case FrameGraphDebuggerPixelFormat::Rgba16Float:
                return tgfx::PixelFormat::RGBA16F;
            case FrameGraphDebuggerPixelFormat::Rgba32Float:
                return tgfx::PixelFormat::RGBA32F;
            case FrameGraphDebuggerPixelFormat::Depth32Float:
                return tgfx::PixelFormat::D32F;
            case FrameGraphDebuggerPixelFormat::Depth16Unorm:
            case FrameGraphDebuggerPixelFormat::Unknown:
                return tgfx::PixelFormat::Undefined;
            }
            return tgfx::PixelFormat::Undefined;
        }

        void release_gpu()
        {
            if (upload_device && upload_texture)
            {
                try
                {
                    upload_device->destroy(upload_texture);
                }
                catch (const std::exception& error)
                {
                    tc_log_error("remote framegraph source: capture texture "
                                 "destroy failed: %s", error.what());
                }
                catch (...)
                {
                    tc_log_error("remote framegraph source: capture texture "
                                 "destroy failed");
                }
            }
            upload_device = nullptr;
            upload_texture = {};
            uploaded_request_id = 0;
            gpu_release_requested.store(false, std::memory_order_release);
        }

        void release_gpu_if_requested()
        {
            if (gpu_release_requested.load(std::memory_order_acquire))
                release_gpu();
        }

        bool ensure_uploaded(
            tgfx::IRenderDevice& device,
            const FrameGraphDebuggerCpuCaptureSnapshot& capture)
        {
            release_gpu_if_requested();
            if (!capture.bytes || capture.bytes->empty())
                return false;
            if (upload_device == &device && upload_texture &&
                uploaded_request_id == capture.request_id)
                return true;
            release_gpu();
            const tgfx::PixelFormat format = upload_format(capture.pixel_format);
            if (format == tgfx::PixelFormat::Undefined)
            {
                tc_log_error("remote framegraph source: unsupported local "
                             "upload pixel format");
                return false;
            }
            try
            {
                tgfx::TextureDesc desc;
                desc.width = capture.width;
                desc.height = capture.height;
                desc.format = format;
                desc.usage = tgfx::TextureUsage::Sampled |
                             tgfx::TextureUsage::CopySrc |
                             tgfx::TextureUsage::CopyDst;
                upload_texture = device.create_texture(desc);
                if (!upload_texture)
                {
                    tc_log_error("remote framegraph source: local capture "
                                 "texture creation failed");
                    return false;
                }
                device.upload_texture(upload_texture, *capture.bytes);
                upload_device = &device;
                uploaded_request_id = capture.request_id;
                return true;
            }
            catch (const std::exception& error)
            {
                tc_log_error("remote framegraph source: local capture upload "
                             "failed: %s", error.what());
            }
            catch (...)
            {
                tc_log_error("remote framegraph source: local capture upload "
                             "failed");
            }
            if (upload_texture)
                device.destroy(upload_texture);
            upload_texture = {};
            upload_device = nullptr;
            uploaded_request_id = 0;
            return false;
        }

        std::optional<FrameGraphDebuggerCpuCaptureSnapshot> cpu_capture() const
        {
            std::lock_guard lock(mutex);
            return state->cpu_capture;
        }

        bool render_image(tgfx::RenderContext2& context,
                          tgfx::TextureHandle target,
                          FrameGraphDebuggerImageKind kind,
                          std::uint32_t width,
                          std::uint32_t height,
                          int channel_mode,
                          bool highlight_hdr)
        {
            const auto capture = cpu_capture();
            if (!capture || !target || width == 0 || height == 0 ||
                (kind == FrameGraphDebuggerImageKind::Depth &&
                 !capture->is_depth) ||
                !ensure_uploaded(context.device(), *capture))
                return false;
            FrameGraphPresenterDraw draw;
            draw.capture_tex = upload_texture;
            draw.dst_rect = Rect2i{0,
                                   0,
                                   static_cast<int>(width),
                                   static_cast<int>(height)};
            draw.options.channel_mode = channel_mode;
            draw.options.highlight_hdr = highlight_hdr;
            presenter.render(&context, target, draw);
            return true;
        }

        std::vector<std::uint8_t> read_depth_normalized(
            tgfx::IRenderDevice& device, int* width, int* height)
        {
            const auto capture = cpu_capture();
            if (!capture || !capture->is_depth ||
                !ensure_uploaded(device, *capture))
            {
                if (width) *width = 0;
                if (height) *height = 0;
                return {};
            }
            return presenter.read_depth_normalized(
                &device, upload_texture, width, height);
        }

        std::string analyze_hdr() const
        {
            const auto capture = cpu_capture();
            if (!capture || !capture->bytes)
                return "No capture available";
            if (capture->is_depth)
                return "HDR stats unavailable for depth texture";
            const std::uint64_t pixels =
                static_cast<std::uint64_t>(capture->width) * capture->height;
            if (pixels == 0)
                return "No capture available";
            double sums[3]{};
            float minima[3]{std::numeric_limits<float>::max(),
                            std::numeric_limits<float>::max(),
                            std::numeric_limits<float>::max()};
            float maxima[3]{std::numeric_limits<float>::lowest(),
                            std::numeric_limits<float>::lowest(),
                            std::numeric_limits<float>::lowest()};
            std::uint64_t hdr_pixels = 0;
            for (std::uint64_t pixel = 0; pixel < pixels; ++pixel)
            {
                float channels[3]{};
                if (capture->pixel_format ==
                    FrameGraphDebuggerPixelFormat::Rgba8Unorm)
                {
                    const std::size_t offset = pixel * 4;
                    if (offset + 3 >= capture->bytes->size())
                        return "Remote capture byte size is invalid";
                    for (int channel = 0; channel < 3; ++channel)
                        channels[channel] =
                            (*capture->bytes)[offset + channel] / 255.0F;
                }
                else if (capture->pixel_format ==
                         FrameGraphDebuggerPixelFormat::Rgba32Float)
                {
                    const std::size_t offset = pixel * 4 * sizeof(float);
                    if (offset + 4 * sizeof(float) > capture->bytes->size())
                        return "Remote capture byte size is invalid";
                    std::memcpy(channels,
                                capture->bytes->data() + offset,
                                3 * sizeof(float));
                }
                else
                {
                    return "HDR analysis is unavailable for this pixel format";
                }
                bool hdr = false;
                for (int channel = 0; channel < 3; ++channel)
                {
                    minima[channel] = std::min(minima[channel],
                                               channels[channel]);
                    maxima[channel] = std::max(maxima[channel],
                                               channels[channel]);
                    sums[channel] += channels[channel];
                    hdr = hdr || channels[channel] > 1.0F;
                }
                if (hdr) ++hdr_pixels;
            }
            std::ostringstream out;
            out << std::fixed << std::setprecision(3)
                << "<b>R:</b> " << minima[0] << " - " << maxima[0]
                << " (avg: " << sums[0] / pixels << ")<br>"
                << "<b>G:</b> " << minima[1] << " - " << maxima[1]
                << " (avg: " << sums[1] / pixels << ")<br>"
                << "<b>B:</b> " << minima[2] << " - " << maxima[2]
                << " (avg: " << sums[2] / pixels << ")<br>"
                << "<b>HDR pixels:</b> " << hdr_pixels << " ("
                << std::setprecision(2)
                << (100.0 * static_cast<double>(hdr_pixels) / pixels)
                << "%)";
            return out.str();
        }
    };

    RemoteFrameGraphDebuggerSource::RemoteFrameGraphDebuggerSource(
        std::size_t gap_capacity, CommandSender sender)
        : impl_(std::make_unique<Impl>(gap_capacity, std::move(sender)))
    {
    }

    RemoteFrameGraphDebuggerSource::~RemoteFrameGraphDebuggerSource() = default;

    std::shared_ptr<const FrameGraphDebuggerSnapshot>
    RemoteFrameGraphDebuggerSource::snapshot() const
    {
        return impl_->snapshot();
    }

    bool RemoteFrameGraphDebuggerSource::refresh()
    {
        return impl_->refresh();
    }

    void RemoteFrameGraphDebuggerSource::finish_frame()
    {
        impl_->release_gpu_if_requested();
    }

    void RemoteFrameGraphDebuggerSource::connect()
    {
        impl_->connect_configured();
    }

    void RemoteFrameGraphDebuggerSource::disconnect()
    {
        impl_->disconnect_live();
        impl_->disconnected("remote source disconnected");
        impl_->release_gpu();
    }

    void RemoteFrameGraphDebuggerSource::close()
    {
        impl_->close();
        impl_->release_gpu();
    }

    bool RemoteFrameGraphDebuggerSource::select_target(std::uint64_t target_id)
    {
        return impl_->select_target(target_id);
    }

    bool RemoteFrameGraphDebuggerSource::select_pass(
        std::optional<std::uint64_t> pass_id)
    {
        return impl_->select_pass(pass_id);
    }

    void RemoteFrameGraphDebuggerSource::set_mode(FrameGraphDebuggerMode mode)
    {
        impl_->mutate([mode](auto& next) { next.mode = mode; });
        impl_->request_exact_capture();
    }

    void RemoteFrameGraphDebuggerSource::set_selected_symbol(
        const std::string& symbol)
    {
        impl_->mutate([&symbol](auto& next) { next.selected_symbol = symbol; });
        impl_->request_exact_capture();
    }

    void RemoteFrameGraphDebuggerSource::set_selected_resource(
        const std::string& resource)
    {
        impl_->mutate([&resource](auto& next)
                      { next.selected_resource = resource; });
        impl_->request_exact_capture();
    }

    void RemoteFrameGraphDebuggerSource::set_channel_mode(int mode)
    {
        impl_->mutate([mode](auto& next) { next.channel_mode = mode; });
    }

    void RemoteFrameGraphDebuggerSource::set_paused(bool paused)
    {
        impl_->mutate([paused](auto& next) { next.paused = paused; });
        if (paused)
            impl_->cancel_capture();
        else
            impl_->request_exact_capture();
    }

    void RemoteFrameGraphDebuggerSource::set_highlight_hdr(bool enabled)
    {
        impl_->mutate([enabled](auto& next) { next.highlight_hdr = enabled; });
    }

    std::string RemoteFrameGraphDebuggerSource::analyze_hdr()
    {
        return impl_->analyze_hdr();
    }

    bool RemoteFrameGraphDebuggerSource::render_image(
        tgfx::RenderContext2& context,
        tgfx::TextureHandle target,
        FrameGraphDebuggerImageKind kind,
        std::uint32_t width,
        std::uint32_t height,
        int channel_mode,
        bool highlight_hdr)
    {
        return impl_->render_image(context,
                                   target,
                                   kind,
                                   width,
                                   height,
                                   channel_mode,
                                   highlight_hdr);
    }

    std::vector<std::uint8_t>
    RemoteFrameGraphDebuggerSource::read_depth_normalized(tgfx::IRenderDevice& device,
                                                          int* width,
                                                          int* height)
    {
        return impl_->read_depth_normalized(device, width, height);
    }

    bool RemoteFrameGraphDebuggerSource::ingest(const DecodedMessage& message)
    {
        return impl_->ingest(message);
    }

    bool RemoteFrameGraphDebuggerSource::connect(
        RemoteFrameGraphConnectionConfig config)
    {
        return impl_->connect_live(std::move(config));
    }

    bool RemoteFrameGraphDebuggerSource::request_exact_capture()
    {
        return impl_->request_exact_capture();
    }

    void
    RemoteFrameGraphDebuggerSource::transport_disconnected(std::string detail)
    {
        impl_->disconnected(std::move(detail));
    }

} // namespace termin
