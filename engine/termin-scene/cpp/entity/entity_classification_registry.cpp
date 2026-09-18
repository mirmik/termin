#include <termin/entity/entity_classification_registry.hpp>

#include <cctype>
#include <unordered_map>

namespace termin {
    namespace {
        std::string trim_name(std::string_view value) {
            std::size_t first = 0;
            while (first < value.size() && std::isspace(static_cast<unsigned char>(value[first]))) {
                ++first;
            }
            std::size_t last = value.size();
            while (last > first && std::isspace(static_cast<unsigned char>(value[last - 1]))) {
                --last;
            }
            return std::string(value.substr(first, last - first));
        }

        bool prepare_names(const std::vector<std::string>& source,
                           EntityClassificationRegistry::Names& destination,
                           std::string_view kind,
                           std::string* error) {
            if (source.size() != EntityClassificationRegistry::name_count) {
                if (error) {
                    *error = std::string(kind) + " names must contain exactly 64 entries";
                }
                return false;
            }

            std::unordered_map<std::string, std::size_t> occupied;
            for (std::size_t index = 0; index < source.size(); ++index) {
                std::string name = trim_name(source[index]);
                if (!name.empty()) {
                    const auto [existing, inserted] = occupied.emplace(name, index);
                    if (!inserted) {
                        if (error) {
                            *error = std::string(kind) + " name '" + name + "' is duplicated at indices " +
                                     std::to_string(existing->second) + " and " + std::to_string(index);
                        }
                        return false;
                    }
                }
                destination[index] = std::move(name);
            }
            return true;
        }

        std::optional<std::size_t> find_name(const EntityClassificationRegistry::Names& names,
                                             std::string_view requested) {
            const std::string normalized = trim_name(requested);
            if (normalized.empty()) {
                return std::nullopt;
            }
            for (std::size_t index = 0; index < names.size(); ++index) {
                if (names[index] == normalized) {
                    return index;
                }
            }
            return std::nullopt;
        }
    } // namespace

    bool EntityClassificationRegistry::configure(const std::vector<std::string>& layer_names,
                                                  const std::vector<std::string>& flag_names,
                                                  std::string* error) {
        Names staged_layers{};
        Names staged_flags{};
        if (!prepare_names(layer_names, staged_layers, "layer", error) ||
            !prepare_names(flag_names, staged_flags, "flag", error)) {
            return false;
        }

        _layer_names = std::move(staged_layers);
        _flag_names = std::move(staged_flags);
        if (error) {
            error->clear();
        }
        return true;
    }

    std::optional<std::size_t> EntityClassificationRegistry::layer_index(std::string_view name) const {
        return find_name(_layer_names, name);
    }

    std::optional<std::size_t> EntityClassificationRegistry::flag_index(std::string_view name) const {
        return find_name(_flag_names, name);
    }

} // namespace termin
