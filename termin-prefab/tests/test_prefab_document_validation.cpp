#include <cmath>
#include <iostream>
#include <limits>
#include <string>
#include <utility>
#include <vector>

#include <trent/json.h>
#include <termin/prefab/prefab_document.hpp>

#define TEST_ASSERT(cond, msg) \
    do { \
        if (!(cond)) { \
            std::cerr << "FAIL: " << msg << " (line " << __LINE__ << ")\n"; \
            return 1; \
        } \
    } while (0)

namespace {

nos::trent valid_document_data() {
    nos::trent data;
    data["version"] = termin::prefab::PrefabDocument::CurrentVersion;
    data["uuid"] = "validation-document";
    nos::trent& root = data["root"];
    root["uuid"] = "validation-root";
    root["name"] = "Root";
    root["priority"] = int64_t{0};
    root["visible"] = true;
    root["enabled"] = true;
    root["pickable"] = true;
    root["selectable"] = true;
    root["layer"] = int64_t{0};
    root["flags"] = int64_t{0};
    root["pose"]["position"].init(nos::trent::type::list);
    root["pose"]["position"].push_back(0.0);
    root["pose"]["position"].push_back(1.0);
    root["pose"]["position"].push_back(2.0);
    root["pose"]["rotation"].init(nos::trent::type::list);
    root["pose"]["rotation"].push_back(0.0);
    root["pose"]["rotation"].push_back(0.0);
    root["pose"]["rotation"].push_back(0.0);
    root["pose"]["rotation"].push_back(1.0);
    root["scale"].init(nos::trent::type::list);
    root["scale"].push_back(1.0);
    root["scale"].push_back(1.0);
    root["scale"].push_back(1.0);
    root["components"].init(nos::trent::type::list);
    root["children"].init(nos::trent::type::list);
    return data;
}

bool rejects(const nos::trent& data, const std::string& expected_path) {
    const auto result = termin::prefab::PrefabDocument::parse_json(nos::json::dump(data));
    return !result.ok() && result.message.find(expected_path) != std::string::npos;
}

} // namespace

int main() {
    const nos::trent valid = valid_document_data();
    auto parsed = termin::prefab::PrefabDocument::parse_json(nos::json::dump(valid));
    TEST_ASSERT(parsed.ok(), "canonical v3 document should validate");
    TEST_ASSERT(
        termin::prefab::PrefabDocument::parse_json(parsed.document.to_json()).ok(),
        "validated document should round-trip"
    );

    for (const char* field : {"visible", "enabled", "pickable", "selectable"}) {
        nos::trent malformed = valid;
        malformed["root"][field] = int64_t{1};
        TEST_ASSERT(rejects(malformed, std::string("root.") + field),
                    "entity flags must be booleans with field diagnostics");
    }

    for (const char* field : {"priority", "layer", "flags"}) {
        nos::trent malformed = valid;
        malformed["root"][field] = 1.5;
        TEST_ASSERT(rejects(malformed, std::string("root.") + field),
                    "entity integer fields must reject fractions");
    }

    nos::trent priority_overflow = valid;
    priority_overflow["root"]["priority"] =
        static_cast<double>(std::numeric_limits<int>::max()) + 1.0;
    TEST_ASSERT(rejects(priority_overflow, "root.priority"),
                "priority must fit native int");

    for (const char* field : {"layer", "flags"}) {
        nos::trent negative = valid;
        negative["root"][field] = int64_t{-1};
        TEST_ASSERT(rejects(negative, std::string("root.") + field),
                    "bit fields must be non-negative");
    }

    struct VectorCase {
        const char* path;
        size_t size;
    };
    const std::vector<VectorCase> vectors = {
        {"position", 3}, {"rotation", 4}, {"scale", 3},
    };
    for (const VectorCase& item : vectors) {
        nos::trent malformed = valid;
        nos::trent& value = std::string(item.path) == "scale"
            ? malformed["root"]["scale"]
            : malformed["root"]["pose"][item.path];
        value.as_list().pop_back();
        const std::string expected_path = std::string("root.") +
            (std::string(item.path) == "scale"
                ? "scale"
                : std::string("pose.") + item.path);
        TEST_ASSERT(rejects(malformed, expected_path),
                    "transform vectors must have their canonical arity");

        malformed = valid;
        nos::trent& non_numeric = std::string(item.path) == "scale"
            ? malformed["root"]["scale"]
            : malformed["root"]["pose"][item.path];
        non_numeric[0] = "not-a-number";
        TEST_ASSERT(rejects(malformed, expected_path + "[0]"),
                    "transform vectors must contain finite numbers");
    }

    nos::trent child_malformed = valid;
    nos::trent child = valid["root"];
    child["uuid"] = "validation-child";
    child["pose"]["rotation"][2] = "bad";
    child_malformed["root"]["children"].push_back(std::move(child));
    TEST_ASSERT(rejects(child_malformed, "root.children[0].pose.rotation[2]"),
                "nested diagnostics must identify the complete source path");

    std::string non_finite_json = nos::json::dump(valid);
    const size_t position_key = non_finite_json.find("\"position\"");
    const size_t first_position_value = non_finite_json.find('[', position_key) + 1;
    const size_t first_position_end = non_finite_json.find(',', first_position_value);
    non_finite_json.replace(
        first_position_value,
        first_position_end - first_position_value,
        "1e9999"
    );
    const auto non_finite =
        termin::prefab::PrefabDocument::parse_json(non_finite_json);
    TEST_ASSERT(!non_finite.ok() &&
                    non_finite.message.find("root.pose.position[0]") != std::string::npos,
                "non-finite transform numbers must be rejected at their exact source path");

    return 0;
}
