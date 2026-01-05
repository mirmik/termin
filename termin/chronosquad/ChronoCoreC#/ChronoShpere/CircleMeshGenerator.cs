using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class CircleMeshGenerator : MonoBehaviour
{
    Mesh mesh;

    // Start is called before the first frame update
    void Start()
    {
        mesh = create_circle_mesh(1.0f);
        GetComponent<MeshFilter>().mesh = mesh;
    }

    Mesh create_circle_mesh(float radius)
    {
        Mesh mesh = new Mesh();
        MyList<Vector3> vertices = new MyList<Vector3>();
        MyList<int> triangles = new MyList<int>();

        int n = 32;
        float angle_step = 2 * Mathf.PI / n;
        float angle = 0;
        for (int i = 0; i < n; ++i)
        {
            float x = radius * Mathf.Cos(angle);
            float y = radius * Mathf.Sin(angle);
            vertices.Add(new Vector3(x, 0.3f, y));
            angle += angle_step;
        }

        for (int i = 0; i < n; ++i)
        {
            triangles.Add(i);
            triangles.Add(0);
            triangles.Add((i + 1) % n);
        }

        mesh.vertices = vertices.ToArray();
        mesh.triangles = triangles.ToArray();
        mesh.RecalculateNormals();
        return mesh;
    }

    // Update is called once per frame
    void Update() { }
}
