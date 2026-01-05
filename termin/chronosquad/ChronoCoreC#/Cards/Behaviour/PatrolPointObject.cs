using System.Collections;
using System.Collections.Generic;
using System;
using UnityEngine;

public class PatrolPointObject : MonoBehaviour
{
    public PatrolPointType Type = PatrolPointType.Walk;
    public float StandTime = 0.0f;

    public bool BezierLabel = false;
    public GameObject InteractionObject = null;

    public PlatformAreaBase _platform_area_base;

    public ReferencedPose GetReferencedPose()
    {
        ObjectId frame = default;

        if (_platform_area_base != null)
            frame = new ObjectId(_platform_area_base.FrameName());

        return new ReferencedPose(new Pose(transform.position, transform.rotation), frame);
    }

#if UNITY_EDITOR
    [ContextMenu("UpdatePlatformAreaBase")]
    public void UpdatePlatformAreaBase()
    {
        _platform_area_base = GameCore.FindInParentTree<PlatformAreaBase>(gameObject);
        // set that object is dirty
        UnityEditor.EditorUtility.SetDirty(this);
    }

    [UnityEditor.MenuItem("Tools/PatrolPointObject/UpdatePlatformAreaBase")]
    public static void UpdatePlatformAreaBaseAll()
    {
        var patrol_points = FindObjectsOfType<PatrolPointObject>();
        foreach (var patrol_point in patrol_points)
        {
            patrol_point.UpdatePlatformAreaBase();
        }

        // set dirty
        UnityEditor.SceneManagement.EditorSceneManager.MarkAllScenesDirty();
    }

    [ContextMenu("LocateToNavMesh")]
    public void LocateToNavMesh()
    {
        var position = transform.position;
        var nav_mesh_hit = new UnityEngine.AI.NavMeshHit();
        if (
            UnityEngine.AI.NavMesh.SamplePosition(
                position,
                out nav_mesh_hit,
                1.0f,
                UnityEngine.AI.NavMesh.AllAreas
            )
        )
        {
            transform.position = nav_mesh_hit.position;
        }
        else
        {
            Debug.LogError("Can't locate to nav mesh");
        }
    }

    [ContextMenu("LocateToGround")]
    public void LocateToGround()
    {
        RaycastHit hit;
        if (
            Physics.Raycast(
                transform.position + Vector3.up * 0.3f,
                Vector3.down,
                out hit,
                layerMask: Utility.ToMask(Layers.GROUND_LAYER)
                    | Utility.ToMask(Layers.DEFAULT_LAYER)
                    | Utility.ToMask(Layers.OBSTACLES_LAYER),
                maxDistance: 10.0f
            )
        )
        {
            transform.position = hit.point;
        }
        else
        {
            Debug.LogError("Can't locate to ground");
        }
    }

    [UnityEditor.MenuItem("Tools/PatrolPointObject/LocateToNavMeshAll")]
    public static void LocateToNavMeshAll()
    {
        var patrol_points = FindObjectsOfType<PatrolPointObject>();
        foreach (var patrol_point in patrol_points)
        {
            patrol_point.LocateToNavMesh();
        }

        // set dirty
        UnityEditor.SceneManagement.EditorSceneManager.MarkAllScenesDirty();
    }

    [UnityEditor.MenuItem("Tools/PatrolPointObject/LocateToGroundAll")]
    public static void LocateToGroundAll()
    {
        var patrol_points = FindObjectsOfType<PatrolPointObject>();
        foreach (var patrol_point in patrol_points)
        {
            patrol_point.LocateToGround();
        }

        // set dirty
        UnityEditor.SceneManagement.EditorSceneManager.MarkAllScenesDirty();
    }
#endif
}
