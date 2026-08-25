#pragma once

#include "termin_visual_scene/items/item3d_packets.hpp"
#include "termin_visual_scene/native_visual_item3d.hpp"

namespace termin::visual {

    class TERMIN_VISUAL_SCENE_API StaticMeshItem3D final : public NativeVisualItem3D {
    public:
        explicit StaticMeshItem3D(std::shared_ptr<const termin::Mesh3> mesh,
                                  termin::LinearColor tint = {1.0f, 1.0f, 1.0f, 1.0f},
                                  bool depth_test = true);

        const std::shared_ptr<const termin::Mesh3>& mesh() const noexcept {
            return mesh_;
        }
        void set_mesh(std::shared_ptr<const termin::Mesh3> mesh);
        termin::LinearColor tint() const noexcept {
            return tint_;
        }
        void set_tint(termin::LinearColor tint);
        const std::shared_ptr<const BaseColorTextureData3D>& base_color_texture() const noexcept {
            return base_color_texture_;
        }
        void set_base_color_texture(std::shared_ptr<const BaseColorTextureData3D> texture);
        void clear_base_color_texture() noexcept {
            base_color_texture_.reset();
        }
        const FlatLighting3D& flat_lighting() const noexcept {
            return flat_lighting_;
        }
        void set_flat_lighting(termin::Vec3f direction, float ambient = 0.28f, float diffuse = 0.72f);
        void clear_flat_lighting() noexcept {
            flat_lighting_ = {};
        }
        bool hit_test_enabled() const noexcept {
            return hit_test_enabled_;
        }
        void set_hit_test_enabled(bool value) noexcept {
            hit_test_enabled_ = value;
        }
        bool depth_test() const noexcept {
            return depth_test_;
        }
        void set_depth_test(bool value) noexcept {
            depth_test_ = value;
        }

        std::optional<VisualBounds3D> local_bounds() const override;
        std::optional<HitCandidate3D> hit_test(const HitTestContext3D& context) const override;
        bool paint(GraphicItemPaintContext3D& context) const override;

    private:
        std::shared_ptr<const termin::Mesh3> mesh_;
        std::shared_ptr<const BaseColorTextureData3D> base_color_texture_;
        termin::LinearColor tint_{1.0f, 1.0f, 1.0f, 1.0f};
        FlatLighting3D flat_lighting_{};
        bool hit_test_enabled_ = true;
        bool depth_test_ = true;
    };

} // namespace termin::visual
