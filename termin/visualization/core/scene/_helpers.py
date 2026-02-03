"""Helper functions for Scene operations.

These functions provide Python-specific functionality that cannot be
efficiently implemented in C++, such as searching by Python type.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, List, Type, TypeVar

if TYPE_CHECKING:
    from termin._native.scene import TcScene
    from termin.visualization.core.component import Component, InputComponent

T = TypeVar("T", bound="Component")


def find_component(scene: "TcScene", component_type: Type[T]) -> T | None:
    """Find first component of given type in scene.

    Args:
        scene: The scene to search in.
        component_type: Component class to search for.

    Returns:
        First matching component or None.
    """
    type_name = component_type.__name__
    components = scene.get_components_of_type(type_name)
    return components[0] if components else None


def find_components(scene: "TcScene", component_type: Type[T]) -> List[T]:
    """Find all components of given type in scene.

    Args:
        scene: The scene to search in.
        component_type: Component class to search for.

    Returns:
        List of all matching components.
    """
    type_name = component_type.__name__
    return scene.get_components_of_type(type_name)


def dispatch_input(
    scene: "TcScene",
    event_name: str,
    event,
    filter_fn: Callable[["InputComponent"], bool] | None = None,
) -> None:
    """Dispatch input event to InputComponents.

    Args:
        scene: The scene to dispatch to.
        event_name: Name of the handler method (e.g., "on_mouse_button").
        event: Event object to dispatch.
        filter_fn: Optional filter function. If provided, only components
                   for which filter_fn(component) returns True receive the event.

    Note: For best performance without filter_fn, use the specific dispatch methods
    on the scene (dispatch_mouse_button, dispatch_mouse_move, dispatch_scroll, dispatch_key).
    """
    # Fast path: use C-level dispatch when no filter is needed
    if filter_fn is None:
        if event_name == "on_mouse_button":
            scene.dispatch_mouse_button(event)
        elif event_name == "on_mouse_move":
            scene.dispatch_mouse_move(event)
        elif event_name == "on_scroll":
            scene.dispatch_scroll(event)
        elif event_name == "on_key":
            scene.dispatch_key(event)
        return

    # Slow path with filter: iterate components and call methods
    from termin._native import log

    def dispatch_to_component(component):
        if not filter_fn(component):
            return True
        handler = getattr(component, event_name, None)
        if handler:
            try:
                handler(event)
            except Exception as e:
                log.error(f"Error in input handler '{event_name}' of component '{component}': {e}")
        return True

    scene.foreach_component_of_type("InputComponent", dispatch_to_component)
