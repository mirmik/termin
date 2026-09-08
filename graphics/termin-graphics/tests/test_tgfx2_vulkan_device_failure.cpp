#include "tgfx2/vulkan/internal/device_failure.hpp"
#include "tgfx2/vulkan/vulkan_render_device.hpp"

#include <cstdio>
#include <cstdlib>
#include <stdexcept>
#include <memory>

namespace {
    struct Trace {
        VkResult submit_result = VK_SUCCESS;
        VkResult wait_result = VK_SUCCESS;
        VkResult reset_result = VK_SUCCESS;
        unsigned submits = 0;
        unsigned waits = 0;
        unsigned resets = 0;
    } trace;

    VKAPI_ATTR VkResult VKAPI_CALL
    queue_submit(VkQueue, uint32_t, const VkSubmitInfo*, VkFence) {
        ++trace.submits;
        return trace.submit_result;
    }

    VKAPI_ATTR VkResult VKAPI_CALL
    wait_for_fences(VkDevice, uint32_t, const VkFence*, VkBool32, uint64_t) {
        ++trace.waits;
        return trace.wait_result;
    }

    VKAPI_ATTR VkResult VKAPI_CALL reset_fences(VkDevice, uint32_t, const VkFence*) {
        ++trace.resets;
        return trace.reset_result;
    }

    template <class Call> bool throws(Call&& call) {
        try {
            call();
        } catch (const std::runtime_error&) {
            return true;
        }
        return false;
    }

    bool test_submit_failure() {
        trace = {};
        trace.submit_result = VK_ERROR_DEVICE_LOST;
        tgfx::vulkan_detail::DeviceOps ops;
        ops.queue_submit = queue_submit;
        tgfx::vulkan_detail::DeviceFailureState failure;
        VkSubmitInfo submit{};
        submit.sType = VK_STRUCTURE_TYPE_SUBMIT_INFO;

        bool ok = throws([&] {
            tgfx::vulkan_detail::submit_or_fail(
                failure, ops, VK_NULL_HANDLE, submit, VK_NULL_HANDLE, "fault-injected submit");
        });
        ok &= failure.terminal() && failure.result() == VK_ERROR_DEVICE_LOST && trace.submits == 1;
        ok &= throws([&] {
            tgfx::vulkan_detail::submit_or_fail(
                failure, ops, VK_NULL_HANDLE, submit, VK_NULL_HANDLE, "retry submit");
        });
        // The retry is rejected before native submission, so no fence can be
        // left in an unsignalable wait cycle.
        return ok && trace.submits == 1;
    }

    bool test_prepare_failure(VkResult wait_result, VkResult reset_result) {
        trace = {};
        trace.wait_result = wait_result;
        trace.reset_result = reset_result;
        tgfx::vulkan_detail::DeviceOps ops;
        ops.wait_for_fences = wait_for_fences;
        ops.reset_fences = reset_fences;
        tgfx::vulkan_detail::DeviceFailureState failure;
        bool in_flight = true;

        bool ok = throws([&] {
            tgfx::vulkan_detail::prepare_fence_or_fail(failure,
                                                       ops,
                                                       VK_NULL_HANDLE,
                                                       VK_NULL_HANDLE,
                                                       in_flight,
                                                       "fault-injected wait",
                                                       "fault-injected reset");
        });
        const unsigned waits = trace.waits;
        const unsigned resets = trace.resets;
        ok &= failure.terminal() && in_flight;
        ok &= throws([&] {
            tgfx::vulkan_detail::prepare_fence_or_fail(failure,
                                                       ops,
                                                       VK_NULL_HANDLE,
                                                       VK_NULL_HANDLE,
                                                       in_flight,
                                                       "retry wait",
                                                       "retry reset");
        });
        ok &= trace.waits == waits && trace.resets == resets;
        ok &= wait_result == VK_SUCCESS ? (waits == 1 && resets == 1) : (waits == 1 && resets == 0);
        return ok;
    }

    bool test_prepare_success() {
        trace = {};
        tgfx::vulkan_detail::DeviceOps ops;
        ops.wait_for_fences = wait_for_fences;
        ops.reset_fences = reset_fences;
        tgfx::vulkan_detail::DeviceFailureState failure;
        bool in_flight = true;
        tgfx::vulkan_detail::prepare_fence_or_fail(failure,
                                                   ops,
                                                   VK_NULL_HANDLE,
                                                   VK_NULL_HANDLE,
                                                   in_flight,
                                                   "wait",
                                                   "reset");
        return !failure.terminal() && !in_flight && trace.waits == 1 && trace.resets == 1;
    }

    bool test_render_device_integration() {
        const char* validation_required = std::getenv("TGFX2_GPU_VALIDATION_REQUIRED");
        if (validation_required && validation_required[0] == '1') {
            std::puts("Native failure integration skipped because required validation layer is unavailable");
            return true;
        }
        trace = {};
        trace.submit_result = VK_ERROR_DEVICE_LOST;
        tgfx::VulkanDeviceCreateInfo info;
        info.enable_validation = false;
        tgfx::vulkan_detail::DeviceOps ops;
        ops.queue_submit = queue_submit;
        std::unique_ptr<tgfx::VulkanRenderDevice> device;
        try {
            device = std::make_unique<tgfx::VulkanRenderDevice>(info, ops);
        } catch (const std::exception& error) {
            std::printf("Vulkan device unavailable; native failure integration skipped: %s\n", error.what());
            return true;
        }

        auto commands = device->create_command_list();
        commands->begin();
        commands->end();
        bool ok = throws([&] { device->submit(*commands); });
        ok &= device->has_terminal_error() && trace.submits == 1;
        ok &= throws([&] { device->submit(*commands); });
        ok &= throws([&] { (void)device->create_command_list(); });
        ok &= trace.submits == 1;
        // Cleanup remains allowed, but it cannot recover the fail-stop state.
        device->wait_idle();
        ok &= device->has_terminal_error();
        return ok;
    }
}

int main() {
    const bool ok = test_submit_failure() &&
                    test_prepare_failure(VK_TIMEOUT, VK_SUCCESS) &&
                    test_prepare_failure(VK_SUCCESS, VK_ERROR_DEVICE_LOST) &&
                    test_prepare_success() &&
                    test_render_device_integration();
    if (!ok) {
        std::fprintf(stderr, "Vulkan terminal device failure contract failed\n");
        return 1;
    }
    std::puts("Vulkan terminal submit/fence failure contract passed");
    return 0;
}
