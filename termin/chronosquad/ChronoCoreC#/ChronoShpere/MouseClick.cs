using System.Collections;
using System.Collections.Generic;

#if UNITY_64 || UNITY_EDITOR
using UnityEngine;
using Unity.AI.Navigation;
using UnityEngine.AI;
#endif

public class MouseClick : MonoBehaviour
{
    float _last_click_time = 0;
    TimelineGraph _timeline_graph;

    float last_update_time = 0;

    float start_right_click_time = 0;
    public bool right_click = false;

    VerticalNavigation _vertical_navigation = null;

    void Start()
    {
        _vertical_navigation = GameObject.FindFirstObjectByType<VerticalNavigation>();
        _last_click_time = Time.time;
        _timeline_graph = GameObject.Find("TimelineGraphCamera")?.GetComponent<TimelineGraph>();
    }

    bool UiClickCheck(Vector2 mouse_position)
    {
        UserInterfaceCanvas ui = GameObject
            .Find("ChronoSphereInterface")
            .GetComponent<UserInterfaceCanvas>();

        return ui.Click(mouse_position);
    }

    bool UICheck(Vector2 mouse_position)
    {
        return UiClickCheck(Input.mousePosition);
    }

    // void RightButtonLong(Vector2 mouse_position)
    // {
    // 	RaycastHit hit = Raycast(Input.mousePosition);
    // 	if (hit.collider == null)
    // 		return;

    // 	var obj = hit.collider.gameObject;
    // 	var layer = obj.layer;
    // 	var pos = hit.point;

    // 	if (layer == 6 || layer == 0) // Клик на землю или препятствие. Укрытия игнорируются.
    // 		ViewMarker.Instance.Attach(pos);
    // }

    RaycastHit Raycast(Vector2 mouse_position)
    {
        return GameCore.CursorEnvironmentHit(mouse_position, add_ui_layer: true);
    }

    void LeftButton(Vector2 mouse_position, bool double_click)
    {
        RaycastHit envhit = new RaycastHit();
        RaycastHit acthit = new RaycastHit();
        var hit = GameCore.CursorEnvironmentHit(
            mouse_position,
            ref envhit,
            ref acthit,
            add_ui_layer: true
        );
        if (hit.collider == null)
            return;

        var obj = hit.collider.gameObject;
        var layer = obj.layer;
        var pos = hit.point;

        ClickInformation clickInformation = new ClickInformation(
            actor_hit: acthit,
            environment_hit: envhit,
            actor_position: acthit.point,
            environment_position: envhit.point,
            double_click: double_click
        );

        if (layer == 6 || layer == 0 || layer == 10 || layer == 26) // Клик на землю или препятствие. Укрытия игнорируются.
            GameCore.environment_click(pos, clickInformation);
        else if (layer == (int)Layers.PROMISE_OBJECT_LAYER) // Клик на обещание.
            GameCore.promise_click(pos, obj);
        else if (
            layer == (int)Layers.ACTOR_LAYER || layer == (int)Layers.ACTOR_NON_TRANSPARENT_LAYER
        ) // Клик на персонажа.
            GameCore.left_click_on_actor(clickInformation);
        // else if (layer == (int)Layers.NAVMESH_LINK_COLLIDER_LAYER)
        // 	GameCore.navmeshlink_click(pos, double_click, obj);
        else if (layer == 21) // climbing collider
            GameCore.climbing_block_click(pos, double_click, obj, clickInformation);
        else if (layer == (int)Layers.CORNER_LEAN_LAYER)
            GameCore.corner_lean_click(pos, double_click, obj, clickInformation);
        else if (layer == (int)Layers.UI_LAYER) // ui
            GameCore.ui_click(pos, obj);
    }

    void RightButton(Vector2 mouse_position)
    {
        start_right_click_time = Time.time;
        right_click = true;

        RaycastHit hit = Raycast(Input.mousePosition);
        if (hit.collider == null)
            return;

        if (GameCore.HasActiveAction())
        {
            GameCore.CancelActiveAction();
            return;
        }

        var obj = hit.collider.gameObject;
        var layer = obj.layer;
        var pos = hit.point;

        if (layer == 6 || layer == 0) // Клик на землю или препятствие. Укрытия игнорируются.
            GameCore.right_environment_click(pos, false, obj);
        else if (layer == (int)Layers.ACTOR_LAYER)
        {
            var collider = hit.collider.gameObject;
            var actor = collider.transform.parent.gameObject;
            GameCore.right_click_on_actor(actor);
        }
        else if (layer == 5) // ui
            GameCore.ui_click(pos, obj);
        else if (layer == (int)Layers.EDITOR_LAYER)
            GameCore.editor_object_click(pos, obj);
    }

    void LongRightDown()
    {
        ViewMarker.Instance.Dettach();
    }

    // on gui event
    void OnGUI()
    {
        if (_timeline_graph != null)
        {
            bool in_timeline_graph = _timeline_graph.IsCursorInViewport();
            if (in_timeline_graph)
            {
                return;
            }
        }

        if (Event.current.type == EventType.KeyDown)
        {
            if (Event.current.keyCode == KeyCode.Z)
            {
                var camera = Camera.main;
                var cullingMask = camera.cullingMask;
                camera.cullingMask = cullingMask | 1 << 26;
            }
        }

        if (Event.current.type == EventType.KeyUp)
        {
            if (Event.current.keyCode == KeyCode.Z)
            {
                var camera = Camera.main;
                var cullingMask = camera.cullingMask;
                camera.cullingMask = cullingMask & ~(1 << 26);
            }
        }

        // if (Event.current.type == EventType.MouseDown)
        // {
        // 	if (UICheck(Input.mousePosition))
        // 		return;

        // 	if (Event.current.button  == 0)
        // 	{
        // 		GameCore.LeftButtonMark();
        // 	}
        // }

        if (Event.current.type == EventType.MouseDown)
        {
            if (UICheck(Input.mousePosition))
                return;

            if (Event.current.button == 0)
            {
                if (_last_click_time + 0.3f > Time.time)
                {
                    LeftButton(Input.mousePosition, true);
                    _last_click_time = Time.time;
                    return;
                }

                LeftButton(Input.mousePosition, false);
                _last_click_time = Time.time;
                return;
            }

            if (Event.current.button == 1)
            {
                RightButton(Input.mousePosition);
                return;
            }
        }

        if (Event.current.type == EventType.MouseUp)
        {
            if (Event.current.button == 1)
            {
                right_click = false;

                if (start_right_click_time + 0.5f < Time.time)
                {
                    //RightButtonLong( Input.mousePosition );
                }
            }
        }

        // if mouse moved
        // if (Event.current.type == EventType.MouseMove)
        // {
        // 	UpdateHover();
        // }
    }

    void Update()
    {
        if (right_click)
        {
            var rctime = Time.time - start_right_click_time;
            if (rctime > 1.0f)
            {
                right_click = false;
                LongRightDown();
            }
        }

        // if (Time.time - last_update_time > 0.1f)
        // {
        UpdateHover();
        last_update_time = Time.time;
        // }
    }

    void UpdateHover()
    {
        // mouse position in 0..1
        var mouse_pos = Input.mousePosition / new Vector2(Screen.width, Screen.height);
        Shader.SetGlobalVector("_MousePosition", mouse_pos);

        // int layerMask =
        // 	1 << 6 |
        // 	1 << (int)Layers.ACTOR_LAYER |
        // 	1 << (int)Layers.ACTOR_NON_TRANSPARENT_LAYER |
        // 	1 << 21 |
        // 	1 << 24 |
        // 	1 << (int)Layers.CORNER_LEAN_LAYER |
        // 	1 << 0 |
        // 	1 << 10 |
        // 	1 << (int)Layers.NAVMESH_LINK_COLLIDER_LAYER |
        // 	1 << LayerMask.NameToLayer("BracedCollider");

        // var ray = CreateRay(Input.mousePosition);
        RaycastHit hit = Raycast(Input.mousePosition);

        bool hovered_actor = false;
        if (hit.collider != null)
        {
            var obj = hit.collider.gameObject;
            var layer = obj.layer;
            var pos = hit.point;

            // if (layer == (int)Layers.NAVMESH_LINK_COLLIDER_LAYER)
            // {
            // 	GameCore.navmeshlink_hover(pos, obj);
            // }
            if (layer == 6 || layer == 0 || layer == 10)
            {
                GameCore.environment_hover(pos, obj);
            }
            else if (layer == 21) // climbing collider
            {
                GameCore.climbing_block_hover(pos, obj);
            }
            else if (layer == (int)Layers.CORNER_LEAN_LAYER) // climbing collider
            {
                GameCore.corner_lean_hover(pos, obj);
            }
            else if (layer == 24) // climbing collider
            {
                GameCore.climbing_surface_hover(pos, obj);
            }
            else if (layer == (int)Layers.ACTOR_LAYER) // actor
            {
                GameCore.hover_actor(obj, layer);
                hovered_actor = true;
            }
            else if (layer == (int)Layers.ACTOR_NON_TRANSPARENT_LAYER)
            {
                GameCore.hover_actor(obj, layer);
                hovered_actor = true;
            }
            else
            {
                GameCore.hover_unkown(obj, layer);
            }

            if (layer != 21 && layer != (int)Layers.CORNER_LEAN_LAYER)
            {
                GameCore.climbing_block_hover(Vector3.zero, null);
            }
        }
        else
        {
            GameCore.hover_unkown(null, -1);
            GameCore.climbing_block_hover(Vector3.zero, null);
        }

        if (!hovered_actor)
            GameCore.hover_actor(null, 0);
    }
}

public struct ClickInformation
{
    public RaycastHit actor_hit;
    public RaycastHit environment_hit;
    public Vector3 actor_position;
    public Vector3 environment_position;
    public bool double_click;

    public ClickInformation(
        RaycastHit actor_hit,
        RaycastHit environment_hit,
        Vector3 actor_position,
        Vector3 environment_position,
        bool double_click
    )
    {
        this.actor_hit = actor_hit;
        this.environment_hit = environment_hit;
        this.actor_position = actor_position;
        this.environment_position = environment_position;
        this.double_click = double_click;
    }
}
