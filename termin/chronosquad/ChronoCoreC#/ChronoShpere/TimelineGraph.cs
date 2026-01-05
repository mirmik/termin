// using UnityEngine;
// using System.Collections.Generic;

// // using pool
// using UnityEngine.Pool;

// class ArrowMeshObject
// {
//     Mesh mesh;
//     GameObject gameObject;

//     Vector3 start_a;
//     Vector3 start_b;
//     Vector3 finish_a;
//     Vector3 finish_b;

//     float width = 0.1f;

//     public ArrowMeshObject()
//     {
//         mesh = new Mesh();
//         mesh.MarkDynamic();

//         gameObject = new GameObject("ArrowMeshObject");
//         gameObject.AddComponent<MeshFilter>().mesh = mesh;
//         gameObject.AddComponent<MeshRenderer>().material = new Material(
//             Shader.Find("Unlit/TimeLineShader")
//         );

//         start_a = new Vector3(0, 0, 0);
//         start_b = new Vector3(0, 0, 0);
//         finish_a = new Vector3(0, 0, 0);
//         finish_b = new Vector3(0, 0, 0);

//         var vertices = new MyList<Vector3>();
//         var indices = new MyList<int>();
//         var normals = new MyList<Vector3>();

//         vertices.Add(start_a);
//         vertices.Add(start_b);
//         vertices.Add(finish_a);
//         vertices.Add(finish_b);

//         indices.Add(0);
//         indices.Add(1);
//         indices.Add(2);
//         indices.Add(0);
//         indices.Add(2);
//         indices.Add(3);

//         normals.Add(Vector3.up);
//         normals.Add(Vector3.up);
//         normals.Add(Vector3.up);
//         normals.Add(Vector3.up);

//         mesh.vertices = vertices.ToArray();
//         mesh.triangles = indices.ToArray();
//         mesh.normals = normals.ToArray();
//     }

//     public void SetPoints(Vector3 s, Vector3 f)
//     {
//         var diff = f - s;
//         var normal = new Vector3(-diff.y, diff.x, 0).normalized;

//         start_a = s + normal * width;
//         start_b = s - normal * width;
//         finish_a = f + normal * width;
//         finish_b = f - normal * width;

//         // TODO: Is it need?
//         mesh.vertices = new Vector3[] { start_a, start_b, finish_a, finish_b };
//     }
// }

// class TimelineGraphDraw
// {
//     ITimeline tl;
//     ArrowMeshObject arrowMeshObject;
//     ArrowMeshObject sub_arrowMeshObject;

//     float level;

//     public TimelineGraphDraw(ITimeline tl)
//     {
//         this.tl = tl;
//         arrowMeshObject = new ArrowMeshObject();
//         //sub_arrowMeshObject = new ArrowMeshObject();
//     }

//     public SetLevel(float val)
//     {
//         level = val;
//     }

//     public UpdateCoordinates(float left, float right)
//     {
//         arrowMeshObject.SetPoints(new Vector3(left, level, 0), new Vector3(right, level, 0));
//     }
// }

// class TimelineGraphBackground
// {
//     GameObject _timeline_map_background_object;
//     MeshRenderer _timeline_map_background_mesh_renderer;
//     MeshFilter _timeline_map_background_mesh_filter;
//     Mesh _timeline_map_background_mesh;

//     public TimelineGraphBackground()
//     {
//         SetupBackground();
//     }

//     public void SetupBackground()
//     {
//         _timeline_map_background_object = new GameObject("TimelineMapBackground");
//         _timeline_map_background_object.layer = 15;
//         _timeline_map_background_object.transform.SetParent(this.transform, false);
//         _timeline_map_background_mesh_renderer =
//             _timeline_map_background_object.AddComponent<MeshRenderer>();
//         _timeline_map_background_mesh_filter =
//             _timeline_map_background_object.AddComponent<MeshFilter>();
//         _timeline_map_background_mesh = new Mesh();
//         _timeline_map_background_mesh_filter.mesh = _timeline_map_background_mesh;
//         _timeline_map_background_mesh_renderer.material = backgoundmat;

//         // add two triangles to background
//         var vertices = new MyList<Vector3>();
//         var indices = new MyList<int>();
//         var normals = new MyList<Vector3>();

//         var a = new Vector3(-1, -1, bglevel);
//         var b = new Vector3(1, -1, bglevel);
//         var c = new Vector3(1, 1, bglevel);
//         var d = new Vector3(-1, 1, bglevel);

//         var index = vertices.Count;
//         vertices.Add(a);
//         vertices.Add(b);
//         vertices.Add(c);
//         vertices.Add(d);

//         indices.Add(index);
//         indices.Add(index + 1);
//         indices.Add(index + 2);

//         indices.Add(index);
//         indices.Add(index + 2);
//         indices.Add(index + 3);

//         normals.Add(Vector3.up);
//         normals.Add(Vector3.up);
//         normals.Add(Vector3.up);
//         normals.Add(Vector3.up);

//         _timeline_map_background_mesh.Clear();
//         _timeline_map_background_mesh.vertices = vertices.ToArray();
//         _timeline_map_background_mesh.triangles = indices.ToArray();
//         _timeline_map_background_mesh.normals = normals.ToArray();
//     }
// }

// public class TimelineGraph : MonoBehaviour
// {
//     Camera cam;
//     public Material mat;
//     public Material backgoundmat;
//     MeshRenderer mr;
//     MeshFilter mf;
//     Mesh mesh;

//     ChronosphereController _chronosquad_controller;

//     TimelineGraphBackground timelineGraphBackground;

//     float aspect_ratio = 1.0f;

//     float current_maximize_coef = 0;
//     float target_maximize_coef = 0;
//     bool _timeline_map_maximized = false;

//     GameObject _timeline_map_object;
//     IObjectPool<GraphLine> line_pool;
//     MyList<GraphLine> lines = new MyList<GraphLine>();

//     IObjectPool<GraphTriangle> triangle_pool;
//     MyList<GraphTriangle> triangles = new MyList<GraphTriangle>();
//     SimpleFilter filter;

//     Dictionary<string, TimelineGraphDraw> _timeline_graph_draws =
//         new Dictionary<string, TimelineGraphDraw>();

//     float bglevel = 0.5f;
//     float grlevel = 1.0f;

//     float width_per_2 = 0.004f;
//     float arrow_length = 0.05f;
//     float arrow_width_per_2 = 0.015f;

//     ChronoSphere ChronoSphere()
//     {
//         return _chronosquad_controller.ChronoSphere();
//     }

//     void Start()
//     {
//         _timeline_map_object = new GameObject("TimelineMap");
//         _timeline_map_object.layer = 15;
//         cam = this.GetComponent<Camera>();
//         mr = _timeline_map_object.AddComponent<MeshRenderer>();
//         mf = _timeline_map_object.AddComponent<MeshFilter>();
//         mesh = new Mesh();
//         mf.mesh = mesh;
//         mr.material = mat;

//         _timeline_map_object.transform.SetParent(this.transform, false);
//         _timeline_map_object.transform.localPosition = new Vector3(0, 1, 0);

//         filter = gameObject.GetComponent<SimpleFilter>();
//         _chronosquad_controller = GameObject
//             .Find("Timelines")
//             .GetComponent<ChronosphereController>();

//         line_pool = new ObjectPool<GraphLine>(() => new GraphLine(), (line) => { });

//         triangle_pool = new ObjectPool<GraphTriangle>(() => new GraphTriangle(), (triangle) => { });

//         aspect_ratio = (float)Screen.width / (float)Screen.height;

//         AddLine(new Vector3(0, 0.1f, 0), new Vector3(0.5f, 0.1f, 0), true);
//         AddLine(new Vector3(0.5f, 0.1f, 0), new Vector3(0.5f, 0.2f, 0), true);
//         AddLine(new Vector3(0.5f, 0.2f, 0), new Vector3(0.1f, 0.2f, 0), true);
//         AddLine(new Vector3(0.1f, 0.2f, 0), new Vector3(0.1f, 0.3f, 0), true);
//         AddLine(new Vector3(0.1f, 0.3f, 0), new Vector3(0.7f, 0.3f, 0), true);

//         AddLine(new Vector3(0.07f, 0.1f, 0), new Vector3(0.07f, 0.3f, 0), false);

//         //Maximize(false);
//         UpdateViewPort();

//         timelineGraphBackground = new TimelineGraphBackground();

//         UpdateTimelineDrawsObject();
//     }

//     void UpdateTimelineDrawsObject()
//     {
//         foreach (var ktl in _chronosquad_controller.ChronoSphere().Timelines())
//         {
//             var key = ktl.Key;
//             var tl = ktl.Value;

//             if (!_timeline_graph_draws.ContainsKey(key))
//             {
//                 _timeline_graph_draws[key] = new TimelineGraphDraw();
//             }
//         }
//     }

//     void UpdateTimelineDrawsCoordinates() { }

//     void AddLine(Vector3 start, Vector3 end, bool arrow = false)
//     {
//         // start.y = -start.y;
//         // end.y = -end.y;

//         //map 0..1 to -xw..xw
//         //map 0..1 to -yw..yw

//         float xw = 0.8f;
//         float yw = 0.8f;
//         start = new Vector3(start.x * xw * 2 - xw, start.y * yw * 2 - yw, start.z);
//         end = new Vector3(end.x * xw * 2 - xw, end.y * yw * 2 - yw, end.z);

//         //lines.Add(new GraphLine() { start = start, end = end, arrow = arrow });
//         var line = line_pool.Get();
//         line.start = start;
//         line.end = end;
//         line.arrow = arrow;
//         lines.Add(line);
//     }

//     GraphTriangle MakeTriangle(Vector3 a, Vector3 b, Vector3 c)
//     {
//         var tr = triangle_pool.Get();
//         tr.a = a;
//         tr.b = b;
//         tr.c = c;
//         return tr;
//     }

//     void CompileLineToTriangle(GraphLine line)
//     {
//         var diff = line.end - line.start;
//         var diffnorm = diff.normalized;
//         var dwp2 = diffnorm * width_per_2;
//         var x = diff.x;
//         var y = diff.y;

//         var norm = new Vector3(-y, x, 0);
//         var normalized = norm.normalized;
//         normalized = new Vector3(normalized.x, normalized.y * aspect_ratio, normalized.z);

//         var e = new Vector3(dwp2.x, dwp2.y * aspect_ratio, dwp2.z);
//         var e2 = new Vector3(diffnorm.x, diffnorm.y * aspect_ratio, diffnorm.z);

//         var ee = line.arrow ? -e2 * arrow_length : e;

//         var z = new Vector3(0, 0, grlevel);
//         var a = line.start + normalized * width_per_2 + z - e;
//         var b = line.start - normalized * width_per_2 + z - e;
//         var c = line.end + normalized * width_per_2 + z + ee;
//         var d = line.end - normalized * width_per_2 + z + ee;
//         triangles.Add(MakeTriangle(a, c, d));
//         triangles.Add(MakeTriangle(b, c, d));

//         if (line.arrow)
//         {
//             var arrow_a = line.end + z;
//             var arrow_b = line.end + z - e2 * arrow_length + normalized * arrow_width_per_2;
//             var arrow_c = line.end + z - e2 * arrow_length - normalized * arrow_width_per_2;
//             triangles.Add(MakeTriangle(arrow_a, arrow_b, arrow_c));
//         }
//     }

//     void ReevaluateMesh()
//     {
//         for (int i = 0; i < triangles.Count; i++)
//         {
//             triangle_pool.Release(triangles[i]);
//         }

//         triangles.Clear();
//         foreach (var line in lines)
//         {
//             CompileLineToTriangle(line);
//         }

//         var vertices = new MyList<Vector3>();
//         var indices = new MyList<int>();
//         var normals = new MyList<Vector3>();
//         var uvs = new MyList<Vector3>();

//         foreach (var triangle in triangles)
//         {
//             var index = vertices.Count;
//             vertices.Add(triangle.a);
//             vertices.Add(triangle.b);
//             vertices.Add(triangle.c);

//             indices.Add(index);
//             indices.Add(index + 1);
//             indices.Add(index + 2);

//             normals.Add(Vector3.up);
//             normals.Add(Vector3.up);
//             normals.Add(Vector3.up);
//         }

//         var new_mesh = new Mesh();

//         new_mesh.vertices = vertices.ToArray();
//         new_mesh.triangles = indices.ToArray();
//         new_mesh.normals = normals.ToArray();

//         var oldmesh = mf.mesh;
//         mf.mesh = new_mesh;

//         oldmesh.Clear();
//     }

//     void AddLinesFromChronosphere()
//     {
//         var tls = _chronosquad_controller.TimelineControllers();
//         for (int i = 0; i < tls.Count; i++)
//         {
//             AddLine(new Vector3(0, 0.1f * i, 0), new Vector3(0.5f, 0.1f * i, 0), true);
//             //AddLine(new Vector3(0, 0.5f + 0.1f * i, 0), new Vector3(0.5f, 0.5f+ 0.1f * i, 0), true);
//             // 	AddLine(new Vector3(0.5f, 0.1f * i, 0), new Vector3(0.5f, 0.1f * (i+1), 0), true);
//             // 	AddLine(new Vector3(0.0f, 0.1f * i, 0), new Vector3(0.0f, 0.1f * (i+1), 0), true);
//             // 	AddLine(new Vector3(0.25f, 0.1f * i, 0), new Vector3(0.25f, 0.1f * (i+1), 0), true);
//             // 	AddLine(new Vector3(0.1f, 0.1f * i, 0), new Vector3(0.1f, 0.1f * (i+1), 0), true);
//         }
//     }

//     void ClearLines()
//     {
//         foreach (var line in lines)
//         {
//             line_pool.Release(line);
//         }
//         lines.Clear();
//     }

//     void Update()
//     {
//         ClearLines();

//         // AddLine(new Vector3(-0.1f, -0.1f, 0), new Vector3(1.1f, -0.1f, 0), false);
//         // AddLine(new Vector3(-0.1f, -0.1f, 0), new Vector3(-0.1f, 1.1f, 0), false);
//         // AddLine(new Vector3(-0.1f, 1.1f, 0), new Vector3(1.1f, 1.1f, 0), false);
//         // AddLine(new Vector3(1.1f, -0.1f, 0), new Vector3(1.1f, 1.1f, 0), false);

//         AddLinesFromChronosphere();

//         ReevaluateMesh();
//         //UpdateViewPort() ;

//         UpdateTimelineDrawsObject();
//         UpdateTimelineDrawsCoordinates();

//         if (current_maximize_coef != target_maximize_coef)
//         {
//             UpdateViewPort();
//         }
//     }

//     void UpdateViewPort()
//     {
//         current_maximize_coef +=
//             (target_maximize_coef - current_maximize_coef) * 0.3f * Time.deltaTime * 60;
//         MaximizeImpl(current_maximize_coef);
//     }

//     Rect RectLerp(Rect a, Rect b, float t)
//     {
//         return new Rect(
//             a.x + (b.x - a.x) * t,
//             a.y + (b.y - a.y) * t,
//             a.width + (b.width - a.width) * t,
//             a.height + (b.height - a.height) * t
//         );
//     }

//     void MaximizeImpl(float coeff)
//     {
//         var rectmin = new Rect(0.85f, 0.85f, 0.15f, 0.15f);
//         var rectmax = new Rect(0.1f, 0.1f, 0.8f, 0.8f);
//         cam.rect = RectLerp(rectmin, rectmax, coeff);
//     }

//     void Maximize(bool timeline_map_maximized)
//     {
//         _timeline_map_maximized = timeline_map_maximized;
//         if (_timeline_map_maximized)
//         {
//             target_maximize_coef = 1;
//             //filter.enabled = true;
//         }
//         else
//         {
//             target_maximize_coef = 0;
//             //filter.enabled = false;
//         }
//     }

//     public void MaximizeSwap()
//     {
//         _timeline_map_maximized = !_timeline_map_maximized;
//         Maximize(_timeline_map_maximized);
//     }

//     GraphLine NearestLine(Vector2 field_point) { }

//     Vector2 ScreenPointToFieldPoint(Vector2 pnt)
//     {
//         return new Vector2();
//     }

//     Tuple<GraphLine, long> ScreenPointToLinePoint(Vector2 pnt)
//     {
//         var field_point = ScreenPointToFieldPoint(pnt);
//         var nearest_line = NearestLine(field_point);

//         return new Tuple<GraphLine, long>(nearest_line, 0);
//     }
// }

// class GraphLine
// {
//     public Vector3 start;
//     public Vector3 end;
//     public bool arrow;
// }

// class GraphTriangle
// {
//     public Vector3 a;
//     public Vector3 b;
//     public Vector3 c;
// }
