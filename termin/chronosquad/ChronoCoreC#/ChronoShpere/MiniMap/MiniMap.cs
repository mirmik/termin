#if UNITY_64
using UnityEngine;
#endif

using System;
using System.Collections.Generic;

public class MiniMap : MonoBehaviour
{
    Camera cam;
    Camera main_camera;

    GameObject _minimap_camera_projection_object;
    LineRenderer _minimap_camera_projection_line;

    RenderTexture _minimap_texture;

    GameObject MiniMapPlane;
    Material MiniMapMaterial;

    Vector3 _last_camera_position;
    Quaternion _last_camera_rotation;

    bool _inited = false;

    void Start()
    {
        _minimap_camera_projection_object = new GameObject("MinimapCameraProjection");
        _minimap_camera_projection_object.layer = LayerMask.NameToLayer("MiniMapCountour");
        _minimap_camera_projection_object.transform.parent = transform;
        _minimap_camera_projection_line =
            _minimap_camera_projection_object.AddComponent<LineRenderer>();

        MiniMapPlane = GameObject.CreatePrimitive(PrimitiveType.Plane);

        // no shadow
        MiniMapPlane.GetComponent<Renderer>().shadowCastingMode = UnityEngine
            .Rendering
            .ShadowCastingMode
            .Off;

        MiniMapMaterial = MiniMapPlane.GetComponent<Renderer>().material;

        cam = GetComponent<Camera>();

        // disable depth texture rendering
        cam.depthTextureMode = DepthTextureMode.None;
        main_camera = Camera.main;
    }

    void SetMinimapMode()
    {
        // set layer mask
        cam.cullingMask =
            1 << LayerMask.NameToLayer("MiniMap") | 1 << LayerMask.NameToLayer("MiniMapCountour");

        MiniMapMaterial.SetTexture("_MainTex", _minimap_texture);

        // растянуть изображение на плоскости


        MiniMapPlane.transform.position = cam.transform.position + cam.transform.forward * 2;

        MiniMapPlane.transform.localScale = new Vector3(
            cam.orthographicSize * cam.aspect / 5,
            1,
            cam.orthographicSize / 5
        );

        MiniMapPlane.transform.rotation =
            cam.transform.rotation * Quaternion.Euler(-90, 0, 0) * Quaternion.Euler(0, 180, 0);
    }

    public RenderTexture Render()
    {
        _minimap_texture = new RenderTexture(Screen.width, Screen.height, 24);
        var vpr = cam.rect;
        cam.rect = new Rect(0, 0, 1, 1);
        cam.targetTexture = _minimap_texture;
        cam.Render();
        cam.targetTexture = null;
        SetMinimapMode();
        cam.rect = vpr;
        return _minimap_texture;
    }

    void SetViewPort(float x, float y, float width, float height)
    {
        cam.rect = new Rect(x, y, width, height);
    }

    void SetCameraOrientation(float angle)
    {
        cam.transform.rotation = Quaternion.Euler(0, 0, angle);
    }

    void DrawProjection(Vector3[] projection)
    {
        _minimap_camera_projection_line.positionCount = 4;
        _minimap_camera_projection_line.SetPositions(projection);
        _minimap_camera_projection_line.loop = true;
        _minimap_camera_projection_line.startWidth = 2f;
        _minimap_camera_projection_line.endWidth = 2f;
    }

    void Update()
    {
        if (!_inited)
        {
            _minimap_texture = Render();
            _inited = true;
        }
        else
        {
            UpdateProjection();
        }

        //UpdateProjection();
    }

    void UpdateProjection()
    {
        if (
            _last_camera_position != main_camera.transform.position
            || _last_camera_rotation != main_camera.transform.rotation
        )
        {
            DrawProjection(GetCameraProjection());
            _last_camera_position = main_camera.transform.position;
            _last_camera_rotation = main_camera.transform.rotation;
        }
    }

    Plane plane = new Plane(inPoint: Vector3.zero, inNormal: Vector3.up);
    Vector3[] vec = new Vector3[4];

    Vector3[] GetCameraProjection()
    {
        Ray ray0 = main_camera.ScreenPointToRay(new Vector2(0, 0));
        Ray ray1 = main_camera.ScreenPointToRay(new Vector2(Screen.width, 0));
        Ray ray2 = main_camera.ScreenPointToRay(new Vector2(Screen.width, Screen.height));
        Ray ray3 = main_camera.ScreenPointToRay(new Vector2(0, Screen.height));

        float enter0,
            enter1,
            enter2,
            enter3;

        plane.Raycast(ray0, out enter0);
        plane.Raycast(ray1, out enter1);
        plane.Raycast(ray2, out enter2);
        plane.Raycast(ray3, out enter3);

        var point0 = ray0.GetPoint(enter0);
        var point1 = ray1.GetPoint(enter1);
        var point2 = ray2.GetPoint(enter2);
        var point3 = ray3.GetPoint(enter3);

        var camera_y = cam.transform.position.y - 1;
        point0.y = camera_y;
        point1.y = camera_y;
        point2.y = camera_y;
        point3.y = camera_y;

        vec[0] = point0;
        vec[1] = point1;
        vec[2] = point2;
        vec[3] = point3;

        return vec;
    }

    public bool IsPointerOver(Vector2 pnt)
    {
        return cam.rect.Contains(pnt);
    }
}
