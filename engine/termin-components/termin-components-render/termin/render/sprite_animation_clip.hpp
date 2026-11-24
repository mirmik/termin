#pragma once

#include <cstdint>
#include <memory>
#include <string>
#include <utility>
#include <vector>

#include <termin/export.hpp>

namespace nos {
    class trent;
}

namespace termin {
    struct SpriteAnimationFrame {
        std::string sprite_uuid;
        double duration = 0.0;
        std::string event;
    };

    struct SpriteAnimationClip {
        std::string uuid;
        std::string name;
        std::string source_path;
        std::vector<SpriteAnimationFrame> frames;
        std::vector<double> frame_ends;
        uint32_t version = 0;
        bool loaded = false;
    };

    // Parse the descriptor without declaring or replacing a live asset.
    ENTITY_API std::vector<SpriteAnimationFrame> parse_sprite_animation_clip(const nos::trent& descriptor);

    class ENTITY_API TcSpriteAnimationClip {
    public:
        TcSpriteAnimationClip() = default;
        static TcSpriteAnimationClip
        declare(const std::string& uuid, const std::string& name, const std::string& source_path = {});
        static TcSpriteAnimationClip from_uuid(const std::string& uuid);
        bool is_valid() const {
            return asset_ != nullptr;
        }
        bool is_loaded() const {
            return asset_ && asset_->loaded;
        }
        const SpriteAnimationClip* get() const {
            return asset_.get();
        }
        uint32_t version() const {
            return asset_ ? asset_->version : 0;
        }

        bool update(std::vector<SpriteAnimationFrame> frames);
        void load_json(const std::string& text);
        void unload();

    private:
        explicit TcSpriteAnimationClip(std::shared_ptr<SpriteAnimationClip> asset)
            : asset_(std::move(asset)) {}
        void replace_frames(std::vector<SpriteAnimationFrame> frames);
        std::shared_ptr<SpriteAnimationClip> asset_;
    };
} // namespace termin
