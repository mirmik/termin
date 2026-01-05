using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class PolygonsInspector : MonoBehaviour
{
    // editor menu item

    public struct MeshInfo
    {
        public Mesh mesh;
        public int polygons;
    }

    static public void DebugPrint(MeshInfo mesh_info)
    {
        Debug.Log($"Mesh {mesh_info.mesh.name} has {mesh_info.polygons} polygons");
    }

#if UNITY_EDITOR
    [UnityEditor.MenuItem("Tools/Instrument/ReportAboutPolygons")]
    static void ReportAboutPolygons()
    {
        MyList<MeshInfo> meshes = new MyList<MeshInfo>();
        var all_objects = GameObject.FindObjectsByType<GameObject>(FindObjectsSortMode.None);

        foreach (var go in all_objects)
        {
            var mesh_filter = go.GetComponent<MeshFilter>();
            if (mesh_filter != null)
            {
                var mesh = mesh_filter.sharedMesh;
                if (mesh != null)
                {
                    var polygons = mesh.triangles.Length / 3;
                    if (polygons < 1000)
                        continue;
                    meshes.Add(new MeshInfo { mesh = mesh, polygons = polygons });
                }
            }

            var skinned_mesh_renderer = go.GetComponent<SkinnedMeshRenderer>();
            if (skinned_mesh_renderer != null)
            {
                var mesh = skinned_mesh_renderer.sharedMesh;
                if (mesh != null)
                {
                    var polygons = mesh.triangles.Length / 3;
                    if (polygons < 1000)
                        continue;
                    meshes.Add(new MeshInfo { mesh = mesh, polygons = polygons });
                }
            }
        }

        // sort meshes by polygons
        meshes.Sort((a, b) => b.polygons.CompareTo(a.polygons));
        foreach (var mesh_info in meshes)
        {
            DebugPrint(mesh_info);
        }
    }
#endif
}
