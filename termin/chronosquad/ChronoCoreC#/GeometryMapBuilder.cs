using System.Collections.Generic;
using UnityEngine;
using System.Text;
using System;
using System.IO;

#if UNITY_EDITOR
using UnityEditor;
#endif

public class GeometryMapBuilder
{
    Mesh mesh;
    Texture2D texture;
    Vector3[,] array;
    Vector3 minval;
    Vector3 maxval;

    public GeometryMapBuilder(Mesh mesh, int width, int height)
    {
        this.mesh = mesh;
        texture = new Texture2D(width, height, TextureFormat.RGBAFloat, false);
        array = new Vector3[width, height];
        for (int x = 0; x < width; x++)
        {
            for (int y = 0; y < height; y++)
            {
                // nan
                array[x, y] = new Vector3(float.NaN, float.NaN, float.NaN);
            }
        }

        var vertices = mesh.vertices;
        for (int i = 0; i < vertices.Length; i++)
        {
            var v = vertices[i];
            minval.x = Mathf.Min(minval.x, v.x);
            minval.y = Mathf.Min(minval.y, v.y);
            minval.z = Mathf.Min(minval.z, v.z);
            maxval.x = Mathf.Max(maxval.x, v.x);
            maxval.y = Mathf.Max(maxval.y, v.y);
            maxval.z = Mathf.Max(maxval.z, v.z);
        }
    }

    public void BuildTexture()
    {
        FillIn();
    }

    void FillIn()
    {
        var uvs = mesh.uv;

        if (mesh.uv2 != null && mesh.uv2.Length > 0)
        {
            uvs = mesh.uv2;
        }

        for (int triangleIndex = 0; triangleIndex < mesh.triangles.Length; triangleIndex += 3)
        {
            int a = mesh.triangles[triangleIndex];
            int b = mesh.triangles[triangleIndex + 1];
            int c = mesh.triangles[triangleIndex + 2];

            Vector2 a_uv = uvs[a];
            Vector2 b_uv = uvs[b];
            Vector2 c_uv = uvs[c];

            Vector3 a_vertex = mesh.vertices[a];
            Vector3 b_vertex = mesh.vertices[b];
            Vector3 c_vertex = mesh.vertices[c];

            FillTriangle(a_uv, b_uv, c_uv, a_vertex, b_vertex, c_vertex);
        }
    }

    Vector2Int GetTextureCoord(Vector2 uv)
    {
        return new Vector2Int((int)(uv.x * texture.width), (int)(uv.y * texture.height));
    }

    static public bool PointInTriangle(Vector2 a, Vector2 b, Vector2 c, Vector2 p)
    {
        float s = a.y * c.x - a.x * c.y + (c.y - a.y) * p.x + (a.x - c.x) * p.y;
        float t = a.x * b.y - a.y * b.x + (a.y - b.y) * p.x + (b.x - a.x) * p.y;

        if ((s < 0) != (t < 0))
            return false;

        float A = -b.y * c.x + a.y * (c.x - b.x) + a.x * (b.y - c.y) + b.x * c.y;

        return A < 0 ? (s <= 0 && s + t >= A) : (s >= 0 && s + t <= A);
    }

    void FillTriangle(
        Vector2 a_uv,
        Vector2 b_uv,
        Vector2 c_uv,
        Vector3 a_vertex,
        Vector3 b_vertex,
        Vector3 c_vertex
    )
    {
        Vector2 max = new Vector2(
            Mathf.Max(a_uv.x, b_uv.x, c_uv.x),
            Mathf.Max(a_uv.y, b_uv.y, c_uv.y)
        );
        Vector2 min = new Vector2(
            Mathf.Min(a_uv.x, b_uv.x, c_uv.x),
            Mathf.Min(a_uv.y, b_uv.y, c_uv.y)
        );

        Vector2Int maxCoord = GetTextureCoord(max);
        Vector2Int minCoord = GetTextureCoord(min);
        for (int x = minCoord.x; x < maxCoord.x; x++)
        {
            for (int y = minCoord.y; y < maxCoord.y; y++)
            {
                Vector2 uv = new Vector2(x / (float)texture.width, y / (float)texture.height);
                if (PointInTriangle(a_uv, b_uv, c_uv, uv))
                {
                    //Debug.Log("Point in triangle " + uv);
                    // X = A^(-1) * U
                    Matrix3x3 A = new Matrix3x3(
                        a_uv.x,
                        b_uv.x,
                        c_uv.x,
                        a_uv.y,
                        b_uv.y,
                        c_uv.y,
                        1,
                        1,
                        1
                    );
                    var inv_A = A.Inverse();
                    Vector3 U = new Vector3(uv.x, uv.y, 1);
                    Vector3 baricentric = inv_A * U;

                    var v =
                        baricentric.x * a_vertex
                        + baricentric.y * b_vertex
                        + baricentric.z * c_vertex;

                    v.x = (v.x - minval.x) / (maxval.x - minval.x);
                    v.y = (v.y - minval.y) / (maxval.y - minval.y);
                    v.z = (v.z - minval.z) / (maxval.z - minval.z);

                    texture.SetPixel(x, y, new Color(v.x, v.y, v.z, 1));
                }
            }
        }
    }

    public void SaveTextureToFile(string path)
    {
        byte[] bytes = texture.EncodeToPNG();
        File.WriteAllBytes(path, bytes);
    }

    public void SaveScaleToFile(string path)
    {
        var g = System.Globalization.CultureInfo.InvariantCulture;
        var min = minval;
        var max = maxval;
        var scale =
            min.x.ToString(g)
            + ","
            + min.y.ToString(g)
            + ","
            + min.z.ToString(g)
            + "\n"
            + max.x.ToString(g)
            + ","
            + max.y.ToString(g)
            + ","
            + max.z.ToString(g);
        File.WriteAllText(path, scale);
    }

    public static Texture2D LoadTextureFromFile(string path)
    {
        var texture = new Texture2D(1024, 1024);
        var bytes = System.IO.File.ReadAllBytes(path);
        texture.LoadImage(bytes);
        return texture;
    }

    public struct MinMaxScale
    {
        public Vector3 min;
        public Vector3 max;

        public MinMaxScale(Vector3 min, Vector3 max)
        {
            this.min = min;
            this.max = max;
        }
    }

    public static MinMaxScale LoadScaleFromFile(string path)
    {
        var bytes = System.IO.File.ReadAllBytes(path);
        var scale = System.Text.Encoding.UTF8.GetString(bytes);
        var parts = scale.Split('\n');
        var minval = parts[0].Split(',');
        var maxval = parts[1].Split(',');
        Debug.Log("Min: " + minval[0] + " " + minval[1] + " " + minval[2]);
        Debug.Log("Max: " + maxval[0] + " " + maxval[1] + " " + maxval[2]);
        var g = System.Globalization.CultureInfo.InvariantCulture;
        return new MinMaxScale(
            new Vector3(
                float.Parse(minval[0], g),
                float.Parse(minval[1], g),
                float.Parse(minval[2], g)
            ),
            new Vector3(
                float.Parse(maxval[0], g),
                float.Parse(maxval[1], g),
                float.Parse(maxval[2], g)
            )
        );
    }

    static List<GameObject> FindAllObjectsWithMeshes()
    {
        var all_objects = GameObject.FindObjectsByType<GameObject>(FindObjectsSortMode.None);
        var meshes = new List<GameObject>();
        foreach (var obj in all_objects)
        {
            if (obj.layer != 0)
            {
                continue;
            }

            try
            {
                var renderer = obj.GetComponent<Renderer>();
                if (renderer == null)
                {
                    continue;
                }

                // is mesh filter exists
                var mesh_filter = obj.GetComponent<MeshFilter>();
                if (mesh_filter == null)
                {
                    continue;
                }

                meshes.Add(obj);
            }
            catch (System.Exception)
            {
                //Debug.Log("Error: " + e.Message);
            }
        }
        return meshes;
    }

    public static string IerarchyPath(GameObject obj)
    {
        var path = new StringBuilder();
        var parent = obj.transform.parent;
        while (parent != null)
        {
            path.Insert(0, parent.name + "_");
            parent = parent.parent;
        }
        path.Append(obj.name);
        return path.ToString();
    }

#if UNITY_EDITOR
    [MenuItem("Tools/Build Geometry Map")]
    static void BuildGeometryMap()
    {
        var mesh_objects = FindAllObjectsWithMeshes();
        //List<GameObject> mesh_objects = new List<GameObject>();
        // find object with name TestCube
        //GameObject gobj = GameObject.Find("TestCube");
        //mesh_objects.Add(gobj);

        var scene_name = UnityEditor.SceneManagement.EditorSceneManager.GetActiveScene().name;
        var dirpath = "Assets/StreamingAssets/GeometryMaps/" + scene_name + "/";
        if (!Directory.Exists(dirpath))
        {
            Directory.CreateDirectory(dirpath);
        }

        foreach (var obj in mesh_objects)
        {
            try
            {
                GeometryMapController controller = obj.GetComponent<GeometryMapController>();
                if (controller == null)
                {
                    continue;
                }

                // var count_of_triangles = obj.GetComponent<MeshFilter>().sharedMesh.triangles.Length / 3;
                // Debug.Log("Object: " + obj.name + " Triangles: " + count_of_triangles);
                // continue;

                var path = IerarchyPath(obj);

                var name = obj.name;
                var scale = obj.transform.localScale;
                var mesh = obj.GetComponent<MeshFilter>().sharedMesh;
                var builder = new GeometryMapBuilder(mesh, 1024, 1024);
                builder.BuildTexture();

                builder.SaveTextureToFile(
                    "Assets/StreamingAssets/GeometryMaps/" + scene_name + "/" + path + ".png"
                );
                builder.SaveScaleToFile(
                    "Assets/StreamingAssets/GeometryMaps/" + scene_name + "/" + path + ".scl"
                );
            }
            catch (System.Exception e)
            {
                Debug.Log("Error: " + e.Message);
            }
        }
    }
#endif
}
