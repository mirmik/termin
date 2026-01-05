using UnityEngine;
using UnityEngine.AI;
using Unity.AI.Navigation;

public static class NML_Utility
{
    static public void RemoveLinks(Transform storage_transform, string links_name = "Links")
    {
        var links = storage_transform.Find(links_name);
        if (links != null)
        {
            GameObject.DestroyImmediate(links.gameObject);
        }
    }

    static void AddLinkToStorage(NavMeshLink link, Transform storage_transform, string storage_name)
    {
        var links = storage_transform.Find(storage_name);
        if (links == null)
        {
            links = new GameObject(storage_name).transform;
            links.gameObject.layer = (int)Layers.LINK_LAYER;
            links.parent = storage_transform;
        }
        link.transform.parent = links;
    }

    static public NavMeshLink MakeLink(
        Vector3 a,
        Vector3 b,
        Quaternion orientation,
        Transform storage_transform,
        int area,
        int agent,
        string storage_name = "Links",
        float width = 0,
        bool autoupdate = false
    )
    {
        var link = new GameObject("Link");
        link.layer = (int)Layers.LINK_LAYER;
        link.transform.position = (a + b) / 2;
        link.transform.rotation = orientation;

        var aa = link.transform.InverseTransformPoint(a);
        var bb = link.transform.InverseTransformPoint(b);

        link.AddComponent<NavMeshLink>();
        var nav_mesh_link = link.GetComponent<NavMeshLink>();
        nav_mesh_link.startPoint = aa;
        nav_mesh_link.endPoint = bb;
        nav_mesh_link.width = width;
        nav_mesh_link.costModifier = 4;
        nav_mesh_link.bidirectional = true;
        nav_mesh_link.area = area;
        nav_mesh_link.agentTypeID = agent;
        nav_mesh_link.autoUpdate = autoupdate;

        AddLinkToStorage(nav_mesh_link, storage_transform, storage_name);

#if UNITY_EDITOR
        // set it dirty
        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(
            storage_transform.gameObject.scene
        );
#endif
        return nav_mesh_link;
    }

    static public NavMeshLink MakeLinkWithChecks(
        Vector3 a,
        Vector3 b,
        Quaternion orientation,
        Transform storage_transform,
        int area,
        int agent,
        bool check_external = false,
        bool check_navmesh = false,
        float width = 0
    )
    {
        if (check_external)
        {
            var c = (a + b) / 2;
            var d = a - c;
            var ta = c + 1.2f * d;
            var tb = c - 1.2f * d;

            var overlap_a = Utility.HasSpaceSphere(ta, 0.01f);
            var overlap_b = Utility.HasSpaceSphere(tb, 0.01f);

            if (!overlap_a || !overlap_b)
            {
                return null;
            }
        }

        if (check_navmesh)
        {
            var asample = PathFinding.NavMeshPoint_Global_EditorMode(a);
            var bsample = PathFinding.NavMeshPoint_Global_EditorMode(b);

            var adist = Vector3.Distance(a, asample);
            var bdist = Vector3.Distance(b, bsample);

            if (adist > 0.2f || bdist > 0.2f)
            {
                return null;
            }
        }

        return MakeLink(
            a: a,
            b: b,
            width: width,
            orientation: orientation,
            storage_transform: storage_transform,
            area: area,
            agent: agent
        );
    }
}
