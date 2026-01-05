using System.Collections;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
using Unity.AI.Navigation;
#endif

#if UNITY_64
[RequireComponent(typeof(NavMeshSurfaceDrawer))]
#endif
public class PlatformView : ObjectController
{
    Vector3 StartPosition;
    Vector3 EndPosition;
    public bool MoveSinus = false;

    float period = 10f;

    NavMeshSurface _nav_mesh_surface;

    int _navmesh_area = -1;

    public float PositionNoiseAmplitude = 1.0f;
    public float PositionNoiseFrequency = 0.6f;
    public float RotationNoiseAmplitude = 0.1f;

    public int AreaNo()
    {
        if (_navmesh_area == -1)
        {
            _nav_mesh_surface = GetComponent<NavMeshSurface>();
            _navmesh_area = _nav_mesh_surface.defaultArea;
        }

        return _navmesh_area;
    }

    public string FrameName()
    {
        return gameObject.name;
    }

    public override void ManualAwake()
    {
        _model = transform.Find("Model").gameObject;
        _nav_mesh_surface = GetComponent<NavMeshSurface>();
        _navmesh_area = _nav_mesh_surface.defaultArea;

        StartPosition = transform.position;
        EndPosition = transform.position + new Vector3(0, 0, 10);
        var chronosphere_controller = GameCore.GetChronosphereController();

        base.ManualAwake();
    }

    public override void UpdateView()
    {
        var object_of_timeline = GetObject();
        Pose pose = object_of_timeline.PoseProphet();

        transform.position = pose.position;
        transform.rotation = pose.rotation;

        UpdateHideOrMaterial(object_of_timeline, always_visible: true);
    }

    public override void InitObjectController(ITimeline tl)
    {
        StartPosition = transform.position;
        EndPosition = transform.position + new Vector3(0, 0, 10);

        var obj = CreateObject<Platform>(gameObject.name, tl);
        obj.SetPose(transform.position, Quaternion.identity);

        if (MoveSinus)
            obj.StartSinusAnimatronic(
                new Pose(StartPosition, Quaternion.identity),
                new Pose(EndPosition, Quaternion.identity),
                period
            );

        base.InitVariables(obj);

        ObjectProxy().Object().RotationNoiseAmplitude = RotationNoiseAmplitude;
        ObjectProxy().Object().PositionNoiseAmplitude = PositionNoiseAmplitude;
        ObjectProxy().Object().PositionNoiseFrequency = PositionNoiseFrequency;

        obj.PreEvaluate();
    }
}
