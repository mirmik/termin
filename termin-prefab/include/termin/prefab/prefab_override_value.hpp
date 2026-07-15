#pragma once

#include <cstdint>
#include <optional>
#include <string>
#include <string_view>

#include <tcbase/tc_trent.hpp>
#include <termin/prefab/export.hpp>

namespace termin::prefab {

class TERMIN_PREFAB_API PrefabOverrideResourceResolver {
public:
    virtual ~PrefabOverrideResourceResolver() = default;

    virtual bool resolve(
        std::string_view resource_type,
        std::string_view target_kind,
        std::string_view uuid,
        std::string_view display_name,
        tc::trent& result,
        std::string& error
    ) const = 0;
};

// A language-neutral, JSON-safe override value. The stored representation is
// deliberately distinct from raw tc_value so container and semantic type
// identity cannot be inferred or lost during a round trip.
class TERMIN_PREFAB_API PrefabOverrideValue {
public:
    static constexpr const char* Schema = "termin.prefab.override-value";
    static constexpr int64_t Version = 1;

    PrefabOverrideValue();

    static std::optional<PrefabOverrideValue> parse(
        const tc_value* encoded,
        std::string& error
    );
    static std::optional<PrefabOverrideValue> parse_json(
        const std::string& json,
        std::string& error
    );
    static std::optional<PrefabOverrideValue> from_inspect_value(
        const tc_value* value,
        std::string_view target_kind,
        std::string& error
    );

    tc_value serialize() const;
    std::string to_json(int indent = -1) const;
    std::string tag() const;

    // Produces the ordinary tc_value payload consumed by inspect setters.
    // Semantic kind/resource nodes must match target_kind exactly.
    std::optional<tc::trent> materialize_for_inspect(
        std::string_view target_kind,
        std::string& error
    ) const;
    std::optional<tc::trent> materialize_for_inspect(
        std::string_view target_kind,
        const PrefabOverrideResourceResolver& resource_resolver,
        std::string& error
    ) const;

private:
    explicit PrefabOverrideValue(tc::trent encoded);

    tc::trent _encoded;
};

} // namespace termin::prefab
