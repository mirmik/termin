#include <tcbase/tc_log.h>

#include <atomic>
#include <chrono>
#include <future>
#include <thread>

#include "guard_main.h"

namespace {
struct Notification {
    std::promise<void> entered;
    std::shared_future<void> release;
    std::atomic<size_t> pending{0};
};

void notify(void* data) {
    auto& notification = *static_cast<Notification*>(data);
    notification.pending.store(tc_log_capture_pending());
    notification.entered.set_value();
    notification.release.wait();
}
} // namespace

TEST_CASE("log unsubscribe quiesces native producer notification before destruction") {
    using namespace std::chrono_literals;
    tc_log_capture_stop();
    CHECK(tc_log_capture_start(8) == 1);
    std::promise<void> release;
    Notification notification;
    notification.release = release.get_future().share();
    auto entered = notification.entered.get_future();
    tc_log_capture_set_wakeup(notify, &notification);
    std::thread producer([] { tc_log_info("native producer"); });
    const bool started = entered.wait_for(2s) == std::future_status::ready;
    if (!started) {
        release.set_value();
        producer.join();
        tc_log_capture_stop();
        CHECK(started);
        return;
    }
    CHECK(notification.pending.load() == 1);
    std::promise<void> unsubscribing;
    auto unsubscribed = std::async(std::launch::async, [&] {
        unsubscribing.set_value();
        tc_log_capture_set_wakeup(nullptr, nullptr);
    });
    unsubscribing.get_future().wait();
    CHECK(unsubscribed.wait_for(20ms) == std::future_status::timeout);
    release.set_value();
    producer.join();
    CHECK(unsubscribed.wait_for(2s) == std::future_status::ready);
    unsubscribed.get();
    // The queue remains readable after the notification owner has detached.
    tc_log_record record;
    CHECK(tc_log_capture_drain(&record, 1, nullptr) == 1);
    std::thread detached_producer([] { tc_log_info("after unsubscribe"); });
    detached_producer.join();
    CHECK(tc_log_capture_pending() == 1);
    tc_log_capture_stop();
}

GUARD_TEST_MAIN();
