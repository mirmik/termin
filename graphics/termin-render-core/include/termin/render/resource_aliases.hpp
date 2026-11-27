#pragma once

#include <string>

namespace termin {

    enum class AttachmentKind {
        Color,
        Depth,
    };

    struct ResourceView {
        std::string parent;
        AttachmentKind attachment = AttachmentKind::Color;
    };

    struct FboComposition {
        std::string color;
        std::string depth;
    };

    // Terminal resource names. A viewport slot is resolved against the active
    // target on each execution, so the plan never retains device handles.
    enum class AttachmentStorage { Resource, ViewportOutput, ViewportSlot };

    struct AttachmentSource {
        std::string name;
        AttachmentStorage storage = AttachmentStorage::Resource;
        bool operator==(const AttachmentSource&) const = default;
    };

    struct AttachmentSources {
        AttachmentSource color;
        AttachmentSource depth;
        bool depth_view = false;
    };

} // namespace termin
