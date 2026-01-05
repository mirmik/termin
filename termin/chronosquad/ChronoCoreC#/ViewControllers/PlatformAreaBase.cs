using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Unity.AI.Navigation;

public class PlatformAreaBase : MonoBehaviour
{
    NavMeshSurface _nav_mesh_surface;
    public bool IsPlatform => ObjectReference != null;
    public GameObject ObjectReference;
    public StaticBrother Brother;

    void Awake()
    {
        _nav_mesh_surface = GetComponent<NavMeshSurface>();
    }

    void Start()
    {
        if (Brother != null)
        {
            DisableAllNavMeshLinksRecurse();
            DisableAllNavMeshSurfacesRecurse();
        }
    }

    void DisableAllNavMeshLinksRecurse()
    {
        DisableAllNavMeshLinksRecurse_Internal(transform);
    }

    void DisableAllNavMeshLinksRecurse_Internal(Transform transform)
    {
        var link = transform.GetComponent<NavMeshLink>();
        if (link != null)
        {
            link.autoUpdate = false;
            //link.RemoveData();
            link.enabled = false;
        }

        for (int i = 0; i < transform.childCount; i++)
        {
            DisableAllNavMeshLinksRecurse_Internal(transform.GetChild(i));
        }
    }

    void DisableAllNavMeshSurfacesRecurse()
    {
        DisableAllNavMeshSurfacesRecurse_Internal(transform);
    }

    void DisableAllNavMeshSurfacesRecurse_Internal(Transform transform)
    {
        var surface = transform.GetComponent<NavMeshSurface>();
        if (surface != null)
        {
            surface.RemoveData();
            surface.enabled = false;
        }

        for (int i = 0; i < transform.childCount; i++)
        {
            DisableAllNavMeshSurfacesRecurse_Internal(transform.GetChild(i));
        }
    }

    public Vector3 GlobalPositionOnMeToGlobalPositionOnStaticBrother(Vector3 position)
    {
        var position_on_me = transform.InverseTransformPoint(position);
        var position_on_brother = Brother.transform.TransformPoint(position_on_me);
        return position_on_brother;
    }

    public Vector3 GlobalPositionOnStaticBrotherToGlobalPositionOnMe(Vector3 position)
    {
        var position_on_brother = Brother.transform.InverseTransformPoint(position);
        var position_on_me = transform.TransformPoint(position_on_brother);
        return position_on_me;
    }

    public int AreaNo()
    {
        return _nav_mesh_surface.defaultArea;
    }

    public string FrameName()
    {
        if (IsPlatform)
            return ObjectReference.name;
        else
            return null;
    }

    public Vector3 GetGravity(Vector3 position)
    {
        var solver = GetComponent<IGravitySolver>();
        if (solver != null)
            return solver.GetGravity(position);
        else
            return Vector3.zero;
    }

    public Vector3 NavigatePosition(Vector3 position)
    {
        if (Brother != null)
            return GlobalPositionOnMeToGlobalPositionOnStaticBrother(position);
        else
            return position;
    }

    public Vector3 InvertNavigatePosition(Vector3 position)
    {
        if (Brother != null)
            return GlobalPositionOnStaticBrotherToGlobalPositionOnMe(position);
        else
            return position;
    }

    void DisableAutoUpdateForAllLinksRecursively_Internal(Transform transform)
    {
        var link = transform.GetComponent<NavMeshLink>();
        if (link != null)
        {
            link.autoUpdate = false;
        }

        for (int i = 0; i < transform.childCount; i++)
        {
            DisableAutoUpdateForAllLinksRecursively_Internal(transform.GetChild(i));
        }
    }

    [ContextMenu("DisableAutoUpdateForAllLinksRecursively")]
    public void DisableAutoUpdateForAllLinksRecursively()
    {
        DisableAutoUpdateForAllLinksRecursively_Internal(transform);
    }
}
