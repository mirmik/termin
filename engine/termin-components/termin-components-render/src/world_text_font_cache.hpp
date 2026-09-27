#pragma once

#include <memory>
#include <string>
#include <unordered_map>
#include <tgfx2/font_atlas.hpp>

namespace termin::detail {
    // Used by world-text encoders on the render thread. Weak ownership releases
    // both CPU and GPU atlases when the last component stops using the font.
    // Keep this pool separate from configurable UI fonts: world text fixes its
    // preload size and atlas settings, while UI clients may mutate theirs.
    class WorldTextFontCache {
        std::unordered_map<std::string, std::weak_ptr<tgfx::FontAtlas>> fonts_;

    public:
        std::shared_ptr<tgfx::FontAtlas> acquire(const std::string& path) {
            if (auto it = fonts_.find(path); it != fonts_.end()) {
                if (auto font = it->second.lock())
                    return font;
            }
            std::erase_if(fonts_, [](const auto& item) { return item.second.expired(); });
            auto font = std::make_shared<tgfx::FontAtlas>(path, 16);
            fonts_.insert_or_assign(path, font);
            return font;
        }
    };
} // namespace termin::detail
