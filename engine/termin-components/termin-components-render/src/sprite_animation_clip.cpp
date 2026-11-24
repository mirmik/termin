#include <termin/render/sprite_animation_clip.hpp>

#include <cmath>
#include <mutex>
#include <stdexcept>
#include <unordered_map>

#include <tcbase/tc_log.h>
#include <tcbase/trent/json.h>

namespace termin {
    namespace {
        std::unordered_map<std::string, std::shared_ptr<SpriteAnimationClip>> clips;
        std::mutex clips_mutex;

        void validate_frames(const std::vector<SpriteAnimationFrame>& frames, std::vector<double>* ends = nullptr) {
            if (frames.empty())
                throw std::invalid_argument("sprite animation requires at least one frame");
            double total = 0;
            for (size_t i = 0; i < frames.size(); ++i) {
                const auto& frame = frames[i];
                if (frame.sprite_uuid.empty()) {
                    throw std::invalid_argument("missing sprite UUID in sprite animation frame " + std::to_string(i));
                }
                const double end = total + frame.duration;
                if (!std::isfinite(end) || end <= total) {
                    throw std::invalid_argument("invalid duration in sprite animation frame " + std::to_string(i));
                }
                if (ends)
                    ends->push_back(end);
                total = end;
            }
        }
    } // namespace

    std::vector<SpriteAnimationFrame> parse_sprite_animation_clip(const nos::trent& descriptor) {
        if (!descriptor["format"].is_string() || descriptor["format"].as_string() != "termin.sprite-animation" ||
            !descriptor["version"].is_numer() || descriptor["version"].as_numer() != 1) {
            throw std::invalid_argument("unsupported sprite animation clip format or version");
        }
        if (!descriptor["frames"].is_list())
            throw std::invalid_argument("sprite animation frames must be an array");
        const auto& entries = descriptor["frames"].as_list();
        std::vector<SpriteAnimationFrame> frames;
        frames.reserve(entries.size());
        for (const auto& entry : entries) {
            if (!entry["sprite"].is_string() || !entry["duration"].is_numer() ||
                (entry.contains("event") && !entry["event"].is_string())) {
                throw std::invalid_argument("invalid sprite, duration or event in sprite animation frame " +
                                            std::to_string(frames.size()));
            }
            frames.push_back({entry["sprite"].as_string(),
                              static_cast<double>(entry["duration"].as_numer()),
                              entry.contains("event") ? entry["event"].as_string() : ""});
        }
        validate_frames(frames);
        return frames;
    }

    TcSpriteAnimationClip
    TcSpriteAnimationClip::declare(const std::string& uuid, const std::string& name, const std::string& source_path) {
        if (uuid.empty()) {
            tc_log_error("[SpriteAnimationClip] cannot declare clip with empty UUID");
            return {};
        }
        std::lock_guard lock(clips_mutex);
        auto& asset = clips[uuid];
        if (!asset) {
            asset = std::make_shared<SpriteAnimationClip>();
            asset->uuid = uuid;
            asset->name = uuid;
        }
        if (!name.empty())
            asset->name = name;
        if (!source_path.empty())
            asset->source_path = source_path;
        return TcSpriteAnimationClip(asset);
    }

    TcSpriteAnimationClip TcSpriteAnimationClip::from_uuid(const std::string& uuid) {
        std::lock_guard lock(clips_mutex);
        const auto it = clips.find(uuid);
        return it == clips.end() ? TcSpriteAnimationClip{} : TcSpriteAnimationClip(it->second);
    }

    void TcSpriteAnimationClip::replace_frames(std::vector<SpriteAnimationFrame> frames) {
        if (!asset_)
            throw std::invalid_argument("cannot update an invalid sprite animation clip handle");
        std::vector<double> ends;
        ends.reserve(frames.size());
        validate_frames(frames, &ends);
        asset_->frames = std::move(frames);
        asset_->frame_ends = std::move(ends);
        asset_->loaded = true;
        ++asset_->version;
    }

    bool TcSpriteAnimationClip::update(std::vector<SpriteAnimationFrame> frames) {
        try {
            replace_frames(std::move(frames));
        } catch (const std::invalid_argument& e) {
            tc_log_error("[SpriteAnimationClip] '%s': %s", asset_ ? asset_->uuid.c_str() : "", e.what());
            return false;
        }
        return true;
    }

    void TcSpriteAnimationClip::load_json(const std::string& text) {
        replace_frames(parse_sprite_animation_clip(nos::json::parse(text)));
    }

    void TcSpriteAnimationClip::unload() {
        if (!asset_ || !asset_->loaded)
            return;
        asset_->loaded = false;
        asset_->frames.clear();
        asset_->frame_ends.clear();
        ++asset_->version;
    }
} // namespace termin
