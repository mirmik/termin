#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;

class ArrowMeshObject
{
    Mesh mesh = new Mesh();
    GameObject gameObject;

    //bool _dash_style = false;
    MeshFilter mf;

    Material material;
    float zlevel = 0.1f;

    Vector3 start;
    Vector3 finish;

    Vector3 start_a;
    Vector3 start_b;
    Vector3 finish_a;
    Vector3 finish_b;

    float width = 20f;

    public ArrowMeshObject(GameObject canvas)
    {
        gameObject = new GameObject("ArrowMeshObject");
        gameObject.layer = 15;
        mf = gameObject.AddComponent<MeshFilter>();
        mf.mesh = mesh;
        material = new Material(Shader.Find("Unlit/TimeLineShader"));
        // material =  Resources.Load<Material>("ChronoShpere/AAA");
        gameObject.AddComponent<MeshRenderer>().material = material;
        gameObject.transform.parent = canvas.transform;
        gameObject.transform.localPosition = new Vector3(0, 0, 0);

        UpdateMesh();

        UpdateParameters(new Rect(0, 0, 1800, 1800));
    }

    public void SetWidth(float w)
    {
        width = w;
        //UpdateMesh();
    }

    Vector3[] arr = new Vector3[4];
    int[] triangles = new int[6];
    Vector3[] normals = new Vector3[4];

    void UpdateMesh()
    {
        var diff = finish - start;
        var normal = new Vector3(-diff.y, diff.x, 0).normalized;

        start_a = start + normal * width;
        start_b = start - normal * width;
        finish_a = finish + normal * width;
        finish_b = finish - normal * width;

        start_a.z = zlevel;
        start_b.z = zlevel;
        finish_a.z = zlevel;
        finish_b.z = zlevel;

        // TODO: Is it need?
        arr[0] = start_a;
        arr[1] = start_b;
        arr[2] = finish_a;
        arr[3] = finish_b;

        mesh.vertices = arr;
        mf.mesh = mesh;

        triangles[0] = 0;
        triangles[1] = 2;
        triangles[2] = 1;
        triangles[3] = 1;
        triangles[4] = 2;
        triangles[5] = 3;

        normals[0] = Vector3.up;
        normals[1] = Vector3.up;
        normals[2] = Vector3.up;
        normals[3] = Vector3.up;

        //mesh.vertices = vertices.ToArray();
        mesh.triangles = triangles;
        mesh.normals = normals;
    }

    public Vector2 FindNearest(Vector2 pnt)
    {
        var start = new Vector2(this.start.x, this.start.y);
        var finish = new Vector2(this.finish.x, this.finish.y);
        var line = finish - start;
        var len = line.magnitude;
        var dir = line / len;
        var normal = new Vector2(-dir.y, dir.x);
        var p = pnt - start;
        var proj = Vector2.Dot(p, dir);
        //var perp = Vector2.Dot(p, normal);
        if (proj < 0)
            return start;
        if (proj > len)
            return finish;
        return start + dir * proj;
    }

    public float DistanceTo(Vector2 vec)
    {
        var nearest = FindNearest(vec);
        return (vec - nearest).magnitude;
    }

    public void SetPoints(Vector3 s, Vector3 f)
    {
        start = s;
        finish = f;
        UpdateMesh();
    }

    public void SetIsCurrent(bool is_current)
    {
        material.SetInt("IsCurrent", is_current ? 1 : 0);
    }

    public void UpdateParameters(Rect viewrect)
    {
        //SetPoints( new Vector3(0, 0, 60.0f), new Vector3(1800, 1800, 60.0f) );

        // material.SetInt("Dash", _dash_style ? 1 : 0);
        // material.SetFloat("DashSize", 0.5f);
        // material.SetVector("Center", new Vector4(0, 0, 0, 0));
        // material.SetVector(
        // 	"lrtb",
        // 	new Vector4(
        // 		viewrect.x,
        // 		viewrect.y,
        // 		viewrect.x + viewrect.width,
        // 		viewrect.y + viewrect.height
        // 	)
        // );
    }
}
