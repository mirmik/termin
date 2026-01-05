using System.Collections;
using System.Collections.Generic;
using System.Linq;

#if UNITY_64
using UnityEngine;
using UnityEngine.AI;
using Unity.AI.Navigation;
#endif

public class NavMeshSurfaceDrawer : MonoBehaviour
{
    //NavMeshSurface navMeshSurface;

    MyList<OnBottomMove> onBottomMoveList = new MyList<OnBottomMove>();

    NavMeshSurface[] GetNavMeshSurfaces()
    {
        return GameObject.FindObjectsByType<NavMeshSurface>(FindObjectsSortMode.None);
    }

    void TransformVerticesToLocalSpace(Mesh mesh, Transform transform)
    {
        Vector3[] vertices = mesh.vertices;
        for (int i = 0; i < vertices.Length; i++)
        {
            vertices[i] = transform.InverseTransformPoint(vertices[i]);
        }
        mesh.vertices = vertices;

        // recalculate normals
        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
    }

    public string info()
    {
        return "NOINFO";
    }

    MyList<OnBottomMove> GetOnBottomMoveList()
    {
        if (onBottomMoveList.Count == 0)
        {
            onBottomMoveList = GameCore.GetChildrenComponentsRecurse<OnBottomMove>(gameObject);
        }
        return onBottomMoveList;
    }

    NavMeshDataInstance onBottomMoveNavMeshDataInstance;

    void MakeOnBottomMoveListNavMeshSurface()
    {
        if (onBottomMoveList.Count == 0)
        {
            return;
        }

        List<NavMeshBuildSource> navMeshDataSources = new List<NavMeshBuildSource>();

        foreach (var onBottomMove in onBottomMoveList)
        {
            var source = onBottomMove.CreateNavMeshSource();
            navMeshDataSources.Add(source);
        }

        // bottom rotation
        Quaternion bottomRotation = Quaternion.Euler(0, 0, 180);

        NavMeshData onBottomMoveNavMeshData = NavMeshBuilder.BuildNavMeshData(
            NavMesh.GetSettingsByIndex(2),
            navMeshDataSources,
            new Bounds(Vector3.zero, new Vector3(10000, 10000, 10000)),
            Vector3.zero,
            bottomRotation
        );

        onBottomMoveNavMeshDataInstance = NavMesh.AddNavMeshData(onBottomMoveNavMeshData);

        // Debug.Log("onBottomMoveNavMeshDataInstance: " +
        // 	onBottomMoveNavMeshDataInstance.valid);
    }

    [ContextMenu("CreateBottomMoveNavMeshSurface")]
    public void CreateBottomMoveNavMeshSurface()
    {
        if (onBottomMoveNavMeshDataInstance.valid)
        {
            NavMesh.RemoveNavMeshData(onBottomMoveNavMeshDataInstance);
        }

        GetOnBottomMoveList();
        MakeOnBottomMoveListNavMeshSurface();
    }

    // public void Init()
    // {
    // 	navMeshSurface = GetComponent<NavMeshSurface>();

    // 	// try {
    // 	// 	CreateMeshOfSubobjects(navMeshSurface);
    // 	// }
    // 	// catch (System.Exception e) {
    // 	// 	Debug.Log("NavMeshSurfaceDrawer.Init: " + e.Message);
    // 	// }

    // 	GetOnBottomMoveList();
    // 	MakeOnBottomMoveListNavMeshSurface();
    // }


#if UNITY_EDITOR


    [ContextMenu("RemoveMesh")]
    public void RemoveMesh()
    {
        var navMeshDrawObject = transform.Find("NavMeshDrawObjectExperimental");
        if (navMeshDrawObject != null)
        {
            GameObject.DestroyImmediate(navMeshDrawObject.gameObject);
        }
    }

    [ContextMenu("CreateNavigateMesh")]
    public void CreateNavigateMesh()
    {
        RemoveMesh();
        CreateMeshOfSubobjects(this.gameObject);

        // set dirty
        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(
            UnityEditor.SceneManagement.EditorSceneManager.GetActiveScene()
        );
    }

    // [ContextMenu("CreateNavigateMeshFromPlatformBase")]
    // public void CreateNavigateMeshFromPlatformBase()
    // {
    // 	var platform_area_base = GetComponent<PlatformAreaBase>();
    // 	var surfaces = platform_area_base.GetSurfaces();

    // }



    public void CreateMeshOfSubobjects(GameObject baseobj, Material material = null)
    {
        if (material == null)
        {
            material = MaterialKeeper.Instance.GetMaterial("FOVMaterial");
        }

        GameObject navMeshDrawObject = new GameObject("NavMeshDrawObjectExperimental");
        navMeshDrawObject.transform.parent = transform;
        navMeshDrawObject.layer = LayerMask.NameToLayer("FieldOfView");
        // get all subobjects on layer 6 and 0
        var objs = baseobj.GetComponentsInChildren<MeshRenderer>();
        var solid_objs = new MyList<MeshRenderer>();
        foreach (var obj in objs)
        {
            var layer = obj.gameObject.layer;
            if (layer == 0 || layer == 6)
            {
                solid_objs.Add(obj);
            }
        }

        var s = solid_objs[0];

        // print all uvs of the first object
        foreach (var uv in s.GetComponent<MeshFilter>().sharedMesh.uv2)
        {
            Debug.Log("uv: " + uv);
        }

        //return;

        Mesh combinedMesh = new Mesh();

        CombineInstance[] combine = new CombineInstance[solid_objs.Count];
        for (int i = 0; i < solid_objs.Count; i++)
        {
            var mesh = solid_objs[i].GetComponent<MeshFilter>().sharedMesh;

            // make mesh copy
            mesh = Instantiate(mesh);

            //TransformVerticesToLocalSpace(mesh, solid_objs[i].transform);
            combine[i] = new CombineInstance()
            {
                mesh = mesh,
                transform = solid_objs[i].transform.localToWorldMatrix
            };
        }
        combinedMesh.CombineMeshes(combine);

        navMeshDrawObject.AddComponent<MeshFilter>().mesh = combinedMesh;
        navMeshDrawObject.AddComponent<MeshRenderer>().material = material;
        var navMeshRenderer_helper = navMeshDrawObject.AddComponent<NavMeshRender>();

        // add collider
        var meshCollider = navMeshDrawObject.AddComponent<MeshCollider>();
        meshCollider.sharedMesh = combinedMesh;

        //navMeshDrawObject.AddComponent<BSPTree>();
        //navMeshDrawObject.AddComponent<MeshAnalyzeMonoBeh>();

        // set it dirty
        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(
            UnityEditor.SceneManagement.EditorSceneManager.GetActiveScene()
        );
    }
#endif

    [ContextMenu("CreateLinksForAll_MeshAnalyze")]
    public void CreateLinksForAll_MeshAnalyze()
    {
        var meshAnalyzeList = GameCore.GetChildrenComponentsRecurse<MeshAnalyzeMonoBeh>(gameObject);
        foreach (var meshAnalyze in meshAnalyzeList)
        {
            meshAnalyze.FullProgram();
        }
    }

    [ContextMenu("CreateLeansForAll_MeshAnalyze")]
    public void CreateLeansForAll_MeshAnalyze()
    {
        var meshAnalyzeList = GameCore.GetChildrenComponentsRecurse<MeshAnalyzeMonoBeh>(gameObject);
        foreach (var meshAnalyze in meshAnalyzeList)
        {
            try
            {
                meshAnalyze.MakeLeanZones();
            }
            catch (System.Exception e)
            {
                Debug.Log("CreateLeansForAll_MeshAnalyze: " + e.Message);
            }
        }
    }
}
