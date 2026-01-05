using System.Collections;
using System.Collections.Generic;
using System;

#if UNITY_64
using UnityEngine;
using UnityEditor;
#endif

[ExecuteAlways]
public class PatrolPointCollection : MonoBehaviour
{
    public List<PatrolPointObject> patrol_points = new List<PatrolPointObject>();

#if UNITY_EDITOR
    List<Pose> position_stash = new List<Pose>();
    Vector3 last_position;
    Quaternion last_rotation;
    Vector3 last_parent_position;
    Quaternion last_parent_rotation;

    bool ParentIsMoved()
    {
        if (this.transform.parent == null)
            return false;

        if (last_parent_position != this.transform.parent.position)
        {
            last_parent_position = this.transform.parent.position;
            return true;
        }

        if (last_parent_rotation != this.transform.parent.rotation)
        {
            last_parent_rotation = this.transform.parent.rotation;
            return true;
        }

        return false;
    }

    bool IsMoved()
    {
        if (last_position != this.transform.position)
        {
            last_position = this.transform.position;
            return true;
        }

        if (last_rotation != this.transform.rotation)
        {
            last_rotation = this.transform.rotation;
            return true;
        }

        return false;
    }

    void Start()
    {
        if (Application.isEditor && !Application.isPlaying)
        {
            if (this.transform.parent == null)
                return;

            StashPositions();
            last_position = this.transform.position;
            last_rotation = this.transform.rotation;
            last_parent_position = this.transform.parent.position;
            last_parent_rotation = this.transform.parent.rotation;
        }
    }

    void Update()
    {
        if (Application.isEditor && !Application.isPlaying)
        {
            if (ParentIsMoved())
            {
                StashPositions();
                return;
            }

            if (IsMoved())
                RestorePositions();
        }
    }

    [ContextMenu("Stash Positions")]
    void StashPositions()
    {
        position_stash.Clear();
        foreach (var point in patrol_points)
        {
            position_stash.Add(new Pose(point.transform.position, point.transform.rotation));
        }
    }

    [ContextMenu("Restore Positions")]
    void RestorePositions()
    {
        for (int i = 0; i < patrol_points.Count; i++)
        {
            var point = patrol_points[i];
            if (i < position_stash.Count)
            {
                point.transform.position = position_stash[i].position;
                point.transform.rotation = position_stash[i].rotation;
            }
        }
    }

    void OnDrawGizmos()
    {
        try
        {
            if (patrol_points == null)
                return;

            for (int i = 0; i < patrol_points.Count; i++)
            {
                var point = patrol_points[i];
                if (point == null)
                    continue;

                Gizmos.color = Color.red;
                Gizmos.DrawSphere(point.transform.position, 0.5f);

                if (i > 0)
                {
                    var prev_point = patrol_points[i - 1];
                    if (prev_point == null)
                        continue;

                    Gizmos.color = Color.red;
                    Gizmos.DrawLine(prev_point.transform.position, point.transform.position);
                }
            }

            if (patrol_points.Count > 1)
            {
                var point = patrol_points[patrol_points.Count - 1];
                var first_point = patrol_points[0];
                if (point != null && first_point != null)
                {
                    Gizmos.color = Color.red;
                    Gizmos.DrawLine(point.transform.position, first_point.transform.position);
                }
            }

            Gizmos.color = Color.yellow;
            if (patrol_points.Count > 0)
                Gizmos.DrawLine(this.transform.position, patrol_points[0].transform.position);

            if (patrol_points.Count > 1)
            {
                Gizmos.color = Color.yellow;
                Gizmos.DrawLine(
                    patrol_points[0].transform.position,
                    patrol_points[1].transform.position
                );
            }
        }
        catch (Exception e)
        {
            Debug.Log(
                "Exception on draw gizmos: name: " + this.gameObject.name + " ex:" + e.Message
            );
            throw;
        }
    }

    void AddPatrolPoint(int index)
    {
        var point = new GameObject("PatrolPoint");
        var pp = point.AddComponent<PatrolPointObject>();
        point.transform.parent = this.transform;
        point.transform.position = this.transform.position + new Vector3(1.0f, 0, 1.0f + index);
        patrol_points.Add(pp);
        point.transform.localScale = new Vector3(0.5f, 0.5f, 0.5f);
        point.name = "PatrolPoint";
    }

    [ContextMenu("Add Patrol Points")]
    void Add1PatrolPoints()
    {
        AddPatrolPoint(1);
    }

    [ContextMenu("Add 2 Patrol Points")]
    void Add2PatrolPoints()
    {
        AddPatrolPoint(1);
        AddPatrolPoint(2);
    }

    [ContextMenu("Add 3 Patrol Points")]
    void Add3PatrolPoints()
    {
        AddPatrolPoint(1);
        AddPatrolPoint(2);
        AddPatrolPoint(3);
    }

    [ContextMenu("Add 4 Patrol Points")]
    void Add4PatrolPoints()
    {
        AddPatrolPoint(1);
        AddPatrolPoint(2);
        AddPatrolPoint(3);
        AddPatrolPoint(4);
    }

    [ContextMenu("Add 5 Patrol Points")]
    void Add5PatrolPoints()
    {
        AddPatrolPoint(1);
        AddPatrolPoint(2);
        AddPatrolPoint(3);
        AddPatrolPoint(4);
        AddPatrolPoint(5);
    }

    [ContextMenu("Restore Patrol Points From Children")]
    public void RestorePatrolPointsFromChildren()
    {
        patrol_points.Clear();
        foreach (Transform child in this.transform)
        {
            // if name has Point
            var pp = child.GetComponent<PatrolPointObject>();
            if (child.name.Contains("Point"))
                patrol_points.Add(pp);
        }

        // mark as dirty
        EditorUtility.SetDirty(this);
    }

    // Rescan for all guards
    // Menu in toolbar
    [MenuItem("Tools/PatrolTools/Rescan All Guards")]
    static void RescanAllGuards()
    {
        // Find all AddPatrolPoint components
        var addPatrolPoints = GameObject.FindObjectsByType<PatrolPointCollection>(
            FindObjectsSortMode.None
        );
        foreach (var addPatrolPoint in addPatrolPoints)
        {
            addPatrolPoint.RestorePatrolPointsFromChildren();
        }
    }

    [MenuItem("Tools/PatrolTools/Set Patrol Point Object To Patrol Point Collection")]
    static void SetPatrolPointObjectToPatrolPointCollection()
    {
        // Find all oject with 'PatrolPoint' name
        var all_objects = GameObject.FindObjectsByType<GameObject>(FindObjectsSortMode.None);
        foreach (var obj in all_objects)
        {
            if (obj.name.Contains("PatrolPoint"))
            {
                var pp = obj.GetComponent<PatrolPointObject>();
                if (pp == null)
                {
                    obj.AddComponent<PatrolPointObject>();
                }
            }
        }
    }

    GameObject InstantiatePatrolPoint(
        Vector3 position,
        Quaternion rotation,
        float stand_time,
        int type
    )
    {
        var point = new GameObject("PatrolPoint");
        var pp = point.AddComponent<PatrolPointObject>();
        point.transform.parent = this.transform;
        point.transform.position = position;
        point.transform.rotation = rotation;
        pp.StandTime = stand_time;
        pp.Type = (PatrolPointType)type;
        patrol_points.Add(pp);
        point.transform.localScale = new Vector3(0.5f, 0.5f, 0.5f);
        point.name = "PatrolPoint";
        return point;
    }

    // Подтягивает изменения маршрута сделанные в режиме игрового редактора
    [ContextMenu("UploadPointsFromTemporaryStore")]
    public void UploadPointsFromTemporaryStore()
    {
        var scene_name = UnityEngine.SceneManagement.SceneManager.GetActiveScene().name;
        var store_path =
            Application.streamingAssetsPath
            + "/PatrolPointsTMP/"
            + scene_name
            + "/"
            + name
            + ".json";
        bool exists = System.IO.File.Exists(store_path);
        if (!exists)
        {
            Debug.Log("No file found: " + store_path);
            return;
        }

        var json = System.IO.File.ReadAllText(store_path);
        IList<PatrolPoint> points_dct;

        try
        {
            var trent = SimpleJsonParser.DeserializeTrent(json);
            Debug.Log("Trent: " + trent);
            points_dct = SimpleJsonParser.ListFromTrent<PatrolPoint>((IList<object>)trent);
        }
        catch (Exception e)
        {
            Debug.LogError("Exception on deserialize points: " + e.Message);
            throw;
        }

        patrol_points.Clear();

        var childs_patrol_points = new List<PatrolPointObject>();
        foreach (Transform child in this.transform)
        {
            var pp = child.GetComponent<PatrolPointObject>();
            if (pp != null)
                childs_patrol_points.Add(pp);
        }

        // Clear all points
        foreach (var point in childs_patrol_points)
        {
            try
            {
                DestroyImmediate(point.gameObject);
            }
            catch (Exception ex)
            {
                Debug.LogError($"Ex: name: {name}" + ex.Message);
            }
        }

        Debug.Assert(points_dct != null);
        foreach (var point in points_dct)
        {
            var pose = point.pose;
            var p = InstantiatePatrolPoint(
                pose.LocalPosition(),
                pose.LocalRotation(),
                point.stand_time,
                (int)point.type
            );
        }

        // mark as dirty
        EditorUtility.SetDirty(this);
    }

    [MenuItem("Tools/PatrolTools/Restore All Patrol Points From Temporary Store")]
    public static void RestoreAllPatrolPointsFromTemporaryStore()
    {
        // Find all AddPatrolPoint components
        var addPatrolPoints = GameObject.FindObjectsByType<PatrolPointCollection>(
            FindObjectsSortMode.None
        );
        foreach (var addPatrolPoint in addPatrolPoints)
        {
            addPatrolPoint.UploadPointsFromTemporaryStore();
        }
    }

    [ContextMenu("InitOrRestoreFirstPoint")]
    public void InitOrRestoreFirstPoint()
    {
        if (patrol_points.Count == 0)
        {
            var point = InstantiatePatrolPoint(
                this.transform.position,
                this.transform.rotation,
                0.0f,
                (int)PatrolPointType.Walk
            );
        }
        else
        {
            var first_point = patrol_points[0];
            StashPositions();
            this.transform.position = first_point.transform.position;
            this.transform.rotation = first_point.transform.rotation;
            RestorePositions();
        }
        // mark as dirty
        EditorUtility.SetDirty(this);
    }

    [MenuItem("Tools/PatrolTools/InitOrRestoreFirstPoint")]
    public static void InitOrRestoreFirstPointGlobal()
    {
        // Find all AddPatrolPoint components
        var addPatrolPoints = GameObject.FindObjectsByType<PatrolPointCollection>(
            FindObjectsSortMode.None
        );
        foreach (var addPatrolPoint in addPatrolPoints)
        {
            addPatrolPoint.InitOrRestoreFirstPoint();
        }
    }

#endif
}
