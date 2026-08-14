#include "termin/collision/contact_patch.hpp"

#include <algorithm>
#include <cmath>
#include <tuple>

namespace termin::collision {
    namespace {

        bool vec_less(const Vec3& a, const Vec3& b) {
            return std::tie(a.x, a.y, a.z) < std::tie(b.x, b.y, b.z);
        }

        bool candidate_less(const ContactCandidate& a, const ContactCandidate& b) {
            if (a.signed_gap != b.signed_gap) {
                return a.signed_gap < b.signed_gap;
            }
            if (a.features.feature_a != b.features.feature_a) {
                return a.features.feature_a < b.features.feature_a;
            }
            if (a.features.feature_b != b.features.feature_b) {
                return a.features.feature_b < b.features.feature_b;
            }
            if (a.point_on_a_world != b.point_on_a_world) {
                return vec_less(a.point_on_a_world, b.point_on_a_world);
            }
            return vec_less(a.point_on_b_world, b.point_on_b_world);
        }

        double distance_squared(const Vec3& a, const Vec3& b) {
            const Vec3 delta = a - b;
            return delta.dot(delta);
        }

        Vec3 project_to_contact_plane(const Vec3& point, const Vec3& normal) {
            return point - normal * point.dot(normal);
        }

        bool duplicates(const ContactCandidate& a, const ContactCandidate& b, double tolerance_squared) {
            return distance_squared(a.point_on_a_world, b.point_on_a_world) <= tolerance_squared &&
                   distance_squared(a.point_on_b_world, b.point_on_b_world) <= tolerance_squared;
        }

        double coverage_score(const std::vector<Vec3>& positions,
                              std::size_t candidate,
                              const std::vector<std::size_t>& selected) {
            const Vec3& point = positions[candidate];
            if (selected.size() == 1) {
                return distance_squared(point, positions[selected[0]]);
            }
            if (selected.size() == 2) {
                const Vec3 first = positions[selected[0]] - point;
                const Vec3 second = positions[selected[1]] - point;
                const Vec3 area = first.cross(second);
                return area.dot(area);
            }

            double nearest = std::numeric_limits<double>::infinity();
            for (const std::size_t index : selected) {
                nearest = std::min(nearest, distance_squared(point, positions[index]));
            }
            return nearest;
        }

    } // namespace

    bool ContactPatch::same_pair(const ContactPatch& other) const {
        return (collider_a == other.collider_a && collider_b == other.collider_b) ||
               (collider_a == other.collider_b && collider_b == other.collider_a);
    }

    uint64_t ContactPatch::pair_key() const {
        auto a = reinterpret_cast<uintptr_t>(collider_a);
        auto b = reinterpret_cast<uintptr_t>(collider_b);
        if (a > b) {
            std::swap(a, b);
        }
        return (uint64_t(a) * 2654435761) ^ uint64_t(b);
    }

    std::optional<std::vector<ContactCandidate>>
    reduce_contact_candidates(std::span<const ContactCandidate> candidates,
                              const Vec3& normal_world,
                              const ContactPatchReductionConfig& config) {
        const double normal_length_squared = normal_world.dot(normal_world);
        if (!std::isfinite(normal_world.x) || !std::isfinite(normal_world.y) || !std::isfinite(normal_world.z) ||
            !std::isfinite(normal_length_squared) || normal_length_squared <= 1e-24) {
            return std::nullopt;
        }
        if (config.max_points == 0 || candidates.empty()) {
            return std::vector<ContactCandidate>{};
        }

        std::vector<ContactCandidate> unique(candidates.begin(), candidates.end());
        std::sort(unique.begin(), unique.end(), candidate_less);

        const double duplicate_tolerance_squared = config.duplicate_tolerance * config.duplicate_tolerance;
        std::vector<ContactCandidate> deduplicated;
        deduplicated.reserve(unique.size());
        for (const ContactCandidate& candidate : unique) {
            const bool duplicate =
                std::any_of(deduplicated.begin(), deduplicated.end(), [&](const ContactCandidate& kept) {
                    return duplicates(candidate, kept, duplicate_tolerance_squared);
                });
            if (!duplicate) {
                deduplicated.push_back(candidate);
            }
        }

        if (deduplicated.size() <= config.max_points) {
            return deduplicated;
        }

        const Vec3 normal = normal_world / std::sqrt(normal_length_squared);

        std::vector<Vec3> positions;
        positions.reserve(deduplicated.size());
        for (const ContactCandidate& candidate : deduplicated) {
            positions.push_back(project_to_contact_plane(candidate.representative_point_world(), normal));
        }

        std::vector<std::size_t> selected{0};
        selected.reserve(config.max_points);
        while (selected.size() < config.max_points) {
            std::size_t best = deduplicated.size();
            double best_score = -1.0;
            for (std::size_t i = 0; i < deduplicated.size(); ++i) {
                if (std::find(selected.begin(), selected.end(), i) != selected.end()) {
                    continue;
                }

                const double score = coverage_score(positions, i, selected);
                if (best == deduplicated.size() || score > best_score + config.metric_tolerance ||
                    (std::abs(score - best_score) <= config.metric_tolerance &&
                     candidate_less(deduplicated[i], deduplicated[best]))) {
                    best = i;
                    best_score = score;
                }
            }
            selected.push_back(best);
        }

        std::vector<ContactCandidate> reduced;
        reduced.reserve(selected.size());
        for (const std::size_t index : selected) {
            reduced.push_back(deduplicated[index]);
        }
        return reduced;
    }

    std::optional<ContactPatch> reduce_contact_patch(const ContactPatch& patch,
                                                     const ContactPatchReductionConfig& config) {
        ContactPatch result = patch;
        std::optional<std::vector<ContactCandidate>> points =
            reduce_contact_candidates(patch.points, patch.normal_world, config);
        if (!points) {
            return std::nullopt;
        }
        result.points = std::move(*points);
        return result;
    }

} // namespace termin::collision
