#pragma once

#include <cstddef>
#include <cstdint>
#include <memory>
#include <string>
#include <vector>

#if defined(_WIN32) && defined(TERMIN_FRAME_PROFILER_EXPORTS)
#define TERMIN_FRAME_PROFILER_API __declspec(dllexport)
#elif defined(_WIN32)
#define TERMIN_FRAME_PROFILER_API __declspec(dllimport)
#else
#define TERMIN_FRAME_PROFILER_API
#endif

#if defined(_WIN32) && defined(TERMIN_FRAME_PROFILER_LOCAL_EXPORTS)
#define TERMIN_FRAME_PROFILER_LOCAL_API __declspec(dllexport)
#elif defined(_WIN32)
#define TERMIN_FRAME_PROFILER_LOCAL_API __declspec(dllimport)
#else
#define TERMIN_FRAME_PROFILER_LOCAL_API
#endif

namespace termin {

    class EngineCore;

    enum class FrameProfilerCapability : std::uint32_t {
        Capture = 1U << 0,
        SectionProfiling = 1U << 1,
        Clear = 1U << 2,
        IncludeUi = 1U << 3,
    };

    using FrameProfilerCapabilities = std::uint32_t;

    constexpr FrameProfilerCapabilities operator|(FrameProfilerCapability left, FrameProfilerCapability right) {
        return static_cast<FrameProfilerCapabilities>(left) | static_cast<FrameProfilerCapabilities>(right);
    }

    constexpr FrameProfilerCapabilities operator|(FrameProfilerCapabilities left, FrameProfilerCapability right) {
        return left | static_cast<FrameProfilerCapabilities>(right);
    }

    constexpr bool has_capability(FrameProfilerCapabilities capabilities, FrameProfilerCapability capability) {
        return (capabilities & static_cast<FrameProfilerCapabilities>(capability)) != 0;
    }

    enum class FrameProfilerGapKind {
        CaptureOverwrite,
        Source,
        TransportDrop,
        Disconnect,
    };

    struct TERMIN_FRAME_PROFILER_API FrameProfilerSourceIdentity {
        std::string source_id;
        std::string session_id;
        std::string display_name;
    };

    struct TERMIN_FRAME_PROFILER_API FrameProfilerSourceStatus {
        bool connected = true;
        bool capturing = false;
        bool profiling_sections = false;
        bool external_profiling = false;
        bool include_ui = false;
        std::uint64_t overwritten_frames = 0;
        std::uint64_t dropped_frames = 0;
        std::string detail;
    };

    struct TERMIN_FRAME_PROFILER_API FrameProfilerSection {
        std::string name;
        double cpu_ms = 0.0;
        double children_ms = 0.0;
        std::uint32_t call_count = 0;
        std::int32_t parent_index = -1;
        std::int32_t first_child = -1;
        std::int32_t next_sibling = -1;
    };

    struct TERMIN_FRAME_PROFILER_API FrameProfilerFrame {
        std::int64_t frame_number = 0;
        double start_time_ms = 0.0;
        double interval_ms = 0.0;
        double active_ms = 0.0;
        double target_interval_ms = 0.0;
        double deadline_lateness_ms = 0.0;
        std::uint32_t missed_intervals = 0;
        bool sections_profiled = false;
        bool gap_before = false;
        std::vector<FrameProfilerSection> sections;
    };

    struct TERMIN_FRAME_PROFILER_API FrameProfilerGap {
        FrameProfilerGapKind kind = FrameProfilerGapKind::Source;
        std::int64_t first_missing_frame = 0;
        std::int64_t last_missing_frame = 0;
        std::uint64_t missing_count = 0;
        std::string detail;
    };

    // One immutable, self-contained source state. A disconnected remote source can
    // publish a new status/gap while retaining the last bounded frame vector.
    struct TERMIN_FRAME_PROFILER_API FrameProfilerSnapshot {
        std::uint64_t revision = 0;
        std::size_t capacity = 0;
        FrameProfilerSourceIdentity identity;
        FrameProfilerCapabilities capabilities = 0;
        FrameProfilerSourceStatus status;
        std::vector<FrameProfilerFrame> frames;
        std::vector<FrameProfilerGap> gaps;

        const FrameProfilerFrame* find(std::int64_t frame_number) const;
    };

    class TERMIN_FRAME_PROFILER_API IFrameProfilerSource {
    public:
        virtual ~IFrameProfilerSource() = default;

        virtual std::uint64_t revision() const = 0;
        virtual std::shared_ptr<const FrameProfilerSnapshot> snapshot() = 0;
        virtual bool start_capture() = 0;
        virtual bool pause_capture() = 0;
        virtual bool set_section_profiling(bool enabled) = 0;
        virtual bool clear_capture() = 0;
        virtual bool set_include_ui(bool enabled) = 0;
        virtual void close() = 0;
    };

    TERMIN_FRAME_PROFILER_LOCAL_API std::unique_ptr<IFrameProfilerSource>
    make_local_frame_profiler_source(EngineCore& engine, int capacity);

} // namespace termin
