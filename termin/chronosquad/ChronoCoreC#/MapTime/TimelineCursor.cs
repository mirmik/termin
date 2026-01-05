#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;

class TimelineCursor : MonoBehaviour
{
    MeshRenderer _timeline_cursor_mesh_renderer;
    MeshFilter _timeline_cursor_mesh_filter;

    void Start()
    {
        _timeline_cursor_mesh_filter = gameObject.AddComponent<MeshFilter>();
        _timeline_cursor_mesh_renderer = gameObject.AddComponent<MeshRenderer>();

        Mesh mesh = new Mesh();

        var vertices = new MyList<Vector3>();
        var indices = new MyList<int>();
        var normals = new MyList<Vector3>();

        // circle mesh
        int segments = 100;

        float radius = 30.0f;
        for (int i = 0; i < segments; i++)
        {
            float angle = 2 * Mathf.PI * i / segments;
            float x = radius * Mathf.Cos(angle);
            float y = radius * Mathf.Sin(angle);
            vertices.Add(new Vector3(x, y, 0));
            normals.Add(new Vector3(0, 0, 1));
        }

        Vector3 center = new Vector3(0, 0, 0);
        vertices.Add(center);
        normals.Add(new Vector3(0, 0, 1));

        for (int i = 0; i < segments - 1; i++)
        {
            indices.Add(i + 1);
            indices.Add(i);
            indices.Add(segments); // center
        }

        indices.Add(0);
        indices.Add(segments - 1);
        indices.Add(segments); // center

        mesh.vertices = vertices.ToArray();
        mesh.normals = normals.ToArray();
        mesh.SetIndices(indices.ToArray(), MeshTopology.Triangles, 0);

        _timeline_cursor_mesh_filter.mesh = mesh;

        gameObject.layer = 15;
    }

    public void SetPosition(Vector3 position)
    {
        transform.position = position;
    }
}
