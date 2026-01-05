using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public struct ObjectLevelPair
{
    public GameObject obj;
    public int level;
}

[ExecuteAlways]
public class VerticalNavigation : MonoBehaviour
{
    static VerticalNavigation _instance = null;
    GameObject sphereMarker;
    GameObject planeMarker;
    public static VerticalNavigation Instance
    {
        get { return _instance; }
    }

    void Awake()
    {
        _instance = this;
        SectionNormal.Normalize();
    }

    void Start()
    {
        if (Application.isEditor && !Application.isPlaying) { }
        else
        {
            sphereMarker = GameObject.CreatePrimitive(PrimitiveType.Sphere);
            var material = MaterialKeeper.Instance.GetMaterial("HalfWorldMarker");
            sphereMarker.GetComponent<Renderer>().material = material;
            sphereMarker.layer = (int)Layers.EFFECTS_LAYER;

            planeMarker = GameObject.CreatePrimitive(PrimitiveType.Plane);
            var plane_material = MaterialKeeper.Instance.GetMaterial("HalfWorldPlane");
            planeMarker.GetComponent<Renderer>().material = plane_material;
            planeMarker.transform.localScale = new Vector3(20, 1, 20);
            planeMarker.layer = (int)Layers.EFFECTS_LAYER;
        }
    }

    public float VertScrollSpeed = 0.5f;
    float VertScrollTimeConstant = 0.2f;

    public float ShewedFloatLevelTarget = 20.0f;
    public float ShewedFloatLevelCursor = 20.0f;

    Vector3 SectionNormal = new Vector3(0.0f, 1, 0.0f);

    public MyList<float> _levels = new MyList<float>();

    //int CurrentLevel = 0;


    public float GetCurrentVerticalLevel()
    {
        return ShewedFloatLevelCursor;
    }

    void GetAllObjectsInCurrentIerarchyRecursive(GameObject root, MyList<ObjectLevelPair> accum)
    {
        foreach (Transform child in root.transform)
        {
            // non actor
            if (child.gameObject.layer == 11)
                continue;

            GetAllObjectsInCurrentIerarchyRecursive(child.gameObject, accum);
        }
    }

    Vector3 RayAndSectionIntersection(Ray ray)
    {
        var origin = ray.origin;
        var direction = ray.direction;
        var normal = SectionNormal;

        var origin_level = Vector3.Dot(origin, normal);
        var level_diff = origin_level - ShewedFloatLevelCursor;
        var direction_project = -Vector3.Dot(direction, normal);
        var mulled_level = level_diff / direction_project;
        return origin + mulled_level * direction;
    }

    // static public float VerticalStart()
    // {
    // 	var _vertical_navigation = VerticalNavigation.Instance;
    // 	if (_vertical_navigation == null)
    // 		return Camera.main.transform.position.y;
    // 	return _vertical_navigation.GetCurrentVerticalLevel();
    // }

    public Ray RayForEnvironment(Vector2 mouse_position)
    {
        var ray = Camera.main.ScreenPointToRay(mouse_position);
        var origin = RayAndSectionIntersection(ray);
        ray.origin = origin;
        //Debug.Log("RayForEnvironment: " + ray.origin + " " + ray.direction);
        return ray;
    }

    void Update()
    {
        if (Application.isEditor && !Application.isPlaying) { }
        else
        {
            if (Input.GetKey(KeyCode.LeftControl))
            {
                planeMarker.SetActive(true);
                sphereMarker.SetActive(true);

                if (Input.GetAxis("Mouse ScrollWheel") > 0)
                {
                    IncrementFloatLevel();
                }
                else if (Input.GetAxis("Mouse ScrollWheel") < 0)
                {
                    DecrementFloatLevel();
                }
            }
            else
            {
                planeMarker.SetActive(false);
                sphereMarker.SetActive(false);
            }

            //ShowLevel(ShewedLevel);

            // if invoked in editor mode

            UpdateFloatCursor();
        }
        SendFloatLevel();
    }

    void UpdatePlaneRotation()
    {
        planeMarker.transform.rotation = Quaternion.FromToRotation(Vector3.up, SectionNormal);
    }

    void SetMarkerPosition(Vector3 pos)
    {
        sphereMarker.transform.position = pos;
        planeMarker.transform.position = pos;
        ShewedFloatLevelTarget = Vector3.Dot(pos, SectionNormal);
        SendFloatLevel();
        UpdatePlaneRotation();
    }

    void OnGUI()
    {
        // if mouse click while left control is pressed
        // if (Input.GetKey(KeyCode.LeftControl) && Input.GetMouseButtonDown(0))
        // {
        // 	// place marker
        // 	Vector3 mouse_pos = Input.mousePosition;
        // 	var hit = GameCore.CursorEnvironmentHit(mouse_pos);
        // 	SetMarkerPosition(hit.point);
        // }

        // on mouse move
        if (Input.GetAxis("Mouse X") != 0 || Input.GetAxis("Mouse Y") != 0)
        {
            if (Input.GetKey(KeyCode.LeftControl) && Input.GetKey(KeyCode.LeftAlt))
            {
                float sens = 1.0f;
                // rotate section normal
                var xaxis = Camera.main.transform.forward;
                var yaxis = Camera.main.transform.right;
                var xaxis_proj = Vector3.ProjectOnPlane(xaxis, new Vector3(0, 1, 0));
                var yaxis_proj = Vector3.ProjectOnPlane(yaxis, new Vector3(0, 1, 0));
                var xquat = Quaternion.AngleAxis(-Input.GetAxis("Mouse X") * sens, xaxis_proj);
                var yquat = Quaternion.AngleAxis(Input.GetAxis("Mouse Y") * sens, yaxis_proj);
                SectionNormal = xquat * yquat * SectionNormal;
                //SectionNormal = Quaternion.AngleAxis(Input.GetAxis("Mouse X") * sens, Vector3.forward) * SectionNormal;
                //SectionNormal = Quaternion.AngleAxis(Input.GetAxis("Mouse Y") * sens, Vector3.right) * SectionNormal;
                SectionNormal.Normalize();

                // update level
                var marker_pos = sphereMarker.transform.position;
                var marker_level = Vector3.Dot(marker_pos, SectionNormal);
                ShewedFloatLevelTarget = marker_level;
                ShewedFloatLevelCursor = marker_level;
                UpdatePlaneRotation();
            }
        }
    }

    public void UpdateMarkerPositionByLevel()
    {
        var marker_level = Vector3.Dot(sphereMarker.transform.position, SectionNormal);
        var level_diff = ShewedFloatLevelTarget - marker_level;
        SetMarkerPosition(sphereMarker.transform.position + level_diff * SectionNormal);
    }

    void IncrementFloatLevel()
    {
        ShewedFloatLevelTarget += VertScrollSpeed;
        UpdateMarkerPositionByLevel();
        // CurrentLevel--;
        // if (CurrentLevel < 0)
        // 	CurrentLevel = 0;
        // ShewedFloatLevelTarget = _levels[CurrentLevel];
    }

    void DecrementFloatLevel()
    {
        ShewedFloatLevelTarget -= VertScrollSpeed;
        UpdateMarkerPositionByLevel();
        // CurrentLevel++;
        // if (CurrentLevel >= _levels.Count)
        // 	CurrentLevel = _levels.Count - 1;
        // ShewedFloatLevelTarget = _levels[CurrentLevel];
    }

    void UpdateFloatCursor()
    {
        ShewedFloatLevelCursor +=
            (ShewedFloatLevelTarget - ShewedFloatLevelCursor)
            * Time.deltaTime
            / VertScrollTimeConstant;
    }

    void SendFloatLevel()
    {
        Shader.SetGlobalVector("_SectionCoords", SectionNormal);
        Shader.SetGlobalFloat("ShewedFloatLevel", ShewedFloatLevelCursor);
    }
}
