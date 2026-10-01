#include "tgfx2/tc_sampler_bridge.hpp"
#include <tcbase/tc_log.h>

namespace tgfx {

    // Explicitly pin enum correspondence before using validated integer casts.
    static_assert(static_cast<int>(FilterMode::Nearest) == TC_SAMPLER_FILTER_NEAREST);
    static_assert(static_cast<int>(FilterMode::Linear) == TC_SAMPLER_FILTER_LINEAR);
    static_assert(static_cast<int>(AddressMode::Repeat) == TC_SAMPLER_ADDRESS_REPEAT);
    static_assert(static_cast<int>(AddressMode::MirroredRepeat) == TC_SAMPLER_ADDRESS_MIRRORED_REPEAT);
    static_assert(static_cast<int>(AddressMode::ClampToEdge) == TC_SAMPLER_ADDRESS_CLAMP_TO_EDGE);
    static_assert(static_cast<int>(AddressMode::ClampToBorder) == TC_SAMPLER_ADDRESS_CLAMP_TO_BORDER);
    static_assert(static_cast<int>(CompareOp::Never) == TC_SAMPLER_COMPARE_NEVER);
    static_assert(static_cast<int>(CompareOp::Less) == TC_SAMPLER_COMPARE_LESS);
    static_assert(static_cast<int>(CompareOp::Equal) == TC_SAMPLER_COMPARE_EQUAL);
    static_assert(static_cast<int>(CompareOp::LessEqual) == TC_SAMPLER_COMPARE_LESS_EQUAL);
    static_assert(static_cast<int>(CompareOp::Greater) == TC_SAMPLER_COMPARE_GREATER);
    static_assert(static_cast<int>(CompareOp::NotEqual) == TC_SAMPLER_COMPARE_NOT_EQUAL);
    static_assert(static_cast<int>(CompareOp::GreaterEqual) == TC_SAMPLER_COMPARE_GREATER_EQUAL);
    static_assert(static_cast<int>(CompareOp::Always) == TC_SAMPLER_COMPARE_ALWAYS);

    bool tc_sampler_to_tgfx2(const tc_sampler_desc& source, SamplerDesc& out) {
        if (!tc_sampler_desc_validate(&source)) {
            tc_log_error("tc_sampler_to_tgfx2: invalid CPU sampler state");
            return false;
        }
        SamplerDesc converted;
        converted.min_filter = static_cast<FilterMode>(source.min_filter);
        converted.mag_filter = static_cast<FilterMode>(source.mag_filter);
        converted.mip_filter = static_cast<FilterMode>(source.mip_filter);
        converted.address_u = static_cast<AddressMode>(source.address_u);
        converted.address_v = static_cast<AddressMode>(source.address_v);
        converted.address_w = static_cast<AddressMode>(source.address_w);
        converted.max_anisotropy = source.max_anisotropy;
        converted.compare_enable = source.compare_enable != 0;
        converted.compare_op = static_cast<CompareOp>(source.compare_op);
        out = converted;
        return true;
    }

} // namespace tgfx
