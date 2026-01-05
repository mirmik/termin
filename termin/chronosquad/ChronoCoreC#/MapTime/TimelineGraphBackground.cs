#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;

class TimelineGraphBackground
{
    GameObject _timeline_map_background_object;
    MeshRenderer _timeline_map_background_mesh_renderer;
    MeshFilter _timeline_map_background_mesh_filter;

    Mesh _timeline_map_background_mesh;
    public Material backgoundmat;
    float bglevel = 0.2f;

    public TimelineGraphBackground(Transform canvas, Material backgoundmat)
    {
        this.backgoundmat = backgoundmat;
        SetupBackground(canvas);
    }

    public void SetupBackground(Transform canvas_transform)
    {
        _timeline_map_background_object = new GameObject("TimelineMapBackground");
        _timeline_map_background_object.transform.parent = canvas_transform;
        _timeline_map_background_object.layer = 15;
        _timeline_map_background_object.transform.SetParent(canvas_transform, false);
        _timeline_map_background_object.transform.localPosition = new Vector3(0, 0, 0);
        _timeline_map_background_mesh_renderer =
            _timeline_map_background_object.AddComponent<MeshRenderer>();
        _timeline_map_background_mesh_filter =
            _timeline_map_background_object.AddComponent<MeshFilter>();

        _timeline_map_background_mesh = new Mesh();
        _timeline_map_background_mesh_renderer.material = backgoundmat;

        var vertices = new MyList<Vector3>();
        var indices = new MyList<int>();
        var normals = new MyList<Vector3>();

        float llim = -1e10f;
        float rlim = 1e10f;
        var a = new Vector3(llim, llim, bglevel);
        var b = new Vector3(rlim, llim, bglevel);
        var c = new Vector3(llim, rlim, bglevel);
        var d = new Vector3(rlim, rlim, bglevel);

        var index = vertices.Count;
        vertices.Add(a);
        vertices.Add(b);
        vertices.Add(c);
        vertices.Add(d);

        indices.Add(index);
        indices.Add(index + 1);
        indices.Add(index + 2);

        indices.Add(index + 1);
        indices.Add(index + 2);
        indices.Add(index + 3);

        normals.Add(Vector3.up);
        normals.Add(Vector3.up);
        normals.Add(Vector3.up);
        normals.Add(Vector3.up);

        _timeline_map_background_mesh.vertices = vertices.ToArray();
        _timeline_map_background_mesh.triangles = indices.ToArray();
        _timeline_map_background_mesh.normals = normals.ToArray();

        _timeline_map_background_mesh_filter.mesh = _timeline_map_background_mesh;
    }
}
