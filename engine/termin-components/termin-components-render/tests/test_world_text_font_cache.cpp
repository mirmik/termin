#include "guard_main.h"
GUARD_TEST_MAIN();

#include "../src/world_text_font_cache.hpp"
#include <vector>

TEST_CASE("world labels share a single font atlas and release it with the last owner") {
    termin::detail::WorldTextFontCache cache;
    std::vector<std::shared_ptr<tgfx::FontAtlas>> labels;
    for (int i = 0; i < 81; ++i)
        labels.push_back(cache.acquire(WORLD_TEXT_TEST_FONT));
    for (const auto& label : labels)
        CHECK(label == labels.front());
    std::weak_ptr<tgfx::FontAtlas> lifetime = labels.front();
    labels.erase(labels.begin(), labels.end() - 1);
    CHECK(!lifetime.expired());
    labels.clear();
    CHECK(lifetime.expired());
    auto reloaded = cache.acquire(WORLD_TEXT_TEST_FONT);
    CHECK(reloaded != nullptr);
    CHECK(lifetime.expired());
}

TEST_CASE("different fonts stay independent while existing labels keep their atlas") {
    termin::detail::WorldTextFontCache cache;
    auto first = cache.acquire(WORLD_TEXT_TEST_FONT);
    auto second = cache.acquire(WORLD_TEXT_TEST_FONT_OTHER);
    CHECK(first != second);
    CHECK(cache.acquire(WORLD_TEXT_TEST_FONT) == first);
    CHECK(cache.acquire(WORLD_TEXT_TEST_FONT_OTHER) == second);
    first.reset();
    CHECK(cache.acquire(WORLD_TEXT_TEST_FONT_OTHER) == second);
}
