using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;

public class ClimbingWalls : MonoBehaviour
{
    MeshRenderer _mesh_renderer;
    MeshFilter _mesh_filter;
    Mesh mesh;
    MyList<Vector3> _unical_normals = new MyList<Vector3>();
    MyList<NavMeshDataInstance> _nav_mesh_data_instances = new MyList<NavMeshDataInstance>();

    public float VoxelSize = 0.1f;

    public long HashOfVector(Vector3 vector)
    {
        long hash = 0;
        hash = hash * 31 + vector.x.GetHashCode();
        hash = hash * 31 + vector.y.GetHashCode();
        hash = hash * 31 + vector.z.GetHashCode();
        return hash;
    }

    void Init()
    {
        _mesh_renderer = GetComponent<MeshRenderer>();
        _mesh_filter = GetComponent<MeshFilter>();

        var vertices = _mesh_filter.sharedMesh.vertices;
        var triangles = _mesh_filter.sharedMesh.triangles;

        mesh = new Mesh();
        mesh.vertices = vertices;
        mesh.triangles = triangles;

        mesh.RecalculateNormals();
        mesh.RecalculateBounds();
    }

    // Start is called before the first frame update
    void Start()
    {
        //Init();
        //MakeWalls();
    }

    // Update is called once per frame
    void Update() { }

    void FindNormals()
    {
        _unical_normals.Clear();
        var normals = mesh.normals;

        for (int i = 0; i < normals.Length; i++)
        {
            var normal = normals[i];
            bool is_unical = true;
            foreach (var unical_normal in _unical_normals)
            {
                var distance = Vector3.Distance(normal, unical_normal);
                if (distance < 0.01f)
                {
                    is_unical = false;
                    break;
                }
            }
            if (is_unical)
                _unical_normals.Add(normal);
        }
    }

    public void MakeWalls()
    {
        FindNormals();
        foreach (var normal in _unical_normals)
        {
            if (Mathf.Abs(normal.y) > 0.01f)
                continue;

            Quaternion q = Quaternion.FromToRotation(Vector3.up, normal);

            List<NavMeshBuildSource> sources = new List<NavMeshBuildSource>();
            sources.Add(
                new NavMeshBuildSource()
                {
                    component = _mesh_filter,
                    transform = transform.localToWorldMatrix,
                    area = 0, //Utility.WALLS_AREA,
                    shape = NavMeshBuildSourceShape.Mesh,
                    sourceObject = _mesh_filter.sharedMesh,
                }
            );

            var settings = NavMesh.GetSettingsByIndex(0);
            settings.overrideVoxelSize = true;
            settings.voxelSize = VoxelSize;

            NavMeshData nav_mesh_data = NavMeshBuilder.BuildNavMeshData(
                settings,
                sources,
                new Bounds(transform.position, Vector3.one * 1000),
                transform.position,
                q
            );

            var nav_mesh_data_instance = NavMesh.AddNavMeshData(nav_mesh_data);
            _nav_mesh_data_instances.Add(nav_mesh_data_instance);
        }
    }

    [ContextMenu("RemoveWalls")]
    public void RemoveWalls()
    {
        foreach (var nav_mesh_data_instance in _nav_mesh_data_instances)
        {
            NavMesh.RemoveNavMeshData(nav_mesh_data_instance);
        }
    }

    [ContextMenu("MakeWalls")]
    public void MakeWallsContextMenu()
    {
        if (_mesh_filter == null)
            Init();
        MakeWalls();
    }
}
