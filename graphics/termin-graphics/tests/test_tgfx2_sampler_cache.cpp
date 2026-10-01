#include "guard_main.h"

#include "tgfx2/i_render_device.hpp"
#include "tgfx2/tc_sampler_bridge.hpp"

#include <cstring>
#include <limits>
#include <memory>
#include <string>
#include <type_traits>
#include <vector>

namespace {

    struct SamplerDeviceRecords {
        int attempts = 0;
        int explicit_destroys = 0;
        int pool_teardown_destroys = 0;
        std::vector<tgfx::SamplerDesc> created;
    };

    class SamplerRecordingDevice final : public tgfx::IRenderDevice {
    public:
        std::shared_ptr<SamplerDeviceRecords> records = std::make_shared<SamplerDeviceRecords>();
        bool fail_creation = false;
        bool throw_creation = false;

        ~SamplerRecordingDevice() override {
            // Native pools, rather than the base-class cache, own teardown.
            records->pool_teardown_destroys += static_cast<int>(records->created.size());
        }

        tgfx::BackendType backend_type() const override { return tgfx::BackendType::Null; }
        tgfx::BackendCapabilities capabilities() const override { return {}; }
        void wait_idle() override {}
        tgfx::BufferHandle create_buffer(const tgfx::BufferDesc&) override { return {}; }
        tgfx::TextureHandle create_texture(const tgfx::TextureDesc&) override { return {}; }
        tgfx::SamplerHandle create_sampler(const tgfx::SamplerDesc& desc) override {
            ++records->attempts;
            if (throw_creation)
                throw std::runtime_error("injected sampler creation error");
            if (fail_creation)
                return {};
            records->created.push_back(desc);
            return {static_cast<uint32_t>(records->created.size())};
        }
        tgfx::ShaderHandle create_shader(const tgfx::ShaderDesc&) override { return {}; }
        tgfx::PipelineHandle create_pipeline(const tgfx::PipelineDesc&) override { return {}; }
        tgfx::ResourceSetHandle create_bound_resource_set(const tgfx::BoundResourceSetDesc&) override { return {}; }
        void destroy(tgfx::BufferHandle) override {}
        void destroy(tgfx::TextureHandle) override {}
        void destroy(tgfx::SamplerHandle) override { ++records->explicit_destroys; }
        void destroy(tgfx::ShaderHandle) override {}
        void destroy(tgfx::PipelineHandle) override {}
        void destroy(tgfx::ResourceSetHandle) override {}
        void upload_buffer(tgfx::BufferHandle, std::span<const uint8_t>, uint64_t = 0) override {}
        void upload_texture(tgfx::TextureHandle, std::span<const uint8_t>, uint32_t = 0) override {}
        void upload_texture_region(tgfx::TextureHandle, uint32_t, uint32_t, uint32_t, uint32_t,
                                   std::span<const uint8_t>, uint32_t = 0) override {}
        void read_buffer(tgfx::BufferHandle, std::span<uint8_t>, uint64_t = 0) override {}
        tgfx::TextureDesc texture_desc(tgfx::TextureHandle) const override { return {}; }
        std::unique_ptr<tgfx::ICommandList> create_command_list(tgfx::QueueType = tgfx::QueueType::Graphics) override {
            return {};
        }
        void submit(tgfx::ICommandList&) override {}
        void present() override {}
    };

    struct SamplerLogCapture {
        SamplerLogCapture() { tc_log_capture_start(64); }
        ~SamplerLogCapture() { tc_log_capture_stop(); }
        bool contains_error(const char* expected) const {
            tc_log_record records[64]{};
            const auto count = tc_log_capture_drain(records, 64, nullptr);
            for (size_t i = 0; i < count; ++i) {
                if (records[i].level == TC_LOG_ERROR && std::string(records[i].message).find(expected) != std::string::npos)
                    return true;
            }
            return false;
        }
    };

    void check_sampler_equal(const tgfx::SamplerDesc& actual, const tgfx::SamplerDesc& expected) {
        CHECK(actual.min_filter == expected.min_filter);
        CHECK(actual.mag_filter == expected.mag_filter);
        CHECK(actual.mip_filter == expected.mip_filter);
        CHECK(actual.address_u == expected.address_u);
        CHECK(actual.address_v == expected.address_v);
        CHECK(actual.address_w == expected.address_w);
        CHECK(actual.max_anisotropy == expected.max_anisotropy);
        CHECK(actual.compare_enable == expected.compare_enable);
        CHECK(actual.compare_op == expected.compare_op);
    }

} // namespace

TEST_CASE("CPU sampler conversion preserves complete state and rejects invalid state atomically") {
    auto source = tc_sampler_desc_default();
    tgfx::SamplerDesc converted;
    REQUIRE(tgfx::tc_sampler_to_tgfx2(source, converted));
    check_sampler_equal(converted, tgfx::SamplerDesc{});

    source.min_filter = TC_SAMPLER_FILTER_NEAREST;
    source.mag_filter = TC_SAMPLER_FILTER_NEAREST;
    source.mip_filter = TC_SAMPLER_FILTER_NEAREST;
    source.address_u = TC_SAMPLER_ADDRESS_MIRRORED_REPEAT;
    source.address_v = TC_SAMPLER_ADDRESS_CLAMP_TO_EDGE;
    source.address_w = TC_SAMPLER_ADDRESS_CLAMP_TO_BORDER;
    source.max_anisotropy = 2.5f;
    source.compare_enable = 1;
    source.compare_op = TC_SAMPLER_COMPARE_LESS_EQUAL;
    REQUIRE(tgfx::tc_sampler_to_tgfx2(source, converted));
    CHECK(converted.min_filter == tgfx::FilterMode::Nearest);
    CHECK(converted.mag_filter == tgfx::FilterMode::Nearest);
    CHECK(converted.mip_filter == tgfx::FilterMode::Nearest);
    CHECK(converted.address_u == tgfx::AddressMode::MirroredRepeat);
    CHECK(converted.address_v == tgfx::AddressMode::ClampToEdge);
    CHECK(converted.address_w == tgfx::AddressMode::ClampToBorder);
    CHECK(converted.max_anisotropy == 2.5f);
    CHECK(converted.compare_enable);
    CHECK(converted.compare_op == tgfx::CompareOp::LessEqual);
    const auto previous = converted;
    source.address_w = 255;
    SamplerLogCapture logs;
    CHECK_FALSE(tgfx::tc_sampler_to_tgfx2(source, converted));
    check_sampler_equal(converted, previous);
    CHECK(logs.contains_error("tc_sampler_to_tgfx2"));
}

TEST_CASE("device sampler cache keys every descriptor field and reuses borrowed variants") {
    SamplerRecordingDevice device;
    const tgfx::SamplerDesc baseline;
    const auto first = device.ensure_sampler(baseline);
    REQUIRE(first);
    CHECK(device.ensure_sampler(baseline) == first);
    CHECK_EQ(device.records->attempts, 1);
    std::vector<tgfx::SamplerDesc> variants(9, baseline);
    variants[0].min_filter = tgfx::FilterMode::Nearest;
    variants[1].mag_filter = tgfx::FilterMode::Nearest;
    variants[2].mip_filter = tgfx::FilterMode::Nearest;
    variants[3].address_u = tgfx::AddressMode::ClampToEdge;
    variants[4].address_v = tgfx::AddressMode::ClampToEdge;
    variants[5].address_w = tgfx::AddressMode::ClampToEdge;
    variants[6].max_anisotropy = 2.0f;
    variants[7].compare_enable = true;
    variants[8].compare_op = tgfx::CompareOp::LessEqual;
    std::vector<tgfx::SamplerHandle> handles{first};
    for (const auto& variant : variants) {
        const auto handle = device.ensure_sampler(variant);
        REQUIRE(handle);
        for (const auto previous : handles)
            CHECK(handle != previous);
        handles.push_back(handle);
        CHECK(device.ensure_sampler(variant) == handle);
        CHECK(device.ensure_sampler(baseline) == first);
        check_sampler_equal(device.records->created.back(), variant);
    }
    CHECK_EQ(device.records->attempts, 10);
    CHECK_EQ(device.records->explicit_destroys, 0);
}

TEST_CASE("sampler cache ignores descriptor padding and stays local to each native device") {
    static_assert(std::is_standard_layout_v<tgfx::SamplerDesc>);
    static_assert(std::is_trivially_copyable_v<tgfx::SamplerDesc>);
    tgfx::SamplerDesc first;
    tgfx::SamplerDesc second;
    std::memset(&first, 0x11, sizeof(first));
    std::memset(&second, 0x22, sizeof(second));
    for (auto* desc : {&first, &second}) {
        desc->min_filter = tgfx::FilterMode::Linear;
        desc->mag_filter = tgfx::FilterMode::Linear;
        desc->mip_filter = tgfx::FilterMode::Linear;
        desc->address_u = tgfx::AddressMode::Repeat;
        desc->address_v = tgfx::AddressMode::Repeat;
        desc->address_w = tgfx::AddressMode::Repeat;
        desc->max_anisotropy = 1.0f;
        desc->compare_enable = false;
        desc->compare_op = tgfx::CompareOp::Never;
    }
    SamplerRecordingDevice a;
    SamplerRecordingDevice b;
    const auto handle = a.ensure_sampler(first);
    REQUIRE(handle);
    CHECK(a.ensure_sampler(second) == handle);
    REQUIRE(b.ensure_sampler(first));
    CHECK_EQ(a.records->attempts, 1);
    CHECK_EQ(b.records->attempts, 1);
}

TEST_CASE("sampler cache rejects invalid fields before ordering or native creation") {
    SamplerRecordingDevice device;
    const tgfx::SamplerDesc baseline;
    std::vector<tgfx::SamplerDesc> invalid(7, baseline);
    invalid[0].min_filter = static_cast<tgfx::FilterMode>(-1);
    invalid[1].mag_filter = static_cast<tgfx::FilterMode>(255);
    invalid[2].mip_filter = static_cast<tgfx::FilterMode>(255);
    invalid[3].address_u = static_cast<tgfx::AddressMode>(-1);
    invalid[4].address_v = static_cast<tgfx::AddressMode>(255);
    invalid[5].address_w = static_cast<tgfx::AddressMode>(255);
    invalid[6].compare_op = static_cast<tgfx::CompareOp>(255);
    SamplerLogCapture logs;
    for (const auto& desc : invalid)
        CHECK_FALSE(device.ensure_sampler(desc));
    for (const auto value : {0.0f, -1.0f, std::numeric_limits<float>::infinity(),
                            -std::numeric_limits<float>::infinity(), std::numeric_limits<float>::quiet_NaN()}) {
        auto desc = baseline;
        desc.max_anisotropy = value;
        CHECK_FALSE(device.ensure_sampler(desc));
    }
    CHECK_EQ(device.records->attempts, 0);
    CHECK(logs.contains_error("invalid sampler descriptor"));
    REQUIRE(device.ensure_sampler(baseline));
    CHECK_EQ(device.records->attempts, 1);
}

TEST_CASE("sampler creation failures log and can recover without caching an invalid handle") {
    SamplerRecordingDevice device;
    const tgfx::SamplerDesc desc;
    SamplerLogCapture logs;
    device.fail_creation = true;
    CHECK_FALSE(device.ensure_sampler(desc));
    CHECK_FALSE(device.ensure_sampler(desc));
    CHECK_EQ(device.records->attempts, 2);
    CHECK(logs.contains_error("empty sampler handle"));
    device.fail_creation = false;
    device.throw_creation = true;
    bool threw = false;
    try {
        device.ensure_sampler(desc);
    } catch (const std::runtime_error& error) {
        threw = true;
        CHECK(std::string(error.what()) == "injected sampler creation error");
    }
    CHECK(threw);
    CHECK(logs.contains_error("backend sampler creation failed"));
    device.throw_creation = false;
    const auto handle = device.ensure_sampler(desc);
    REQUIRE(handle);
    CHECK(device.ensure_sampler(desc) == handle);
    CHECK_EQ(device.records->attempts, 4);
}

TEST_CASE("native sampler pool owns borrowed cache handles through device teardown") {
    auto records = std::make_shared<SamplerDeviceRecords>();
    {
        SamplerRecordingDevice device;
        device.records = records;
        tgfx::SamplerDesc desc;
        const auto repeat = device.ensure_sampler(desc);
        REQUIRE(repeat);
        desc.address_u = tgfx::AddressMode::ClampToEdge;
        const auto clamp = device.ensure_sampler(desc);
        REQUIRE(clamp);
        CHECK(clamp != repeat);
        desc.address_u = tgfx::AddressMode::Repeat;
        CHECK(device.ensure_sampler(desc) == repeat);
        CHECK_EQ(records->pool_teardown_destroys, 0);
        CHECK_EQ(records->explicit_destroys, 0);
    }
    CHECK_EQ(records->pool_teardown_destroys, 2);
    CHECK_EQ(records->explicit_destroys, 0);
}
