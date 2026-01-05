using System;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

class PathViewer : MonoBehaviour
{
    LineRenderer _line_renderer;
    static PathViewer _instance;

    struct PointNormal
    {
        public Vector3 point;
        public Vector3 normal;

        public PointNormal(Vector3 point, Vector3 normal)
        {
            this.point = point;
            this.normal = normal;
        }
    }

    MyList<PointNormal> _precreated = new MyList<PointNormal>();

    public static PathViewer Instance
    {
        get { return _instance; }
    }

    void Awake()
    {
        _instance = this;
    }

    void Start()
    {
        _line_renderer = this.gameObject.AddComponent<LineRenderer>();
        _line_renderer.material = MaterialKeeper.Instance.GetMaterial("PathViewMaterial");
        _line_renderer.startWidth = 0.1f;
        _line_renderer.endWidth = 0.1f;
        _line_renderer.positionCount = 2;
        _line_renderer.useWorldSpace = true;
        _line_renderer.enabled = true;
    }

    public void PathVisualize(UnitPath path)
    {
        _precreated.Clear();
        _line_renderer.enabled = true;

        for (int i = 0; i < path.Count; i++)
        {
            switch (path[i].type)
            {
                case UnitPathPointType.StandartMesh:
                case UnitPathPointType.UpstairsMove:
                case UnitPathPointType.ToUpstairsZone:
                case UnitPathPointType.FromUpstairsZone:
                case UnitPathPointType.BracedClimbingLink:
                case UnitPathPointType.DownToBraced:
                case UnitPathPointType.BracedToUp:
                case UnitPathPointType.JumpDown:
                    var global_point = path[i].position.GlobalPosition(
                        GameCore.GetChronosphereController().GetCurrentTimeline().GetTimeline()
                    );
                    _precreated.Add(new PointNormal(global_point, path[i].normal));
                    break;

                default:
                    break;
            }
        }

        _line_renderer.positionCount = _precreated.Count + 1;
        _line_renderer.SetPosition(
            0,
            path.StartPosition.GlobalPosition(
                GameCore.GetChronosphereController().GetCurrentTimeline().GetTimeline()
            )
                + Vector3.up * 0.1f
        );

        for (int i = 0; i < _precreated.Count; i++)
        {
            _line_renderer.SetPosition(i + 1, _precreated[i].point + _precreated[i].normal * 0.1f);
        }

        _line_renderer.startWidth = 0.1f;
        _line_renderer.endWidth = 0.1f;
    }

    public void DisableView()
    {
        _line_renderer.enabled = false;
    }

    public void DrawLine(Vector3 apos, Vector3 bpos)
    {
        _precreated.Clear();
        _line_renderer.enabled = true;
        _line_renderer.positionCount = 2;
        _line_renderer.SetPosition(0, apos);
        _line_renderer.SetPosition(1, bpos);
        _line_renderer.startWidth = 0.1f;
        _line_renderer.endWidth = 0.1f;
    }

    public void UpdatePathView(Vector3 pos, GameObject go, int areas)
    {
        var selected = GameCore.SelectedActor();
        if (selected == null)
            return;

        bool finish_finded = false;

        var tl = selected.Object().GetTimeline();
        var start_position = selected.Object().CurrentReferencedPoint();
        var finish_position = PathFinding.NavMeshPoint(
            pos,
            tl,
            out finish_finded,
            weak_position_cast: false
        );

        Debug.Assert(!float.IsInfinity(finish_position.LocalPosition.x));

        if (!finish_finded)
        {
            //Debug.Log("Finish not finded");
            DisableView();
            return;
        }

        Debug.Assert(!float.IsInfinity(finish_position.LocalPosition.x));

        var unitpath = PathFinding.MakeUnitPathForMoving(
            selected.Object(),
            selected.Object().GetTimeline(),
            start_position,
            finish_position,
            PathFindingTarget.Standart,
            PathFindingTarget.Standart,
            _braced_coordinates: default,
            navmesh_precast: false,
            use_normal_as_up: false
        );

        PathVisualize(unitpath);
    }

    public void UpdatePathViewToLean(BracedCoordinates braced_coordinates, GameObject go)
    {
        var selected = GameCore.SelectedActor();
        if (selected == null)
            return;

        var start_position = selected.Object().CurrentReferencedPoint();
        var target_vector = braced_coordinates.NavPosition;

        bool finish_finded = false;
        var target_position = PathFinding.NavMeshPoint(
            target_vector,
            selected.Object().GetTimeline(),
            out finish_finded,
            weak_position_cast: true
        );

        if (!finish_finded)
        {
            DisableView();
            return;
        }

        Debug.Assert(!float.IsInfinity(target_position.LocalPosition.x));

        var unitpath = PathFinding.MakeUnitPathForMoving(
            selected.Object(),
            selected.Object().GetTimeline(),
            start_position,
            target_position,
            PathFindingTarget.Standart,
            PathFindingTarget.Lean,
            _braced_coordinates: braced_coordinates,
            navmesh_precast: false,
            use_normal_as_up: false
        );

        PathVisualize(unitpath);
    }
}
