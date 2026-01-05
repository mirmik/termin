using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;
#if UNITY_64
using Unity.AI.Navigation;
#endif

public class NavMeshSurfaceParter : MonoBehaviour
{
    void Start() { }

    GameObject MakeOrientShadow(Quaternion q, int area = 0, string name = "Shadow")
    {
        var shadow_go = new GameObject(name);
        shadow_go.layer = (int)Layers.SHADOW_LAYER;
        shadow_go.transform.SetParent(transform);
        shadow_go.transform.localPosition = Vector3.zero;
        shadow_go.transform.localRotation = q;
        shadow_go.transform.localScale = Vector3.one;
        var shadow = shadow_go.AddComponent<NavMeshSurfaceShadow>();

        var surface = shadow_go.AddComponent<NavMeshSurface>();
        surface.collectObjects = CollectObjects.Children;
        surface.agentTypeID = GameCore.GetNavMeshAgentID("Short").Value;
        surface.defaultArea = area;

        var material = MaterialKeeper.Instance.GetMaterial("ShadowWallMaterial");
        return shadow_go;
    }

    [ContextMenu("Make Wall Shadow Meshes")]
    void MakeOrientedShadowMeshes()
    {
        CleanAllShadowWalls();

        Quaternion a = Quaternion.Euler(0, 0, 90);
        Quaternion b = Quaternion.Euler(0, 0, -90);
        Quaternion c = Quaternion.Euler(90, 0, 0);
        Quaternion d = Quaternion.Euler(-90, 0, 0);

        var pab = GameCore.FindInParentTree<PlatformAreaBase>(gameObject);
        var gravity = pab.GetGravity(transform.position);
        var gmagnitude = gravity.magnitude;
        int area =
            gmagnitude < 1.0 ? (int)Areas.WALLS_FOR_ZERO_GRAVITY_AREA : (int)Areas.WALLS_AREA;

        var name = "ShadowWall";
        MakeOrientShadow(a, area, name);
        MakeOrientShadow(b, area, name);
        MakeOrientShadow(c, area, name);
        MakeOrientShadow(d, area, name);
    }

    [ContextMenu("Make Bottom Oriented Shadow Mesh")]
    void MakeBottomOrientedShadowMesh()
    {
        Quaternion a = Quaternion.Euler(0, 0, 180);
        MakeOrientShadow(a, area: (int)Areas.BOTTOM_AREA);
    }

    GameObject MakeBottomOrientedShadowMesh_()
    {
        Quaternion a = Quaternion.Euler(0, 0, 180);
        return MakeOrientShadow(a, area: (int)Areas.BOTTOM_AREA, "ShadowBottom");
    }

    [ContextMenu("Make Bottom Oriented Layer Automatic")]
    void MakeBottomOrientedLayerAutomatic()
    {
        var go = MakeBottomOrientedShadowMesh_();

        var shadow = go.GetComponent<NavMeshSurfaceShadow>();
        shadow.UseBottomLayerMarks = false;

        var s = shadow.MakeShadows_();
        var sr = shadow.MakeShadowsReversed_();

        s.layer = 26;
        sr.layer = 26;

        //set materials
        var material = MaterialKeeper.Instance.GetMaterial("ShadowDemonstrator");
        s.GetComponent<MeshRenderer>().material = material;
        sr.GetComponent<MeshRenderer>().material = material;

        // add mesh colliders
        s.AddComponent<MeshCollider>();
        sr.AddComponent<MeshCollider>();
    }

    void CleanAllShadowWalls()
    {
        MyList<GameObject> to_destroy = new MyList<GameObject>();
        foreach (Transform child in transform)
        {
            var name = child.gameObject.name;
            if (name == "ShadowWall")
            {
                to_destroy.Add(child.gameObject);
            }
        }

        foreach (var go in to_destroy)
        {
            GameObject.DestroyImmediate(go);
        }

        // set scene dirty
#if UNITY_EDITOR
        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(gameObject.scene);
#endif
    }

    [ContextMenu("Make Wall Shadow Meshes Automatic")]
    void MakeOrientedShadowMeshesAutomatic()
    {
        CleanAllShadowWalls();
        MakeOrientedShadowMeshes();

        foreach (Transform child in transform)
        {
            var name = child.gameObject.name;
            if (name == "ShadowWall")
            {
                var shadow = child.gameObject.GetComponent<NavMeshSurfaceShadow>();
                shadow.UseBottomLayerMarks = false;
                var s = shadow.MakeShadows_();

                s.AddComponent<MeshCollider>();

                s.layer = 31;

                var mesh_surface = child.gameObject.GetComponent<NavMeshSurface>();
                mesh_surface.BuildNavMesh();
            }
        }
    }
}
