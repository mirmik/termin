#pragma once

#include <array>
#include <cstddef>
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include <termin/export.hpp>

namespace termin {

    class TERMIN_SCENE_API EntityClassificationRegistry {
    public:
        static constexpr std::size_t name_count = 64;
        using Names = std::array<std::string, name_count>;

        bool configure(const std::vector<std::string>& layer_names,
                       const std::vector<std::string>& flag_names,
                       std::string* error = nullptr);

        const Names& layer_names() const noexcept { return _layer_names; }
        const Names& flag_names() const noexcept { return _flag_names; }

        std::optional<std::size_t> layer_index(std::string_view name) const;
        std::optional<std::size_t> flag_index(std::string_view name) const;

    private:
        Names _layer_names{};
        Names _flag_names{};
    };

} // namespace termin
