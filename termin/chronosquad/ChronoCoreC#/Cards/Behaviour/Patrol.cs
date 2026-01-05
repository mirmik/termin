using System.Collections;
using System.Collections.Generic;
using System;

#if UNITY_64
using UnityEngine;
#endif

[RequireComponent(typeof(PatrolPointCollection))]
public class Patrol : MonoBehaviour
{
    PatrolPointCollection patrolPointCollection;
    ObjectController guard_view;

    //BasicAiController patrol_behaviour;

    List<GameObject> patrol_points_view = new List<GameObject>();
    GameObject linear_path;
    LineRenderer line_renderer;

    //bool _points_was_changed_in_game_mode = false;

    public MyList<PatrolPoint> ObjectPatrolPoints()
    {
        var guard = guard_view.GetObject();
        var guard_behaviour = guard.AiController();
        var patrol_commander = (guard_behaviour as BasicAiController).GetCommander("patrol");

        var patrol_points = (patrol_commander as PatrolAiCommander).GetPoints();
        return patrol_points;
    }

    void OnEditorPointMoved(PatrolPointEditor point)
    {
        var guard = guard_view.GetObject();
        var patrol_points = ObjectPatrolPoints();

        var p = PathFinding.GlobalToFramedPosition(
            point.transform.position,
            guard.GetTimeline(),
            default
        );

        var rr = patrol_points[point.Index].pose.LocalRotation();
        var rp = new ReferencedPose(p.LocalPosition, rr, p.Frame.name);
        patrol_points[point.Index].pose = rp;

        UpdateViewPosition();
    }

    public void SetPointRotation(Quaternion q, int index)
    {
        var ppoints = ObjectPatrolPoints();
        var point = ppoints[index];
        point.pose.pose.rotation = q;
    }

    string JsonFromPoints(MyList<PatrolPoint> points)
    {
        var trent = SimpleJsonParser.ListToTrent<PatrolPoint>(points);
        return SimpleJsonParser.SerializeTrent(trent);
    }

    void SavePointToTemporaryStore()
    {
        var patrol_points = ObjectPatrolPoints();
        var name = this.name;

        var scene_name = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
        var dirname = Application.streamingAssetsPath + "/PatrolPointsTMP/" + scene_name + "/";
        var store_path = dirname + name + ".json";

        // create directory
        if (!System.IO.Directory.Exists(dirname))
        {
            System.IO.Directory.CreateDirectory(dirname);
        }

        var json = JsonFromPoints(patrol_points);
        System.IO.File.WriteAllText(store_path, json);
    }

    public void OnApplicationQuit()
    {
        // if (_points_was_changed_in_game_mode)
        // {
        SavePointToTemporaryStore();
        //}
    }

    void OnEditorModeChanged(bool mode)
    {
        if (mode)
        {
            var patrol_points = ObjectPatrolPoints();

            var timeline = GameCore.CurrentTimeline();
            if (patrol_points.Count != patrol_points_view.Count)
            {
                foreach (var point in patrol_points_view)
                {
                    if (point != null)
                        DestroyImmediate(point);
                }
                patrol_points_view.Clear();

                foreach (var point in patrol_points)
                {
                    if (point == null)
                        continue;

                    var patrol_point = GameObject.Instantiate(
                        MaterialKeeper.Instance.GetPrefab("PPoint")
                    );
                    var pe = patrol_point.AddComponent<PatrolPointEditor>();
                    pe.Init(this, point.stand_time);
                    pe.Index = patrol_points_view.Count;
                    pe.OnEditorPointMoved += OnEditorPointMoved;

                    //patrol_point.GetComponent<Renderer>().material
                    //	= MaterialKeeper.Instance.GetMaterial("PatrolPointMaterial");

                    patrol_point.layer = LayerMask.NameToLayer("Editor");
                    var gp = point.pose.GlobalPose(timeline);
                    patrol_point.transform.position = gp.position;
                    patrol_point.transform.rotation = gp.rotation;
                    //patrol_point.transform.parent = this.transform;
                    patrol_points_view.Add(patrol_point);
                }

                if (linear_path != null)
                    DestroyImmediate(linear_path);

                linear_path = new GameObject();
                linear_path.transform.parent = this.transform;
                linear_path.name = "LinearPath";
                line_renderer = linear_path.AddComponent<LineRenderer>();
                line_renderer.material = new Material(Shader.Find("Sprites/Default"));
                line_renderer.startColor = Color.blue;
                line_renderer.endColor = Color.red;
                line_renderer.startWidth = 0.1f;
                line_renderer.endWidth = 0.1f;
                line_renderer.positionCount = patrol_points.Count + 1;
                linear_path.layer = LayerMask.NameToLayer("Editor");
            }

            UpdateViewPosition();
        }
        else
        {
            foreach (var point in patrol_points_view)
            {
                if (point != null)
                    DestroyImmediate(point);
            }
            patrol_points_view.Clear();

            if (linear_path != null)
                DestroyImmediate(linear_path);
        }
    }

    public void RemovePoint(int index)
    {
        var patrol_points = ObjectPatrolPoints();
        patrol_points.RemoveAt(index);
        OnEditorModeChanged(false);
        OnEditorModeChanged(true);
        UpdateViewPosition();
    }

    public void CreateOneYet(int index)
    {
        var patrol_points = ObjectPatrolPoints();
        Vector3 position = Vector3.zero;

        if (patrol_points.Count == 0 || patrol_points.Count == 1)
        {
            position = this.transform.position + new Vector3(1.0f, 0, 1.0f);
        }
        else
        {
            var p1 = patrol_points[index].pose.GlobalPosition(GameCore.CurrentTimeline());
            var next_index = (index + 1) % patrol_points.Count;
            var p2 = patrol_points[next_index].pose.GlobalPosition(GameCore.CurrentTimeline());
            position = (p1 + p2) / 2.0f;
        }

        var pnt = new PatrolPoint(
            new ReferencedPose(new Pose(position, Quaternion.identity), default(ObjectId)),
            0,
            PatrolPointType.Walk,
            null
        );

        if (patrol_points.Count == 0 || patrol_points.Count == 1)
        {
            patrol_points.Add(pnt);
        }
        else
        {
            patrol_points.Insert(index + 1, pnt);
        }

        OnEditorModeChanged(false);
        OnEditorModeChanged(true);
        UpdateViewPosition();
    }

    void UpdateViewPosition()
    {
        var guard = guard_view.GetObject();
        var timeline = GameCore.CurrentTimeline();
        var guard_behaviour = guard.AiController();
        var patrol_commander = (guard_behaviour as BasicAiController).GetCommander("patrol");

        var patrol_points = (patrol_commander as PatrolAiCommander).GetPoints();

        for (int i = 0; i < patrol_points.Count; i++)
        {
            var point = patrol_points[i];
            var patrol_point = patrol_points_view[i];
            patrol_point.transform.position = point.pose.GlobalPosition(timeline);

            line_renderer.SetPosition(i, point.pose.ToPoint().GlobalPosition(timeline));
        }
        if (patrol_points.Count > 0)
            line_renderer.SetPosition(
                patrol_points.Count,
                patrol_points[0].pose.GlobalPosition(timeline)
            );
    }

    void Start()
    {
        patrolPointCollection = this.GetComponent<PatrolPointCollection>();
        var patrol_points = patrolPointCollection.patrol_points;
        guard_view = this.GetComponent<ObjectController>();
        var guard = guard_view.GetObject();

        var guard_behaviour = guard.AiController();

        if (guard_behaviour == null)
        {
            var patrol_behaviour = new BasicAiController(guard);
            guard.SetAiController(patrol_behaviour);

            var commander = new PatrolAiCommander();
            if (patrol_points != null && patrol_points.Count > 0)
                commander.SetPoints(GetPatrolPoints());

            var reaction_commander = new GuardReactionCommander();

            patrol_behaviour.AddCommander(reaction_commander, "reaction", 1);
            patrol_behaviour.AddCommander(commander, "patrol", 0);

            foreach (var point in patrol_points)
            {
                if (point == null)
                    continue;

                point.transform.parent = null;
            }
        }

        ChronosphereController.instance.EditorModeChanged += OnEditorModeChanged;
    }

    ReferencedPose GetReferencedPose(Vector3 point, Quaternion rotation)
    {
        var pnt = GameCore.FindNearestPointOnNavMesh(point);
        var area = GameCore.FrameNameForPosition(pnt);
        var refpose = ReferencedPose.FromGlobalPose(
            new Pose(pnt, rotation),
            area,
            guard_view.GetObject().GetTimeline()
        );
        return refpose;
    }

    MyList<PatrolPoint> GetPatrolPoints()
    {
        MyList<PatrolPoint> points = new MyList<PatrolPoint>();
        var patrol_points = patrolPointCollection.patrol_points;
        foreach (var point in patrol_points)
        {
            if (point == null)
                continue;

            var refpoint = point.GetReferencedPose();
            var patrol_point = new PatrolPoint(
                refpoint,
                point.StandTime,
                point.Type,
                point.InteractionObject == null ? null : point.InteractionObject.name
            );
            points.Add(patrol_point);
        }
        return points;
    }
}
