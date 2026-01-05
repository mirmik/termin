using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;
#if UNITY_64
using Unity.AI.Navigation;
#endif

public class NavMeshSurfaceShadow : MonoBehaviour
{
    public bool UseBottomLayerMarks = false;

    int layers = (1 << (int)Layers.DEFAULT_LAYER) | (1 << (int)Layers.OBSTACLES_LAYER);

    void FindMeshFiltersRecurse(Transform trsf, ref MyList<MeshFilter> meshFilters)
    {
        // Debug.Log("Layer: " + trsf.gameObject.layer);
        // Debug.Log("Layer!: " + layers);
        if (((1 << trsf.gameObject.layer) & layers) == 0)
            return;

        var mesh_filter = trsf.GetComponent<MeshFilter>();
        if (mesh_filter != null)
        {
            if (UseBottomLayerMarks)
            {
                MeshAnalyzeMonoBeh meshAnalyzer = trsf.GetComponent<MeshAnalyzeMonoBeh>();
                if (meshAnalyzer != null && meshAnalyzer.MarkBottomLayer)
                {
                    Debug.Log("Marked for bottom layer: " + trsf.name);
                    meshFilters.Add(mesh_filter);
                }
            }
            else
                meshFilters.Add(mesh_filter);
        }

        // prevent adding shadow to shadow
        var shadow = trsf.GetComponent<NavMeshSurfaceShadow>();
        if (shadow != null)
            return;

        for (int i = 0; i < trsf.childCount; i++)
        {
            FindMeshFiltersRecurse(trsf.GetChild(i).transform, ref meshFilters);
        }
    }

    Mesh CombineMeshes(MyList<MeshFilter> meshFilters, bool reverse = false)
    {
        var combine = new CombineInstance[meshFilters.Count];
        var curtrsf = transform.localToWorldMatrix;
        for (int i = 0; i < meshFilters.Count; i++)
        {
            var trsf = meshFilters[i].transform.localToWorldMatrix;
            var trsf_inv_trsf = curtrsf.inverse * trsf;
            combine[i].mesh = meshFilters[i].sharedMesh;
            combine[i].transform = trsf_inv_trsf;
        }

        var mesh = new Mesh();
        mesh.CombineMeshes(combine);
        mesh = Utility.FilterDirrectedPolygons(mesh, 45.0f);

        if (reverse)
            mesh = Utility.InvertNormals(mesh);
        return mesh;
    }

    public GameObject MakeShadows_(bool reverse = false)
    {
        var filters = new MyList<MeshFilter>();
        var parent = transform.parent;
        FindMeshFiltersRecurse(parent, ref filters);

        var mesh = CombineMeshes(filters, reverse: reverse);
        var shadow = new GameObject("ShadowSurface");
        shadow.layer = LayerMask.NameToLayer("Shadow");
        shadow.transform.SetParent(this.transform);
        shadow.transform.localPosition = Vector3.zero;
        shadow.transform.localRotation = Quaternion.identity;
        shadow.transform.localScale = Vector3.one;

        var mesh_filter = shadow.AddComponent<MeshFilter>();
        mesh_filter.sharedMesh = mesh;

        var mesh_renderer = shadow.AddComponent<MeshRenderer>();
        mesh_renderer.material = MaterialKeeper.Instance.GetMaterial("ShadowWallMaterial");
        return shadow;
    }

    public GameObject MakeShadowsReversed_()
    {
        return MakeShadows_(true);
    }

    [ContextMenu("Make Shadows Reversed")]
    public GameObject MakeShadowsReversed()
    {
        return MakeShadowsReversed_();
    }

    [ContextMenu("Make Shadows")]
    public GameObject MakeShadows()
    {
        return MakeShadows_();
    }
}
