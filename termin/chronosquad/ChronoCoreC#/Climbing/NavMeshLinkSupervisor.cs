using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
using Unity.AI.Navigation;
using UnityEngine.AI;
#endif

public class PlatformData
{
    public ObjectId frame_id;
    public GameObject go;
    public Transform reference_object;
    public MyList<NavMeshLink> nav_mesh_links = new MyList<NavMeshLink>();
    public PointOctree<NavMeshLink> octree_points = new PointOctree<NavMeshLink>(
        1000,
        Vector3.zero,
        1
    );
    public PointOctree<NavMeshLink> octree_center_points = new PointOctree<NavMeshLink>(
        1000,
        Vector3.zero,
        1
    );
}

public class NavMeshLinkSupervisor : MonoBehaviour
{
    static NavMeshLinkSupervisor _instance;

    Dictionary<GameObject, PlatformData> object_to_platform =
        new Dictionary<GameObject, PlatformData>();

    MyList<CommonClimbingBlock> climbing_block_list = new MyList<CommonClimbingBlock>();
    MyList<NavMeshLink> nav_mesh_links = new MyList<NavMeshLink>();

    //PointOctree<NavMeshLink> _octree = new PointOctree<NavMeshLink>(1000, Vector3.zero, 1);
    public MyList<PlatformData> platformDatas = new MyList<PlatformData>();

    public static NavMeshLinkSupervisor Instance
    {
        get
        {
            if (_instance == null)
            {
                _instance = GameObject.FindFirstObjectByType<NavMeshLinkSupervisor>();
            }

            return _instance;
        }
    }

    [ContextMenu("PlatformsInfo")]
    public void PlatformsInfo()
    {
        foreach (var platform in platformDatas)
        {
            Debug.Log("Platform: " + platform.frame_id);
            Debug.Log("NavMeshLinks: " + platform.nav_mesh_links.Count);
        }
    }

    public CommonClimbingBlock FoundNearestClimbingBlock(Vector3 position)
    {
        CommonClimbingBlock nearest = null;
        float min_distance = float.MaxValue;
        foreach (var block in climbing_block_list)
        {
            var dist_to_block = block.DistanceToBlock(position);
            if (dist_to_block < min_distance)
            {
                min_distance = dist_to_block;
                nearest = block;
            }
        }
        return nearest;
    }

    public ObjectId FoundPlatformId(GameObject go)
    {
        if (object_to_platform.ContainsKey(go))
            return object_to_platform[go].frame_id;
        else
            return default(ObjectId);
    }

    public GameObject FoundPlatformGO(GameObject go)
    {
        if (object_to_platform.ContainsKey(go))
            return object_to_platform[go].go;
        else
            return default(GameObject);
    }

    public PlatformData PlatformDataForPosition(Vector3 position)
    {
        var clossest_collider = Physics.OverlapSphere(
            position,
            0.5f,
            layerMask: Utility.ToMask(Layers.DEFAULT_LAYER)
                | Utility.ToMask(Layers.OBSTACLES_LAYER)
                | Utility.ToMask(Layers.GROUND_LAYER)
        );

        if (clossest_collider.Length == 0)
        {
            return null;
        }

        var obj = clossest_collider[0].gameObject;
        if (object_to_platform.ContainsKey(obj))
        {
            var platform = object_to_platform[obj];
            return platform;
        }
        else
        {
            //Debug.LogError("No platform found for position: " + position + " obj: " + obj);
            return null;
        }
    }

    public PlatformAreaBase PlatformForPosition(Vector3 position)
    {
        var platform_data = PlatformDataForPosition(position);
        if (platform_data == null)
            return null;

        return platform_data.go.GetComponent<PlatformAreaBase>();
    }

    public ObjectId PlatformIdForPosition(Vector3 position)
    {
        var platform_data = PlatformDataForPosition(position);
        if (platform_data == null)
            return default(ObjectId);

        return platform_data.frame_id;
    }

    void ScanPlatformBase_(GameObject go, PlatformData data, bool bse)
    {
        if (go.GetComponent<PlatformAreaBase>() != null && !bse)
        {
            // Не лезем в вотчину другого объекта
            return;
        }

        if (go.GetComponent<NavMeshLink>() != null)
        {
            data.nav_mesh_links.Add(go.GetComponent<NavMeshLink>());
            var start_position = go.transform.TransformPoint(
                go.GetComponent<NavMeshLink>().startPoint
            );
            var end_position = go.transform.TransformPoint(go.GetComponent<NavMeshLink>().endPoint);

            if (data.reference_object != null)
            {
                start_position = data.reference_object.InverseTransformPoint(start_position);
                end_position = data.reference_object.InverseTransformPoint(end_position);
            }

            var center_position = (start_position + end_position) / 2;

            // Нужны маркеры, какие точки нужно добавлять в деревья
            data.octree_center_points.Add(go.GetComponent<NavMeshLink>(), center_position);
            data.octree_points.Add(go.GetComponent<NavMeshLink>(), start_position);
            data.octree_points.Add(go.GetComponent<NavMeshLink>(), end_position);
        }

        if (go.layer != 0)
            return;

        object_to_platform[go] = data;
        foreach (Transform child in go.transform)
        {
            ScanPlatformBase_(child.gameObject, data, false);
        }
    }

    void ScanPlatformBase(PlatformAreaBase platform_base)
    {
        PlatformData data = new PlatformData();
        data.reference_object = platform_base.IsPlatform
            ? platform_base.ObjectReference.transform
            : null;
        data.go = platform_base.gameObject;
        data.frame_id =
            platform_base.IsPlatform == false
                ? default(ObjectId)
                : new ObjectId(platform_base.ObjectReference.name);
        ScanPlatformBase_(platform_base.gameObject, data, bse: true);
        platformDatas.Add(data);
    }

    void ScanObjectsForPlatforms()
    {
        var platform_bases = GameObject.FindObjectsByType<PlatformAreaBase>(
            FindObjectsSortMode.None
        );
        foreach (var platform_base in platform_bases)
            ScanPlatformBase(platform_base);
    }

    void Awake()
    {
        _instance = this;
    }

    public void InitPlatforms()
    {
        ScanObjectsForPlatforms();
        nav_mesh_links = FindAllNavMeshLinks();
        climbing_block_list = FindAllClimbingBlocks();
    }

    MyList<NavMeshLink> FindAllNavMeshLinks() =>
        new MyList<NavMeshLink>(
            GameObject.FindObjectsByType<NavMeshLink>(FindObjectsSortMode.None)
        );

    MyList<CommonClimbingBlock> FindAllClimbingBlocks() =>
        new MyList<CommonClimbingBlock>(
            GameObject.FindObjectsByType<CommonClimbingBlock>(FindObjectsSortMode.None)
        );

    List<NavMeshLink> nearBy = new List<NavMeshLink>();

    // public NavMeshLink GetLinkByStartFinal2(Vector3 start, Vector3 final)
    // {
    // 	Vector3 center = (start + final) / 2;
    // 	nearBy.Clear();
    // 	_octree.GetNearbyNonAlloc(center, 0.1f, nearBy);
    // 	if (nearBy.Count > 0)
    // 		return nearBy[0];

    // 	return null;
    // }

    bool CheckLink(NavMeshLink link, Vector3 start, Vector3 final)
    {
        var link_start_global = link.transform.TransformPoint(link.startPoint);
        var link_final_global = link.transform.TransformPoint(link.endPoint);

        var dist_start = Vector3.Distance(link_start_global, start);
        var dist_final = Vector3.Distance(link_final_global, final);
        if (dist_start < 0.5f && dist_final < 0.5f)
        {
            return true;
        }

        var dist_start_final = Vector3.Distance(link_start_global, final);
        var dist_final_start = Vector3.Distance(link_final_global, start);
        if (dist_start_final < 0.5f && dist_final_start < 0.5f)
        {
            return true;
        }

        return false;
    }

    public NavMeshLink GetLinkByStartFinal2(Vector3 start, Vector3 final)
    {
        foreach (var platform in platformDatas)
        {
            var local_start = start;
            var local_final = final;
            var local_center = (start + final) / 2;

            if (platform.reference_object != null)
            {
                local_start = platform.reference_object.InverseTransformPoint(start);
                local_final = platform.reference_object.InverseTransformPoint(final);
                local_center = (local_start + local_final) / 2;
            }

            platform.octree_center_points.GetNearbyNonAlloc(local_center, 0.5f, nearBy);
            foreach (var link in nearBy)
            {
                bool is_ok = CheckLink(link, start, final);
                if (is_ok)
                    return link;
            }

            platform.octree_points.GetNearbyNonAlloc(local_start, 0.5f, nearBy);
            foreach (var link in nearBy)
            {
                bool is_ok = CheckLink(link, start, final);
                if (is_ok)
                    return link;
            }

            platform.octree_points.GetNearbyNonAlloc(local_final, 0.5f, nearBy);
            foreach (var link in nearBy)
            {
                bool is_ok = CheckLink(link, start, final);
                if (is_ok)
                    return link;
            }
        }
        return null;
    }

#if UNITY_EDITOR

    // add tool for editor
    [UnityEditor.MenuItem("Tools/NavMeshLinkSupervisor/RemoveNavMeshLinks")]
    static void CleanNavMeshLinks()
    {
        var links = GameObject.FindObjectsByType<NavMeshLink>(FindObjectsSortMode.None);
        foreach (var link in links)
        {
            DestroyImmediate(link.gameObject);
        }
    }

    // add tool for editor
    [UnityEditor.MenuItem("Tools/NavMeshLinkSupervisor/CleanNavMeshData")]
    static void CleanNavMeshData()
    {
        UnityEngine.AI.NavMesh.RemoveAllNavMeshData();

        // set dirty
        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(
            UnityEngine.SceneManagement.SceneManager.GetActiveScene()
        );
    }

    [UnityEditor.MenuItem("Tools/NavMeshLinkSupervisor/BuildMeshForAllSurfaces")]
    static void BuildMeshForAllSurfaces()
    {
        var surfaces = FindObjectsByType<NavMeshSurface>(FindObjectsSortMode.None);
        foreach (var surface in surfaces)
        {
            surface.BuildNavMesh();
        }
        // set dirty
        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(
            UnityEngine.SceneManagement.SceneManager.GetActiveScene()
        );
    }

#endif
}
