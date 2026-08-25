#include "termin_visual_scene/items/static_mesh_item3d.hpp"

#include "item_geometry3d_internal.hpp"

#include <cmath>
#include <stdexcept>

#include <tcbase/tc_log.hpp>

namespace termin::visual {
    namespace {

        bool valid_mesh(const termin::Mesh3& mesh) {
            if (mesh.vertices.empty() || mesh.triangles.empty() || mesh.triangles.size() % 3 != 0)
                return false;
            if (!std::all_of(mesh.vertices.begin(), mesh.vertices.end(), [](termin::Vec3f vertex) {
                    return vertex.is_finite();
                }))
                return false;
            return std::all_of(mesh.triangles.begin(), mesh.triangles.end(), [&](std::uint32_t index) {
                return index < mesh.vertices.size();
            });
        }

        void require_mesh(const std::shared_ptr<const termin::Mesh3>& mesh) {
            if (!mesh || !valid_mesh(*mesh)) {
                tc::Log::error("StaticMeshItem3D rejected invalid mesh replacement");
                throw std::invalid_argument("StaticMeshItem3D requires a finite indexed triangle mesh");
            }
        }

        void require_tint(termin::LinearColor tint) {
            if (!detail::finite(tint)) {
                tc::Log::error("StaticMeshItem3D rejected a non-finite tint");
                throw std::invalid_argument("StaticMeshItem3D tint must be finite");
            }
        }

        void require_texture(const std::shared_ptr<const BaseColorTextureData3D>& texture) {
            const std::uint64_t expected = texture
                                               ? static_cast<std::uint64_t>(texture->width) * texture->height * 4u
                                               : 0u;
            if (!texture || texture->width == 0 || texture->height == 0 ||
                expected != texture->rgba8.size()) {
                tc::Log::error("StaticMeshItem3D rejected invalid base-color texture replacement");
                throw std::invalid_argument("StaticMeshItem3D requires a non-empty RGBA8 base-color texture");
            }
        }

    } // namespace

    StaticMeshItem3D::StaticMeshItem3D(std::shared_ptr<const termin::Mesh3> mesh,
                                       termin::LinearColor tint,
                                       bool depth_test)
        : NativeVisualItem3D("termin.visual.StaticMesh3D"),
          depth_test_(depth_test) {
        set_mesh(std::move(mesh));
        set_tint(tint);
    }

    void StaticMeshItem3D::set_mesh(std::shared_ptr<const termin::Mesh3> mesh) {
        require_mesh(mesh);
        if (base_color_texture_ && !mesh->has_uvs()) {
            tc::Log::error("StaticMeshItem3D rejected a mesh without UVs while a base-color texture is set");
            throw std::invalid_argument("StaticMeshItem3D textured mesh requires one UV per vertex");
        }
        mesh_ = std::move(mesh);
    }

    void StaticMeshItem3D::set_tint(termin::LinearColor tint) {
        require_tint(tint);
        tint_ = tint;
    }

    void StaticMeshItem3D::set_base_color_texture(std::shared_ptr<const BaseColorTextureData3D> texture) {
        require_texture(texture);
        if (flat_lighting_.enabled) {
            tc::Log::error("StaticMeshItem3D rejected a base-color texture while flat lighting is enabled");
            throw std::invalid_argument("StaticMeshItem3D flat lighting is only supported for untextured meshes");
        }
        if (!mesh_->has_uvs()) {
            tc::Log::error("StaticMeshItem3D rejected a base-color texture for a mesh without UVs");
            throw std::invalid_argument("StaticMeshItem3D textured mesh requires one UV per vertex");
        }
        base_color_texture_ = std::move(texture);
    }

    void StaticMeshItem3D::set_flat_lighting(termin::Vec3f direction, float ambient, float diffuse) {
        termin::Vec3f normalized;
        if (!direction.is_finite() || !direction.try_normalized(normalized) || !std::isfinite(ambient) ||
            !std::isfinite(diffuse) || ambient < 0.0f || diffuse < 0.0f) {
            tc::Log::error("StaticMeshItem3D rejected invalid flat-lighting parameters");
            throw std::invalid_argument(
                "StaticMeshItem3D flat lighting requires a finite direction and non-negative finite intensities");
        }
        if (base_color_texture_) {
            tc::Log::error("StaticMeshItem3D rejected flat lighting for a textured mesh");
            throw std::invalid_argument("StaticMeshItem3D flat lighting is only supported for untextured meshes");
        }
        flat_lighting_ = {
            .enabled = true,
            .direction = normalized,
            .ambient = ambient,
            .diffuse = diffuse,
        };
    }

    std::optional<VisualBounds3D> StaticMeshItem3D::local_bounds() const {
        const auto bounds =
            detail::bounds_of(mesh_->vertices.size(), [&](std::size_t index) { return mesh_->vertices[index]; });
        return bounds ? std::optional<VisualBounds3D>(detail::to_visual_bounds(*bounds)) : std::nullopt;
    }

    std::optional<HitCandidate3D> StaticMeshItem3D::hit_test(const HitTestContext3D& context) const {
        if (!hit_test_enabled_)
            return std::nullopt;
        return detail::ray_triangles(
            context.local_ray, mesh_->vertices.size(), mesh_->triangles, {}, [&](std::size_t index) {
                return mesh_->vertices[index];
            });
    }

    bool StaticMeshItem3D::paint(GraphicItemPaintContext3D& context) const {
        const StaticMeshDrawPacket3D packet{mesh_, base_color_texture_, tint_, flat_lighting_, depth_test_};
        return context.submit(StaticMeshDrawProtocol3D, &packet, sizeof(packet));
    }

} // namespace termin::visual
