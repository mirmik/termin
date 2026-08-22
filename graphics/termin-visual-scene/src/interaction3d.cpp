#include "termin_visual_scene/interaction3d.hpp"

#include <exception>

#include <tcbase/tc_log.hpp>

namespace termin::visual {
    namespace {

        bool valid_handle(VisualItem3DHandle value) {
            return !tc_visual_item3d_handle_is_invalid(value);
        }

        bool same_handle(VisualItem3DHandle left, VisualItem3DHandle right) {
            return tc_visual_item3d_handle_eq(left, right);
        }

    } // namespace

    std::size_t SceneInteraction3D::HandleHash::operator()(const HandleKey& value) const noexcept {
        std::size_t result = std::hash<std::uint64_t>{}(value.scene_id);
        result ^= std::hash<std::uint32_t>{}(value.index) + 0x9e3779b9u + (result << 6u) + (result >> 2u);
        result ^= std::hash<std::uint32_t>{}(value.generation) + 0x9e3779b9u + (result << 6u) + (result >> 2u);
        return result;
    }

    SceneInteraction3D::HandleKey SceneInteraction3D::key_(VisualItem3DHandle handle) {
        return {handle.scene_id, handle.index, handle.generation};
    }

    VisualItem3DHandle SceneInteraction3D::hit_handle_(const std::unordered_map<PointerId3D, HitResult3D>& values,
                                                       PointerId3D pointer) {
        const auto found = values.find(pointer);
        return found != values.end() ? found->second.item : tc_visual_item3d_handle_invalid();
    }

    std::optional<HitResult3D> SceneInteraction3D::hit_(
        const std::unordered_map<PointerId3D, HitResult3D>& values, PointerId3D pointer) {
        const auto found = values.find(pointer);
        return found != values.end() ? std::optional<HitResult3D>{found->second} : std::nullopt;
    }

    bool SceneInteraction3D::dispatch_target_(const TargetPointerEvent3D& event) {
        const auto handler = target_pointer_handlers_.find(key_(event.target));
        if (handler == target_pointer_handlers_.end())
            return false;
        // The callback may rebuild the interaction and remove its own map
        // entry. Keep the callable alive independently of that mutation.
        TargetPointerHandler callback = handler->second;
        try {
            callback(event);
        } catch (const std::exception& error) {
            tc::Log::error("SceneInteraction3D target pointer callback failed: %s", error.what());
            return true;
        } catch (...) {
            tc::Log::error("SceneInteraction3D target pointer callback failed with an unknown exception");
            return true;
        }
        return false;
    }

    bool SceneInteraction3D::reconcile_(const TcVisualScene3D& scene,
                                        const PointerEvent3D& event,
                                        PointerDispatch3D& result,
                                        std::uint64_t route_revision) {
        const auto invalid = [&](VisualItem3DHandle handle) {
            const auto* item = scene.resolve(handle);
            return item == nullptr || !scene.effective_visible(*item) || !scene.effective_enabled(*item);
        };
        const auto hovered = hit_(hovered_, event.pointer);
        const auto captured = hit_(captured_, event.pointer);
        const bool invalidate_hovered = hovered && invalid(hovered->item);
        const bool invalidate_captured = captured && invalid(captured->item);
        if (invalidate_hovered)
            hovered_.erase(event.pointer);
        if (invalidate_captured) {
            captured_.erase(event.pointer);
            pressed_.erase(event.pointer);
            sequence_buttons_.erase(event.pointer);
        } else {
            std::erase_if(pressed_,
                          [&](const auto& pair) { return pair.first == event.pointer && invalid(pair.second.item); });
        }

        bool invalidated = false;
        if (invalidate_hovered) {
            result.callback_failed |= dispatch_target_(
                {TargetPointerEventKind3D::Leave, event, hovered->item, hovered->part, std::nullopt, false});
            invalidated = state_revision_ != route_revision;
        }
        if (invalidate_captured) {
            result.callback_failed |= dispatch_target_(
                {TargetPointerEventKind3D::Cancel, event, captured->item, captured->part, std::nullopt, true});
            invalidated = invalidated || state_revision_ != route_revision;
        }
        if (invalidate_captured) {
            // Invalid capture terminates this pointer sequence. The Cancel
            // callback may try to capture another item (or route a nested
            // Down), but the original event must neither use nor retain that
            // newly published ownership.
            if (invalidate_hovered)
                hovered_.erase(event.pointer);
            pressed_.erase(event.pointer);
            captured_.erase(event.pointer);
            last_events_.erase(event.pointer);
            sequence_buttons_.erase(event.pointer);
            ++state_revision_;
            return false;
        }
        if (invalidated)
            return false;
        // Handlers intentionally survive until invalid targets have received
        // their final leave/cancel notification above.
        std::erase_if(target_pointer_handlers_, [&](const auto& pair) {
            return scene.resolve(VisualItem3DHandle{pair.first.scene_id, pair.first.index, pair.first.generation}) ==
                   nullptr;
        });
        std::erase_if(action_handlers_, [&](const auto& pair) {
            return scene.resolve(VisualItem3DHandle{pair.first.scene_id, pair.first.index, pair.first.generation}) ==
                   nullptr;
        });
        return true;
    }

    PointerDispatch3D SceneInteraction3D::route(const TcVisualScene3D& scene, const PointerEvent3D& event) {
        PointerDispatch3D result;
        PointerEvent3D routed_event = event;
        if (event.kind == PointerEventKind3D::Cancel) {
            const auto sequence_button = sequence_buttons_.find(event.pointer);
            if (sequence_button != sequence_buttons_.end())
                routed_event.button = sequence_button->second;
        }
        // Each route owns an epoch. A callback that routes another event must
        // make the nested route authoritative and stop the outer event from
        // publishing or dispatching its stale continuation.
        const std::uint64_t route_revision = ++state_revision_;
        bool terminal_callback_invalidated_route = false;
        result.event = routed_event;
        last_events_[event.pointer] = routed_event;
        if (!reconcile_(scene, routed_event, result, route_revision))
            return result;
        if (event.kind == PointerEventKind3D::Down)
            sequence_buttons_[event.pointer] = event.button;
        if (event.kind != PointerEventKind3D::Cancel)
            result.hit = hit_test(scene, event.world_ray);
        const auto previous_hover = hit_(hovered_, event.pointer);
        const bool same_hover = event.kind != PointerEventKind3D::Cancel && previous_hover && result.hit &&
                                same_handle(previous_hover->item, result.hit->item) &&
                                previous_hover->part == result.hit->part;
        if (event.kind != PointerEventKind3D::Cancel && !same_hover) {
            if (previous_hover) {
                // The previous owner is gone before Leave runs. Reentrant
                // cancellation must not deliver a duplicate Leave.
                hovered_.erase(event.pointer);
                result.callback_failed |= dispatch_target_({TargetPointerEventKind3D::Leave,
                                                            event,
                                                            previous_hover->item,
                                                            previous_hover->part,
                                                            result.hit,
                                                            false});
                if (state_revision_ != route_revision)
                    return result;
            }
            if (result.hit) {
                // Conversely, Enter is published before user code so a
                // reentrant replacement can balance it with one final Leave.
                hovered_[event.pointer] = *result.hit;
                result.callback_failed |= dispatch_target_({TargetPointerEventKind3D::Enter,
                                                            event,
                                                            result.hit->item,
                                                            result.hit->part,
                                                            result.hit,
                                                            false});
                if (state_revision_ != route_revision)
                    return result;
            }
        } else if (event.kind != PointerEventKind3D::Cancel && result.hit) {
            hovered_[event.pointer] = *result.hit;
        }

        if (event.kind == PointerEventKind3D::Down) {
            if (result.hit) {
                pressed_[event.pointer] = *result.hit;
                captured_[event.pointer] = *result.hit;
                result.target = result.hit->item;
                result.callback_failed |= dispatch_target_({TargetPointerEventKind3D::Down,
                                                            event,
                                                            result.hit->item,
                                                            result.hit->part,
                                                            result.hit,
                                                            true});
                if (state_revision_ != route_revision)
                    return result;
            }
        } else if (event.kind == PointerEventKind3D::Move) {
            const auto capture = hit_(captured_, event.pointer);
            result.target = capture ? capture->item : tc_visual_item3d_handle_invalid();
            if (!valid_handle(result.target) && result.hit)
                result.target = result.hit->item;
            const auto target_hit = capture ? capture : result.hit;
            if (target_hit) {
                result.callback_failed |= dispatch_target_({TargetPointerEventKind3D::Move,
                                                            event,
                                                            target_hit->item,
                                                            target_hit->part,
                                                            result.hit,
                                                            capture.has_value()});
                if (state_revision_ != route_revision)
                    return result;
            }
        } else if (event.kind == PointerEventKind3D::Up) {
            const auto capture = hit_(captured_, event.pointer);
            result.target = capture ? capture->item : tc_visual_item3d_handle_invalid();
            if (!valid_handle(result.target) && result.hit)
                result.target = result.hit->item;
            const auto target_hit = capture ? capture : result.hit;
            const auto pressed = pressed_.find(event.pointer);
            if (pressed != pressed_.end() && result.hit && same_handle(pressed->second.item, result.hit->item) &&
                pressed->second.part == result.hit->part) {
                result.action = ActionEvent3D{pressed->second.item, event.pointer, pressed->second.part, "activate"};
            }
            pressed_.erase(event.pointer);
            captured_.erase(event.pointer);
            sequence_buttons_.erase(event.pointer);
            // Up is terminal before user code runs. A callback may replace
            // the scene, but that must not turn an already delivered Up into a
            // second terminal Cancel.
            if (target_hit) {
                result.callback_failed |= dispatch_target_({TargetPointerEventKind3D::Up,
                                                            event,
                                                            target_hit->item,
                                                            target_hit->part,
                                                            result.hit,
                                                            capture.has_value()});
                // The terminal Up owns the release even if the callback
                // attempts to revive the same sequence through capture() or a
                // nested Down.
                pressed_.erase(event.pointer);
                captured_.erase(event.pointer);
                sequence_buttons_.erase(event.pointer);
                if (state_revision_ != route_revision)
                    return result;
            }
        } else {
            const auto capture = hit_(captured_, event.pointer);
            const auto pressed = hit_(pressed_, event.pointer);
            const auto hover = hit_(hovered_, event.pointer);
            result.target = capture ? capture->item : tc_visual_item3d_handle_invalid();
            if (!valid_handle(result.target)) {
                result.target = pressed ? pressed->item : tc_visual_item3d_handle_invalid();
            }
            const auto target_hit = capture ? capture : pressed;
            // Cancel is terminal before either callback. Reentrant global
            // cancellation observes empty maps and cannot notify the same
            // owners recursively.
            hovered_.erase(event.pointer);
            pressed_.erase(event.pointer);
            captured_.erase(event.pointer);
            last_events_.erase(event.pointer);
            sequence_buttons_.erase(event.pointer);
            if (target_hit) {
                result.callback_failed |= dispatch_target_({TargetPointerEventKind3D::Cancel,
                                                            routed_event,
                                                            target_hit->item,
                                                            target_hit->part,
                                                            result.hit,
                                                            capture.has_value()});
                terminal_callback_invalidated_route = state_revision_ != route_revision;
            }
            if (hover) {
                result.callback_failed |= dispatch_target_(
                    {TargetPointerEventKind3D::Leave, routed_event, hover->item, hover->part, std::nullopt, false});
                terminal_callback_invalidated_route =
                    terminal_callback_invalidated_route || state_revision_ != route_revision;
            }
            // Terminal callbacks cannot reacquire this pointer into the just
            // cancelled sequence. Preserve other pointer ids.
            hovered_.erase(event.pointer);
            pressed_.erase(event.pointer);
            captured_.erase(event.pointer);
            last_events_.erase(event.pointer);
            sequence_buttons_.erase(event.pointer);
        }

        result.hovered = hit_handle_(hovered_, event.pointer);
        result.pressed = hit_handle_(pressed_, event.pointer);
        result.captured = hit_handle_(captured_, event.pointer);
        result.used_fallback = !valid_handle(result.target);
        if (terminal_callback_invalidated_route) {
            ++state_revision_;
            return result;
        }
        ActionHandler action_handler;
        if (result.action) {
            const auto* action_target = scene.resolve(result.action->target);
            if (action_target != nullptr && scene.effective_visible(*action_target) &&
                scene.effective_enabled(*action_target)) {
                const auto handler = action_handlers_.find(key_(result.action->target));
                if (handler != action_handlers_.end()) {
                    // Resolve the handler after Up. The Up callback may have
                    // torn down its controller and cleared/replaced the
                    // action handler; retaining the pre-Up callable would
                    // revive stale ownership and can dereference destroyed
                    // captures.
                    action_handler = handler->second;
                }
            }
        }
        if (result.action && action_handler) {
            try {
                action_handler(*result.action);
            } catch (const std::exception& error) {
                tc::Log::error("SceneInteraction3D action callback failed: %s", error.what());
                result.callback_failed = true;
            } catch (...) {
                tc::Log::error("SceneInteraction3D action callback failed with an unknown exception");
                result.callback_failed = true;
            }
            if (state_revision_ != route_revision)
                return result;
        }
        if (result.used_fallback && fallback_handler_) {
            // The fallback can replace/clear itself reentrantly.
            FallbackHandler fallback = fallback_handler_;
            try {
                fallback(routed_event);
            } catch (const std::exception& error) {
                tc::Log::error("SceneInteraction3D fallback callback failed: %s", error.what());
                result.callback_failed = true;
            } catch (...) {
                tc::Log::error("SceneInteraction3D fallback callback failed with an unknown exception");
                result.callback_failed = true;
            }
            if (event.kind != PointerEventKind3D::Cancel && state_revision_ != route_revision)
                return result;
        }
        if (event.kind == PointerEventKind3D::Cancel) {
            // A fallback Cancel is terminal too: nested routing or capture
            // from that callback cannot revive the cancelled pointer.
            hovered_.erase(event.pointer);
            pressed_.erase(event.pointer);
            captured_.erase(event.pointer);
            last_events_.erase(event.pointer);
            sequence_buttons_.erase(event.pointer);
            ++state_revision_;
        }
        return result;
    }

    bool SceneInteraction3D::capture(const TcVisualScene3D& scene,
                                     PointerId3D pointer,
                                     VisualItem3DHandle target,
                                     std::uint64_t part) {
        const auto* item = scene.resolve(target);
        if (item == nullptr || !scene.effective_visible(*item) || !scene.effective_enabled(*item)) {
            return false;
        }
        captured_[pointer] = HitResult3D{target, 0.0, part, {}, {}};
        return true;
    }

    void SceneInteraction3D::release(PointerId3D pointer) {
        captured_.erase(pointer);
    }

    void SceneInteraction3D::cancel_all() {
        ++state_revision_;
        hovered_.clear();
        pressed_.clear();
        captured_.clear();
        last_events_.clear();
        sequence_buttons_.clear();
    }

    bool SceneInteraction3D::cancel_all(const TcVisualScene3D& scene) {
        bool callback_failed = false;
        const auto events = last_events_;
        const auto hovered = hovered_;
        const auto pressed = pressed_;
        const auto captured = captured_;
        const auto sequence_buttons = sequence_buttons_;
        (void)scene;

        // Publish cancellation before invoking user code. A callback may
        // destroy the old borrowed scene or request another cancellation; it
        // must observe empty state and must not receive the same Cancel
        // recursively.
        cancel_all();
        for (const auto& [pointer, previous] : events) {
            const auto hovered_hit = hit_(hovered, pointer);
            const auto pressed_hit = hit_(pressed, pointer);
            const auto captured_hit = hit_(captured, pointer);
            const auto target_hit = captured_hit ? captured_hit : pressed_hit;
            if (!hovered_hit && !target_hit)
                continue;
            PointerEvent3D cancel = previous;
            cancel.kind = PointerEventKind3D::Cancel;
            const auto sequence_button = sequence_buttons.find(pointer);
            if (sequence_button != sequence_buttons.end())
                cancel.button = sequence_button->second;
            if (target_hit) {
                callback_failed |= dispatch_target_({TargetPointerEventKind3D::Cancel,
                                                     cancel,
                                                     target_hit->item,
                                                     target_hit->part,
                                                     std::nullopt,
                                                     captured_hit.has_value()});
            }
            if (hovered_hit) {
                callback_failed |= dispatch_target_({TargetPointerEventKind3D::Leave,
                                                     cancel,
                                                     hovered_hit->item,
                                                     hovered_hit->part,
                                                     std::nullopt,
                                                     false});
            }
        }
        // A terminal callback may route a nested Down or call capture(). The
        // global cancellation postcondition still requires completely empty
        // interaction state when this function returns.
        cancel_all();
        return callback_failed;
    }

    void SceneInteraction3D::set_target_pointer_handler(VisualItem3DHandle item, TargetPointerHandler handler) {
        if (handler)
            target_pointer_handlers_[key_(item)] = std::move(handler);
        else
            target_pointer_handlers_.erase(key_(item));
    }

    void SceneInteraction3D::clear_target_pointer_handler(VisualItem3DHandle item) {
        target_pointer_handlers_.erase(key_(item));
    }

    void SceneInteraction3D::set_action_handler(VisualItem3DHandle item, ActionHandler handler) {
        if (handler) {
            action_handlers_[key_(item)] = std::move(handler);
        } else {
            action_handlers_.erase(key_(item));
        }
    }

    void SceneInteraction3D::clear_action_handler(VisualItem3DHandle item) {
        action_handlers_.erase(key_(item));
    }

    void SceneInteraction3D::set_fallback_handler(FallbackHandler handler) {
        fallback_handler_ = std::move(handler);
    }

    VisualItem3DHandle SceneInteraction3D::hovered(PointerId3D pointer) const {
        return hit_handle_(hovered_, pointer);
    }

    VisualItem3DHandle SceneInteraction3D::pressed(PointerId3D pointer) const {
        return hit_handle_(pressed_, pointer);
    }

    VisualItem3DHandle SceneInteraction3D::captured(PointerId3D pointer) const {
        return hit_handle_(captured_, pointer);
    }

    std::optional<HitResult3D> SceneInteraction3D::hovered_hit(PointerId3D pointer) const {
        return hit_(hovered_, pointer);
    }

    std::optional<HitResult3D> SceneInteraction3D::pressed_hit(PointerId3D pointer) const {
        return hit_(pressed_, pointer);
    }

    std::optional<HitResult3D> SceneInteraction3D::captured_hit(PointerId3D pointer) const {
        return hit_(captured_, pointer);
    }

} // namespace termin::visual
