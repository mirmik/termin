// using System.Collections;
// using System.Collections.Generic;
// using UnityEngine;

// public class VoxilizedField : MonoBehaviour
// {
//     //Vector3[,,] vectors;

//     BSPTree tree;

//     // public MyList<Mesh> CollectMeshes()
//     // {
//     //     var meshes = new MyList<Mesh>();
//     //     var surfaces = GetNavMeshSurfaces();
//     //     foreach (var surface in surfaces)
//     //     {
//     //         var mesh = CreateMeshFromCurrentTriangulation(surface);
//     //         meshes.Add(mesh);
//     //     }
//     //     return meshes;
//     // }

//     public Vector3 CalculateField(Vector3 point)
//     {
//         var nearest = tree.ClosestPointOn(point, 100.0f);
//         var diff = point - nearest;
//         var dist = diff.magnitude;
//         var unit = diff.normalized;

//         var power = 1.0f / dist;
//         var field = unit * power;

//         return field;
//     }

//     public MyList<Vector3> FieldPathFinding(Vector3 start, Vector3 end)
//     {
//         var path = new MyList<Vector3>();
//         var current = start;
//         var step = 0.1f;

//         while (current != end)
//         {
//             var to_target = end - current;
//             var field = CalculateField(current);

//             var sum = field + to_target;
//             var next = current + sum * step;
//             path.Add(next);
//             current = next;
//         }

//         return path;
//     }

//     // void DoVoxelization()
//     // {
//     //     var bounds = new Bounds();
//     //     var meshes = CollectMeshes();

//     //     foreach (var mesh in meshes)
//     //     {
//     //         bounds.Encapsulate(mesh.bounds);
//     //     }

//     //     float step = 1.0f;

//     //     var size = bounds.size;
//     //     var min = bounds.min;
//     //     var max = bounds.max;

//     //     int x = (int)(size.x / step);
//     //     int y = (int)(size.y / step);
//     //     int z = (int)(size.z / step);

//     //     vectors = new Vector3[x, y, z];


//     // }

// }
