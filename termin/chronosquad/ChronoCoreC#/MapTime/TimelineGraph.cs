using System.Collections.Generic;
using System.Linq;
using System;

// using pool
#if UNITY_64
using UnityEngine;
using UnityEngine.Pool;
#endif

public struct TTV
{
    public TimelineGraphDraw t;
    public Vector2 v;

    public TTV(TimelineGraphDraw t, Vector2 v)
    {
        this.t = t;
        this.v = v;
    }
}

public class TimelineGraph : MonoBehaviour
{
    Camera cam;

    public float TopLevel = 100;

    public Material backgoundmat;

    ChronoSphere _chronosphere;

    TimelineGraphBackground timelineGraphBackground;

    TimelineCursor timelineCursor;

    bool _last_is_cursor_in_viewport = false;

    bool _last_right_button_pressed = false;

    bool _last_left_button_pressed = false;

    float aspect_ratio = 1.0f;

    float current_maximize_coef = 0;
    float target_maximize_coef = 0;
    bool _timeline_map_maximized = false;

    //Vector2 _right_click_down_position;

    GameObject _timeline_map_object;

    float camera_zoom = 1.0f;

    SimpleFilter filter;

    Dictionary<string, TimelineGraphDraw> _timeline_graph_draws =
        new Dictionary<string, TimelineGraphDraw>();

    public void CameraMove(Vector3 delta)
    {
        cam.transform.position += delta;
    }

    public void CameraZoom(float delta)
    {
        Debug.Log("CameraZoom" + camera_zoom);
        if (delta > 0)
        {
            camera_zoom *= 1.1f;
        }
        else
        {
            camera_zoom *= 0.9f;
        }
        UpdateProjectionMatrix();
    }

    public TTV FindNearestGraph(Vector2 pnt)
    {
        float min_distance = float.MaxValue;
        Vector2 nearest = new Vector2();
        TimelineGraphDraw resgraph = null;
        foreach (var graph in _timeline_graph_draws.Values)
        {
            var distance = graph.DistanceToMainArrow(pnt);
            if (distance < min_distance)
            {
                min_distance = distance;
                nearest = graph.FindNearestMainPoint(pnt);
                resgraph = graph;
            }
        }
        return new TTV(resgraph, nearest);
    }

    public void SetChronosphere(ChronoSphere chronosphere)
    {
        _chronosphere = chronosphere;
    }

    public Dictionary<string, TimelineGraphDraw> TimelineDraws
    {
        get { return _timeline_graph_draws; }
    }

    public TimelineGraph() { }

    public void Init(GameObject canvas)
    {
        timelineGraphBackground = new TimelineGraphBackground(canvas.transform, backgoundmat);
    }

    void MakeTimelineCursor()
    {
        var go = new GameObject("TimelineCursor");
        timelineCursor = go.AddComponent<TimelineCursor>();
        go.layer = 15;
    }

    void Start()
    {
        MakeTimelineCursor();

        transform.position = new Vector3(0, 0, 0);
        var r = this.GetComponentInChildren<Canvas>();

        _timeline_map_object = new GameObject("TimelineMap");
        _timeline_map_object.layer = 15;
        cam = this.GetComponent<Camera>();
        _timeline_map_object.transform.position = new Vector3(0, 0, 0);

        filter = gameObject.GetComponent<SimpleFilter>();
        _chronosphere = GameObject
            .Find("Timelines")
            .GetComponent<ChronosphereController>()
            .Chronosphere();

        aspect_ratio = (float)Screen.width / (float)Screen.height;
        UpdateViewPort();

        Init(_timeline_map_object);

        UpdateTimelineDrawsObject(_timeline_map_object);

        cam.orthographic = true;
        //cam.orthographicSize = camera_zoom;

        UpdateProjectionMatrix();
    }

    public void UpdateProjectionMatrix()
    {
        cam.projectionMatrix = Matrix4x4.Ortho(
            -1000 * aspect_ratio * camera_zoom,
            1000 * aspect_ratio * camera_zoom,
            -1000 * camera_zoom,
            1000 * camera_zoom,
            -1000,
            1000
        );
    }

    public void UpdateTimelineDrawsObject(GameObject canvas)
    {
        foreach (var ktl in _chronosphere.Timelines())
        {
            var key = ktl.Key;
            var tl = ktl.Value;

            if (!_timeline_graph_draws.ContainsKey(key))
            {
                _timeline_graph_draws[key] = new TimelineGraphDraw(tl, canvas, this);
            }
        }
    }

    Rect CurrentCameraRect()
    {
        var width = Screen.width;
        var height = Screen.height;

        var camera_center = cam.transform.position;

        var camera_size = cam.orthographicSize;

        Vector2 left_top = new Vector2(
            camera_center.x - camera_size * aspect_ratio,
            camera_center.y + camera_size
        );

        Vector2 right_bottom = new Vector2(
            camera_center.x + camera_size * aspect_ratio,
            camera_center.y - camera_size
        );

        return new Rect(
            left_top.x,
            left_top.y,
            right_bottom.x - left_top.x,
            left_top.y - right_bottom.y
        );
    }

    public void UpdateTimelineDrawsCoordinates()
    {
        int i = 0;
        foreach (var graph in _timeline_graph_draws.Values)
        {
            graph.SetLevel(TopLevel + 100 * i);
            i += 1;
        }

        foreach (var graph in _timeline_graph_draws.Values)
        {
            graph.UpdateCoordinates();
        }
    }

    public int CountOfLines()
    {
        return _timeline_graph_draws.Count;
    }

    void Update()
    {
        UpdateTimelineDrawsObject(_timeline_map_object);
        UpdateTimelineDrawsCoordinates();

        if (current_maximize_coef != target_maximize_coef)
        {
            UpdateViewPort();
        }

        Vector3 cursor_position = Input.mousePosition;
        bool is_cursor_in_viewport = IsCursorInViewport();
        if (is_cursor_in_viewport)
        {
            bool right_button_pressed = Input.GetMouseButtonDown(1);
            bool left_button_pressed = Input.GetMouseButtonDown(0);

            _last_left_button_pressed = left_button_pressed;
            _last_right_button_pressed = right_button_pressed;

            // raycast to vertical plane
            Ray ray = cam.ScreenPointToRay(Input.mousePosition);
            var origin = ray.origin;
        }

        _last_is_cursor_in_viewport = is_cursor_in_viewport;

        // mouse wheel

        var world_position = CursorTo2dWorldPosition(cursor_position);
        var nearest = FindNearestGraph(world_position);
        var nearest_as_world = new Vector3(nearest.v.x, nearest.v.y, 0);
        timelineCursor.SetPosition(nearest_as_world);
    }

    Vector2 CursorTo2dWorldPosition(Vector2 cursor_position)
    {
        Ray ray = cam.ScreenPointToRay(cursor_position);
        Plane plane = new Plane(Vector3.forward, Vector3.zero);
        float enter = 0.0f;
        if (!plane.Raycast(ray, out enter))
        {
            return new Vector2();
        }
        var ret = ray.GetPoint(enter);
        return new Vector2(ret.x, ret.y);
    }

    Vector2 CursorTo2dWorldPosition(Vector3 cursor_position)
    {
        return CursorTo2dWorldPosition(new Vector2(cursor_position.x, cursor_position.y));
    }

    // void OnGUI()
    // {
    // 	return;

    // 	if (!IsCursorInViewport())
    // 		return;

    // 	Event e = Event.current;

    // 	if (e.type == EventType.ScrollWheel)
    // 	{
    // 		CameraZoom(e.delta.y);
    // 	}

    // 	if (e.type == EventType.MouseDown)
    // 	{
    // 		Vector3 cursor_position = Input.mousePosition;
    // 		Vector2 world_position = CursorTo2dWorldPosition(cursor_position);
    // 		if (e.button == 0) { }
    // 		else if (e.button == 1)
    // 		{
    // 			_right_click_down_position = world_position;
    // 		}

    // 		if (e.button == 0)
    // 		{
    // 			OnTimeGraphClick();
    // 		}
    // 	}

    // 	if (e.type == EventType.MouseDrag)
    // 	{
    // 		Vector3 cursor_position = Input.mousePosition;
    // 		Vector2 world_position = CursorTo2dWorldPosition(cursor_position);
    // 		if (e.button == 0)
    // 		{
    // 			OnTimeGraphClick();
    // 		}
    // 		else if (e.button == 1)
    // 		{
    // 			var delta = world_position - _right_click_down_position;
    // 			CameraMove(new Vector3(-delta.x, -delta.y, 0));
    // 		}
    // 	}

    // 	if (e.type == EventType.KeyDown)
    // 	{
    // 		if (e.keyCode == KeyCode.J)
    // 		{
    // 			MaximizeSwap();
    // 		}
    // 	}

    // 	if (e.type == EventType.KeyDown)
    // 	{
    // 		if (e.keyCode == KeyCode.Space)
    // 		{
    // 			GameCore.on_space_pressed();
    // 		}
    // 	}
    // }

    void OnTimeGraphClick()
    {
        Vector3 cursor_position = Input.mousePosition;
        Vector2 world_position = CursorTo2dWorldPosition(
            new Vector2(cursor_position.x, cursor_position.y)
        );
        var nearest = FindNearestGraph(world_position);
        var graph = nearest.t;
        var point = nearest.v;
        if (graph != null)
        {
            graph.OnClick(point);
        }
    }

    void UpdateViewPort()
    {
        current_maximize_coef +=
            (target_maximize_coef - current_maximize_coef) * 0.3f * Time.deltaTime * 60;
        MaximizeImpl(current_maximize_coef);
    }

    Rect RectLerp(Rect a, Rect b, float t)
    {
        return new Rect(
            a.x + (b.x - a.x) * t,
            a.y + (b.y - a.y) * t,
            a.width + (b.width - a.width) * t,
            a.height + (b.height - a.height) * t
        );
    }

    void MaximizeImpl(float coeff)
    {
        var rectmin = new Rect(0.85f, 0.85f, 0.15f, 0.15f);
        var rectmax = new Rect(0.1f, 0.1f, 0.8f, 0.8f);
        cam.rect = RectLerp(rectmin, rectmax, coeff);
    }

    void Maximize(bool timeline_map_maximized)
    {
        _timeline_map_maximized = timeline_map_maximized;
        if (_timeline_map_maximized)
        {
            target_maximize_coef = 1;
            //filter.enabled = true;
        }
        else
        {
            target_maximize_coef = 0;
            //filter.enabled = false;
        }
    }

    public void MaximizeSwap()
    {
        _timeline_map_maximized = !_timeline_map_maximized;
        Maximize(_timeline_map_maximized);
    }

    public bool IsCursorInViewport()
    {
        var pnt = Input.mousePosition;
        var rect = cam.rect;

        var width = Screen.width;
        var height = Screen.height;

        var x = pnt.x / width;
        var y = pnt.y / height;

        return rect.Contains(new Vector2(x, y));
    }
}
