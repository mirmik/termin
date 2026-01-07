
import traceback

try:
    import termin.chronosquad.controllers.timeline_initializer
except ImportError as e:
    print("[Project InitScript] ChronoSquad controllers not found, skipping initialization: ", e)
    traceback.print_exc()    

try:
    import termin.chronosquad.controllers.object_controller
except ImportError as e:
    print("[Project InitScript] ChronoSquad ObjectController not found, skipping initialization: ", e)
    traceback.print_exc()    

try:    
    import termin.chronosquad.controllers.chronosphere_controller
except ImportError as e:
    print("[Project InitScript] ChronoSquad ChronosphereController not found, skipping initialization: ", e)
    traceback.print_exc()    

try:
    import termin.chronosquad.controllers.timeline_controller
except ImportError as e:
    print("[Project InitScript] ChronoSquad TimelineController not found, skipping initialization: ", e)
    traceback.print_exc()    
    
try:
    import termin.chronosquad.controllers.click_controller
except ImportError as e:
    print("[Project InitScript] ChronoSquad ClickController not found, skipping initialization: ", e)
    traceback.print_exc()    

try:
    import termin.chronosquad.controllers.game_controller
except ImportError as e:
    print("[Project InitScript] ChronoSquad GameController not found, skipping initialization: ", e)
    traceback.print_exc()    

try:
    import termin.chronosquad.controllers.action_server_component
except ImportError as e:
    print("[Project InitScript] ChronoSquad ActionServerComponent not found, skipping initialization: ", e)
    traceback.print_exc()    

try:
    import termin.chronosquad.controllers.action.blink_action_component
except ImportError as e:
    print("[Project InitScript] ChronoSquad BlinkActionComponent not found, skipping initialization: ", e)
    traceback.print_exc()    

try:
    import termin.chronosquad.controllers.animation_controller
except ImportError as e:
    print("[Project InitScript] ChronoSquad AnimationController not found, skipping initialization: ", e)
    traceback.print_exc()    

try:
    import termin.chronosquad.colliders.human_model_collider
except ImportError as e:
    print("[Project InitScript] ChronoSquad HumanModelCollider not found, skipping initialization: ", e)
    traceback.print_exc()    

# Install ChronoSquad menu
from termin.chronosquad.editor import install_menu
install_menu()