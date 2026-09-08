#pragma once

#include <tcbase/tc_log.h>
#include <vulkan/vulkan.h>

#include <stdexcept>
#include <string>

namespace tgfx::vulkan_detail {

    struct DeviceOps {
        PFN_vkQueueSubmit queue_submit = vkQueueSubmit;
        PFN_vkWaitForFences wait_for_fences = vkWaitForFences;
        PFN_vkResetFences reset_fences = vkResetFences;
        PFN_vkQueueWaitIdle queue_wait_idle = vkQueueWaitIdle;
        PFN_vkDeviceWaitIdle device_wait_idle = vkDeviceWaitIdle;
    };

    // A submit/fence lifecycle failure leaves frame-slot ownership ambiguous.
    // This is deliberately fail-stop: callers may tear the device down, but
    // must not issue another submit or wait on a fence that may never signal.
    class DeviceFailureState {
    public:
        bool terminal() const {
            return terminal_;
        }

        VkResult result() const {
            return result_;
        }

        const std::string& context() const {
            return context_;
        }

        void require_operational(const char* operation) const {
            if (!terminal_)
                return;
            tc_log(TC_LOG_ERROR,
                   "[Vulkan] refusing %s after terminal device failure in %s: VkResult=%d",
                   operation,
                   context_.c_str(),
                   static_cast<int>(result_));
            throw std::runtime_error("Vulkan device is in a terminal error state");
        }

        [[noreturn]] void fail(const char* context, VkResult result) {
            if (!terminal_) {
                terminal_ = true;
                result_ = result;
                context_ = context;
                tc_log(TC_LOG_ERROR,
                       "[Vulkan] terminal device failure in %s: VkResult=%d",
                       context_.c_str(),
                       static_cast<int>(result_));
            }
            throw std::runtime_error("Vulkan terminal device failure");
        }

    private:
        bool terminal_ = false;
        VkResult result_ = VK_SUCCESS;
        std::string context_;
    };

    inline void submit_or_fail(DeviceFailureState& failure,
                               const DeviceOps& ops,
                               VkQueue queue,
                               const VkSubmitInfo& submit,
                               VkFence fence,
                               const char* context) {
        failure.require_operational(context);
        const VkResult result = ops.queue_submit(queue, 1, &submit, fence);
        if (result != VK_SUCCESS)
            failure.fail(context, result);
    }

    inline void prepare_fence_or_fail(DeviceFailureState& failure,
                                      const DeviceOps& ops,
                                      VkDevice device,
                                      VkFence fence,
                                      bool& in_flight,
                                      const char* wait_context,
                                      const char* reset_context) {
        failure.require_operational(wait_context);
        if (!in_flight)
            return;
        const VkResult wait_result = ops.wait_for_fences(device, 1, &fence, VK_TRUE, UINT64_MAX);
        if (wait_result != VK_SUCCESS)
            failure.fail(wait_context, wait_result);
        const VkResult reset_result = ops.reset_fences(device, 1, &fence);
        if (reset_result != VK_SUCCESS)
            failure.fail(reset_context, reset_result);
        in_flight = false;
    }

} // namespace tgfx::vulkan_detail
