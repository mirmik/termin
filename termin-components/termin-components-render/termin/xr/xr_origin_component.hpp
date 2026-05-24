#pragma once

#include <cstdint>
#include <string>

#include <termin/entity/component.hpp>
#include <termin/export.hpp>

namespace termin {

enum class XrReferenceSpace {
    Local,
    Stage,
};

enum class XrReferenceAlignment {
    InitialHeadYaw,
    StageAxes,
};

class ENTITY_API XrOriginComponent : public CxxComponent {
public:
    XrReferenceSpace reference_space = XrReferenceSpace::Local;
    XrReferenceAlignment reference_alignment = XrReferenceAlignment::InitialHeadYaw;
    double near_clip = 0.1;
    double far_clip = 100.0;
    uint64_t layer_mask = 0xFFFFFFFFFFFFFFFFULL;

public:
    XrOriginComponent();

    static void register_type();

    std::string get_reference_space_str() const;
    void set_reference_space_str(const std::string& value);
    std::string get_reference_alignment_str() const;
    void set_reference_alignment_str(const std::string& value);
};

} // namespace termin
