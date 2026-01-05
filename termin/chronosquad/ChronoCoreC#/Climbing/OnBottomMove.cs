using System.Collections;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
using UnityEngine.AI;
using Unity.AI.Navigation;
#endif

public class OnBottomMove : MonoBehaviour
{
    public NavMeshBuildSourceShape source_shape;

    public NavMeshBuildSource CreateNavMeshSource()
    {
        NavMeshBuildSource navMeshBuildSource = new NavMeshBuildSource();
        navMeshBuildSource.shape = source_shape;
        navMeshBuildSource.transform = transform.localToWorldMatrix;
        navMeshBuildSource.area = 0;

        if (source_shape == NavMeshBuildSourceShape.Mesh)
        {
            MeshFilter meshFilter = GetComponent<MeshFilter>();
            if (meshFilter != null)
                navMeshBuildSource.sourceObject = meshFilter.sharedMesh;
        }
        else
        {
            navMeshBuildSource.sourceObject = gameObject;
        }

        if (source_shape == NavMeshBuildSourceShape.Box)
            navMeshBuildSource.size = transform.localScale;
        return navMeshBuildSource;
    }
}
