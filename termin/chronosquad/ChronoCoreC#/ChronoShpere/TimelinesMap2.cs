// using System.Collections;
// using System.Collections.Generic;


// using UnityEngine;
// using UnityEngine.Pool;

// public class TimelinesMap2 : MonoBehaviour
// {
// 	ChronosphereController _chronosquad_controller;

// 	Camera mainCamera;
// 	public Material Material;
// 	public Material backgoundmat;

// 	float aspect_ratio = 1.0f;
// 	float width_per_2 = 0.004f;
// 	float arrow_length = 0.05f;
// 	float arrow_width_per_2 = 0.015f;

// 	float grlevel = 1.0f;

// 	//float bglevel = 0.99f;

// 	IObjectPool<GraphLine> line_pool;
// 	MyList<GraphLine> lines = new MyList<GraphLine>();

// 	IObjectPool<GraphTriangle> triangle_pool;
// 	MyList<GraphTriangle> triangles = new MyList<GraphTriangle>();
// 	CanvasRenderer canvasRender;

// 	GameObject _timeline_map_background_object;

// 	//MeshRenderer _timeline_map_background_mesh_renderer;
// 	//MeshFilter _timeline_map_background_mesh_filter;
// 	CanvasRenderer _timeline_map_background_canvas_render;
// 	Mesh _timeline_map_background_mesh;

// 	public void PoolInit()
// 	{
// 		line_pool = new ObjectPool<GraphLine>(() => new GraphLine(), (line) => { });

// 		triangle_pool = new ObjectPool<GraphTriangle>(() => new GraphTriangle(), (triangle) => { });
// 	}

// 	// Start is called before the first frame update
// 	void Start()
// 	{
// 		_chronosquad_controller = GameObject
// 			.Find("Timelines")
// 			.GetComponent<ChronosphereController>();
// 		mainCamera = Camera.main;
// 		// screen size
// 		float width = mainCamera.pixelWidth;
// 		float height = mainCamera.pixelHeight;

// 		// meshRenderer = gameObject.AddComponent<MeshRenderer>();
// 		// meshFilter = gameObject.AddComponent<MeshFilter>();

// 		PoolInit();
// 		canvasRender = gameObject.AddComponent<CanvasRenderer>();

// 		// Mesh mesh = new Mesh();

// 		// Vector3[] vertices = new Vector3[4];
// 		// vertices[0] = new Vector3(0, 0, 0);
// 		// vertices[1] = new Vector3(width/2, 0, 0);
// 		// vertices[2] = new Vector3(0, height/2, 0);
// 		// vertices[3] = new Vector3(width/2, height/2, 0);

// 		// mesh.vertices = vertices;

// 		// int[] triangles = new int[6];
// 		// triangles[0] = 0;
// 		// triangles[1] = 2;
// 		// triangles[2] = 1;
// 		// triangles[3] = 2;
// 		// triangles[4] = 3;
// 		// triangles[5] = 1;

// 		// mesh.triangles = triangles;

// 		// Vector3[] normals = new Vector3[4];
// 		// normals[0] = -Vector3.forward;
// 		// normals[1] = -Vector3.forward;
// 		// normals[2] = -Vector3.forward;
// 		// normals[3] = -Vector3.forward;

// 		// // mesh.normals = normals;

// 		// // //meshFilter.mesh = mesh;

// 		canvasRender.materialCount = 1;
// 		canvasRender.SetMaterial(Material, 0);
// 		// canvasRender.SetMesh(mesh);


// 		SetupBackground();
// 	}

// 	void SetupBackground()
// 	{
// 		_timeline_map_background_object = new GameObject("TimelineMapBackground");
// 		//_timeline_map_background_object.layer = 15;
// 		//_timeline_map_background_object.transform.SetParent(this.transform, false);
// 		//_timeline_map_background_mesh_renderer = _timeline_map_background_object.AddComponent<MeshRenderer>();
// 		//_timeline_map_background_mesh_filter = _timeline_map_background_object.AddComponent<MeshFilter>();
// 		_timeline_map_background_canvas_render =
// 			_timeline_map_background_object.AddComponent<CanvasRenderer>();
// 		_timeline_map_background_mesh = new Mesh();
// 		_timeline_map_background_canvas_render.materialCount = 1;
// 		_timeline_map_background_canvas_render.SetMaterial(backgoundmat, 0);

// 		float width = mainCamera.pixelWidth;
// 		float height = mainCamera.pixelHeight;

// 		Mesh mesh = new Mesh();

// 		Vector3[] vertices = new Vector3[4];
// 		vertices[0] = new Vector3(0, 0, 0);
// 		vertices[1] = new Vector3(width / 2, 0, 0);
// 		vertices[2] = new Vector3(0, height / 2, 0);
// 		vertices[3] = new Vector3(width / 2, height / 2, 0);

// 		// add two triangles to background
// 		// var vertices = new MyList<Vector3>();
// 		var indices = new MyList<int>();
// 		var normals = new MyList<Vector3>();

// 		// var a = new Vector3(200, 200, 0);
// 		// var b = new Vector3(1300, 200, 0);
// 		// var c = new Vector3(200, 1300, 0);
// 		// var d = new Vector3(1300, 1300, 0);

// 		var index = 0;
// 		// vertices.Add(a);
// 		// vertices.Add(b);
// 		// vertices.Add(c);
// 		// vertices.Add(d);

// 		indices.Add(index);
// 		indices.Add(index + 1);
// 		indices.Add(index + 2);

// 		indices.Add(index + 1);
// 		indices.Add(index + 2);
// 		indices.Add(index + 3);

// 		normals.Add(Vector3.up);
// 		normals.Add(Vector3.up);
// 		normals.Add(Vector3.up);
// 		normals.Add(Vector3.up);

// 		_timeline_map_background_mesh.Clear();
// 		_timeline_map_background_mesh.vertices = vertices;
// 		_timeline_map_background_mesh.triangles = indices.ToArray();
// 		_timeline_map_background_mesh.normals = normals.ToArray();

// 		_timeline_map_background_object.transform.parent = this.transform.parent;
// 		_timeline_map_background_object.transform.localPosition = new Vector3(0, 0, 0);
// 		_timeline_map_background_canvas_render.SetMesh(_timeline_map_background_mesh);
// 	}

// 	void ClearLines()
// 	{
// 		foreach (var line in lines)
// 		{
// 			line_pool.Release(line);
// 		}
// 		lines.Clear();
// 	}

// 	// Update is called once per frame
// 	void Update()
// 	{
// 		ClearLines();

// 		// AddLine(new Vector3(-0.1f, -0.1f, 0), new Vector3(1.1f, -0.1f, 0), false);
// 		// AddLine(new Vector3(-0.1f, -0.1f, 0), new Vector3(-0.1f, 1.1f, 0), false);
// 		// AddLine(new Vector3(-0.1f, 1.1f, 0), new Vector3(1.1f, 1.1f, 0), false);
// 		// AddLine(new Vector3(1.1f, -0.1f, 0), new Vector3(1.1f, 1.1f, 0), false);

// 		AddLinesFromChronosphere();

// 		ReevaluateMesh();
// 		//UpdateViewPort() ;

// 		// if (current_maximize_coef != target_maximize_coef)
// 		// {
// 		// 	UpdateViewPort() ;
// 		// }
// 	}

// 	void AddLinesFromChronosphere()
// 	{
// 		var tls = _chronosquad_controller.TimelineControllers();
// 		for (int i = 0; i < tls.Count; i++)
// 		{
// 			AddLine(new Vector3(0, 0.1f * i, 0), new Vector3(0.5f, 0.1f * i, 0), true);
// 			//AddLine(new Vector3(0, 0.5f + 0.1f * i, 0), new Vector3(0.5f, 0.5f+ 0.1f * i, 0), true);
// 			// 	AddLine(new Vector3(0.5f, 0.1f * i, 0), new Vector3(0.5f, 0.1f * (i+1), 0), true);
// 			// 	AddLine(new Vector3(0.0f, 0.1f * i, 0), new Vector3(0.0f, 0.1f * (i+1), 0), true);
// 			// 	AddLine(new Vector3(0.25f, 0.1f * i, 0), new Vector3(0.25f, 0.1f * (i+1), 0), true);
// 			// 	AddLine(new Vector3(0.1f, 0.1f * i, 0), new Vector3(0.1f, 0.1f * (i+1), 0), true);
// 		}
// 	}

// 	void AddLine(Vector3 start, Vector3 end, bool arrow = false)
// 	{
// 		// start.y = -start.y;
// 		// end.y = -end.y;

// 		//map 0..1 to -xw..xw
// 		//map 0..1 to -yw..yw

// 		float xw = 0.8f;
// 		float yw = 0.8f;
// 		start = new Vector3(start.x * xw * 2 - xw, start.y * yw * 2 - yw, start.z);
// 		end = new Vector3(end.x * xw * 2 - xw, end.y * yw * 2 - yw, end.z);

// 		//lines.Add(new GraphLine() { start = start, end = end, arrow = arrow });
// 		var line = line_pool.Get();
// 		line.start = start;
// 		line.end = end;
// 		line.arrow = arrow;
// 		lines.Add(line);
// 	}

// 	void ReevaluateMesh()
// 	{
// 		for (int i = 0; i < triangles.Count; i++)
// 		{
// 			triangle_pool.Release(triangles[i]);
// 		}

// 		triangles.Clear();
// 		foreach (var line in lines)
// 		{
// 			CompileLineToTriangle(line);
// 		}

// 		var vertices = new MyList<Vector3>();
// 		var indices = new MyList<int>();
// 		var normals = new MyList<Vector3>();
// 		var uvs = new MyList<Vector3>();

// 		foreach (var triangle in triangles)
// 		{
// 			var index = vertices.Count;
// 			vertices.Add(triangle.a);
// 			vertices.Add(triangle.b);
// 			vertices.Add(triangle.c);

// 			indices.Add(index);
// 			indices.Add(index + 1);
// 			indices.Add(index + 2);

// 			normals.Add(Vector3.up);
// 			normals.Add(Vector3.up);
// 			normals.Add(Vector3.up);
// 		}

// 		var new_mesh = new Mesh();

// 		new_mesh.vertices = vertices.ToArray();
// 		new_mesh.triangles = indices.ToArray();
// 		new_mesh.normals = normals.ToArray();

// 		canvasRender.SetMesh(new_mesh);
// 	}

// 	void CompileLineToTriangle(GraphLine line)
// 	{
// 		var diff = line.end - line.start;
// 		var diffnorm = diff.normalized;
// 		var x = diff.x;
// 		var y = diff.y;

// 		var norm = new Vector3(-y, x, 0);
// 		var normalized = norm.normalized;
// 		normalized = new Vector3(normalized.x, normalized.y * aspect_ratio, normalized.z);

// 		var e = diffnorm * width_per_2;
// 		e = new Vector3(e.x, e.y * aspect_ratio, e.z);

// 		var e2 = diffnorm;
// 		e2 = new Vector3(e2.x, e2.y * aspect_ratio, e2.z);

// 		var ee = line.arrow ? -e2 * arrow_length : e;

// 		var z = new Vector3(0, 0, grlevel);
// 		var a = line.start + normalized * width_per_2 + z - e;
// 		var b = line.start - normalized * width_per_2 + z - e;
// 		var c = line.end + normalized * width_per_2 + z + ee;
// 		var d = line.end - normalized * width_per_2 + z + ee;

// 		//triangles.Add(new GraphTriangle() { a = a, b = b, c = c });
// 		//triangles.Add(new GraphTriangle() { a = b, b = c, c = d });

// 		var t1 = triangle_pool.Get();
// 		t1.a = a;
// 		t1.b = b;
// 		t1.c = c;
// 		triangles.Add(t1);
// 		var t2 = triangle_pool.Get();
// 		t2.a = b;
// 		t2.b = c;
// 		t2.c = d;
// 		triangles.Add(t2);

// 		if (line.arrow)
// 		{
// 			var arrow_a = line.end + z;
// 			var arrow_b = line.end + z - e2 * arrow_length + normalized * arrow_width_per_2;
// 			var arrow_c = line.end + z - e2 * arrow_length - normalized * arrow_width_per_2;

// 			//triangles.Add(new GraphTriangle() { a = arrow_a, b = arrow_b, c = arrow_c });
// 			var t3 = triangle_pool.Get();
// 			t3.a = arrow_a;
// 			t3.b = arrow_b;
// 			t3.c = arrow_c;
// 			triangles.Add(t3);
// 		}
// 	}

// 	GraphLine NearestLine(Vector2 field_point) { }

// 	Vector2 ScreenPointToFieldPoint(Vector2 pnt)
// 	{
// 		return new Vector2();
// 	}

// 	Tuple<GraphLine, long> ScreenPointToLinePoint(Vector2 pnt)
// 	{
// 		var field_point = ScreenPointToFieldPoint(pnt);
// 		var nearest_line = NearestLine(field_point);

// 		return new Tuple<GraphLine, long>(nearest_line, 0);
// 	}
// }
