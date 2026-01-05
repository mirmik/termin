using MeshAnalyze;
using UnityEngine;
using System.Collections.Generic;

using UnityEngine.AI;

#if UNITY_64
using Unity.AI.Navigation;
#endif

public struct DistanceMesureResult
{
    public Vector3 point;
    public float distance;
    public bool hitted;
}

// use in editor mode
[ExecuteInEditMode]
public class MeshAnalyzeMonoBeh : MonoBehaviour
{
    public bool GenerateWallLinks = true;

    Mesh mesh;
    MeshAnalyzer meshAnalyzer;

    MyList<Wire> horizontal_wires;
    MyList<Wire> horizontal_corners;
    MyList<Wire> vertical_wires;
    MyList<Wire> vertical_corners;
    MyList<Wire> corners;

    MyList<GameObject> boxes = new MyList<GameObject>();

    public bool GroundLeanZones = true;

    public bool MarkBottomLayer = false;

    public float ExteriorLeafTangOffset = 0.0f;
    public float UStep = 1.0f;

    [ContextMenu("Init")]
    void Init()
    {
        mesh = GetComponent<MeshFilter>().sharedMesh;
        meshAnalyzer = new MeshAnalyzer(mesh, this.transform);
        var wires = meshAnalyzer.FindAllTwoLeavesWires();

        var q = transform.rotation;
        corners = MeshAnalyzer.FilterCorners(wires);
        horizontal_wires = MeshAnalyzer.HorizontalWires(wires, Quaternion.identity);
        horizontal_corners = MeshAnalyzer.FilterCorners(horizontal_wires);
        vertical_wires = MeshAnalyzer.VerticalWires(wires);
        vertical_corners = MeshAnalyzer.FilterCorners(vertical_wires);
    }

    // [ContextMenu("MakeWallLinks")]
    // void MakeWallLinks()
    // {
    // 	Init();
    // 	foreach (var corner in vertical_corners)
    // 	{
    // 		if (corner.IsExteriorCorner())
    // 		{
    // 			MakeWallLinksForExteriorCorner(corner, 0.5f);
    // 		}
    // 	}
    // }


    [ContextMenu("MakeInternalCornerLinksForFloor")]
    void MakeInternalCornerLinksForFloor()
    {
        Init();
        foreach (var corner in horizontal_corners)
        {
            if (corner.IsInteriorCorner())
            {
                var aleaf = corner.ALeaf();
                var bleaf = corner.BLeaf();

                if (aleaf.NormalIsUp(transform.rotation) || bleaf.NormalIsUp(transform.rotation))
                {
                    MakeWallLinksForInternalCorner(corner, 0.5f, width: 0);
                }
            }
        }
    }

    // [ContextMenu("MakeTopWallLinks")]
    // void MakeTopWallLinks()
    // {
    // 	Init();
    // 	foreach (var corner in horizontal_corners)
    // 	{
    // 		if (corner.IsExteriorCorner())
    // 		{
    // 			MakeWallLinksForExteriorCorner(corner, 0.5f);
    // 		}
    // 	}
    // }

    // [ContextMenu("LinksByNavMeshChecks")]
    // void LinksByNavMeshChecks()
    // {
    // 	Init();
    // 	foreach (var corner in corners)
    // 	{
    // 		MakeCornerLinkForNavMeshCheck(corner, 0.5f);
    // 	}
    // }

    [ContextMenu("LinksForExterior")]
    public void LinksForExterior()
    {
        Init();
        foreach (var corner in corners)
        {
            if (corner.IsExteriorCorner())
            {
                LinksForExteriorUniform(corner);
            }
        }
    }

    [ContextMenu("FullProgram")]
    public void FullProgram()
    {
        NML_Utility.RemoveLinks(transform);
        if (!GenerateWallLinks)
            return;

        try
        {
            Init();
            LinksForExterior();
            MakeInternalCornerLinksForFloor();
        }
        catch (System.Exception e)
        {
            Debug.Log("FullProgram: " + name + ":" + e.Message);
        }
    }

    void LinksForExteriorPointLeafOnlyPhase(Vector3 point, Vector3 normal, Vector3 tang, float step)
    {
        float offset = 0.5f;
        var base_point = point + offset * normal + offset * tang;
        RaycastHit hit;
        bool hitted = Physics.Raycast(base_point, -tang, out hit, 3.0f, 1 << 0);
        if (hitted)
        {
            var orientation = Quaternion.LookRotation(tang, normal);

            NML_Utility.MakeLinkWithChecks(
                point + tang * offset,
                hit.point + tang * ExteriorLeafTangOffset,
                orientation,
                check_navmesh: true,
                storage_transform: transform,
                area: ChooseWallAreaForPoint(point),
                agent: GameCore.GetNavMeshAgentID("Short").Value
            );
        }
    }

    void LinksForExteriorUniform(Wire corner)
    {
        var a_point = corner.a.position;
        var b_point = corner.b.position;
        var a_tang = corner.ATangDirection().normalized;
        var b_tang = corner.BTangDirection().normalized;
        var a_normal = corner.ANormalDirection().normalized;
        var b_normal = corner.BNormalDirection().normalized;
        float step = UStep;

        var uniformed = Utility.UniformSpace(a_point, b_point, ref step);
        for (int i = 0; i < uniformed.Count; i++)
        {
            var point = uniformed[i];

            bool a_space = Utility.CheckFreeSpaceForCornerLeaf(point, a_normal, a_tang);
            bool b_space = Utility.CheckFreeSpaceForCornerLeaf(point, b_normal, b_tang);

            if (a_space && b_space)
            {
                float o = 0.5f;
                var ap = point + a_tang * o;
                var bp = point + b_tang * o;
                var c = (ap + bp) / 2;
                var up = point - c;

                var orientation = Quaternion.LookRotation((bp - ap).normalized, up);

                NML_Utility.MakeLinkWithChecks(
                    ap,
                    bp,
                    orientation,
                    check_navmesh: true,
                    storage_transform: transform,
                    area: ChooseWallAreaForPoint(point),
                    agent: GameCore.GetNavMeshAgentID("Short").Value
                );
            }

            if (!a_space)
            {
                LinksForExteriorPointLeafOnlyPhase(point, a_normal, a_tang, step);
            }

            if (!b_space)
            {
                LinksForExteriorPointLeafOnlyPhase(point, b_normal, b_tang, step);
            }
        }
    }

    void MakeWallLinksForInternalCorner(Wire corner, float offset, float width = 10000)
    {
        var a_point = corner.a.position;
        a_point = transform.TransformPoint(a_point);

        var b_point = corner.b.position;
        b_point = transform.TransformPoint(b_point);

        var distance = Vector3.Distance(a_point, b_point);
        float step = 2.0f;
        int count = (int)(distance / step) + 1;
        float actual_step = distance / count;

        var atang = corner.ATangDirection().normalized;
        var btang = corner.BTangDirection().normalized;
        atang = transform.TransformDirection(atang);
        btang = transform.TransformDirection(btang);

        var nnn = (b_point - a_point).normalized;
        MyList<Vector3> points = new MyList<Vector3>();
        for (int i = 0; i < count; i++)
        {
            var point = Vector3.Lerp(a_point, b_point, i / (float)count);
            var off = nnn * step / 2.0f;
            points.Add(point + off);
        }

        MakeUniformedLinks(
            a_point,
            b_point,
            atang * offset,
            btang * offset,
            2.0f,
            check_external: true,
            width: width
        );
    }

    void MakeWallLinksForExteriorCorner(Wire corner, float offset)
    {
        var a_point = corner.BottomPoint();
        a_point = transform.TransformPoint(a_point);

        var b_point = corner.TopPoint();
        b_point = transform.TransformPoint(b_point);

        var distance = Vector3.Distance(a_point, b_point);
        float step = 2.0f;
        int count = (int)(distance / step) + 1;
        float actual_step = distance / count;

        var atang = corner.ATangDirection().normalized;
        var btang = corner.BTangDirection().normalized;
        atang = transform.TransformDirection(atang);
        btang = transform.TransformDirection(btang);

        var nnn = (b_point - a_point).normalized;
        MyList<Vector3> points = new MyList<Vector3>();
        for (int i = 0; i < count; i++)
        {
            var point = Vector3.Lerp(a_point, b_point, i / (float)count);
            var off = nnn * step / 2.0f;
            points.Add(point + off);
        }

        MakeUniformedLinks(
            a_point,
            b_point,
            atang * offset,
            btang * offset,
            2.0f,
            check_external: true
        );
    }

    void MakeCornerLinkForNavMeshCheck(Wire corner, float offset)
    {
        var a_point = corner.a.position;
        a_point = transform.TransformPoint(a_point);

        var b_point = corner.b.position;
        b_point = transform.TransformPoint(b_point);

        var distance = Vector3.Distance(a_point, b_point);
        int count = (int)(distance / UStep) + 1;
        float actual_step = distance / count;

        var atang = corner.ATangDirection().normalized;
        var btang = corner.BTangDirection().normalized;
        atang = transform.TransformDirection(atang);
        btang = transform.TransformDirection(btang);

        var nnn = (b_point - a_point).normalized;
        MyList<Vector3> points = new MyList<Vector3>();
        for (int i = 0; i < count; i++)
        {
            var point = Vector3.Lerp(a_point, b_point, i / (float)count);
            var off = nnn * UStep / 2.0f;
            points.Add(point + off);
        }

        MakeUniformedLinks(
            a_point,
            b_point,
            atang * offset,
            btang * offset,
            UStep,
            check_external: true,
            check_navmesh: true
        );
    }

    public void MakeUniformedLinks(
        Vector3 a,
        Vector3 b,
        Vector3 c_off,
        Vector3 d_off,
        float step,
        bool check_external = false,
        bool check_navmesh = false,
        float width = 10000
    )
    {
        var distance = Vector3.Distance(a, b);
        int count = (int)(distance / step) + 1;
        var nnn = (b - a).normalized;
        float actual_step = distance / count;

        MyList<Vector3> points = new MyList<Vector3>();
        for (int i = 0; i < count; i++)
        {
            var point = Vector3.Lerp(a, b, i / (float)count);
            var off = nnn * step / 2.0f;
            points.Add(point + off);
        }

        var lookdir = c_off.normalized - d_off.normalized;
        var up = Vector3.Cross((b - a).normalized, lookdir.normalized).normalized;

        var link_orientation = Quaternion.LookRotation(lookdir, up);

        if (width != 10000)
            actual_step = width;

        foreach (var point in points)
        {
            var a_ = point + c_off;
            var b_ = point + d_off;
            NML_Utility.MakeLinkWithChecks(
                a: a_,
                b: b_,
                width: actual_step,
                orientation: link_orientation,
                check_external: check_external,
                check_navmesh: check_navmesh,
                storage_transform: transform,
                area: ChooseWallAreaForPoint(point),
                agent: GameCore.GetNavMeshAgentID("Short").Value
            );
        }
    }

    int ChooseWallAreaForPoint(Vector3 point)
    {
        var pab = GameCore.FindInParentTree<PlatformAreaBase>(gameObject);
        var gravity = pab.GetGravity(point);
        int area =
            gravity.magnitude < 1.0f
                ? (int)Areas.WALLS_FOR_ZERO_GRAVITY_AREA
                : (int)Areas.WALLS_AREA;
        return area;
    }

    // public DistanceMesureResult DistanceMesure(Vector3 origin, Vector3 direction, float maxdist)
    // {
    // 	var layer_mask = 1 << 0 | 1 << 6 | 1 << 10;
    // 	RaycastHit hit;
    // 	bool hitted = Physics.Raycast(origin, direction, out hit, maxdist, layer_mask);
    // 	return new DistanceMesureResult
    // 	{
    // 		point = hitted ? hit.point : origin + direction * maxdist,
    // 		distance = hitted ? hit.distance : maxdist,
    // 		hitted = hitted
    // 	};
    // }

    // void MakeDeflatedPetalLink(Leaf leaf)
    // {
    // 	Debug.Log("MakeDeflatedPetalLink");
    // 	float tang_offset = 1.0f;

    // 	var tang = transform.TransformDirection(leaf.tang);
    // 	var normal = transform.TransformDirection(leaf.normal);
    // 	var center = transform.TransformPoint(leaf.Center());
    // 	var tang_n_center = center + tang * tang_offset + normal * 1.0f;

    // 	var dresult = DistanceMesure(tang_n_center, -tang, 2.2f);
    // 	Debug.Log("tan_n_center: " + tang_n_center);

    // 	if (!dresult.hitted) {
    // 		Debug.Log("Not hitted");
    // 		return;
    // 	}
    // 	else {
    // 		Debug.Log("Hitted " + dresult.point + " " + dresult.distance);
    // 	}

    // 	var floor_level = tang_offset - dresult.distance;

    // 	Vector3 c_off = (0.0f+floor_level) * tang + 1.0f*normal;
    // 	Vector3 d_off = (1.0f+floor_level) * tang + 0.0f*normal;

    // 	var a = transform.TransformPoint(leaf.wire.a.position);
    // 	var b = transform.TransformPoint(leaf.wire.b.position);

    // 	MakeUniformedLinks(
    // 		a, b, c_off, d_off, 2.0f);
    // }


    // public void TryMakeCornerLeafForLeaf(Leaf leaf)

    // {
    // 	var test_point = leaf.TangCenterPoint(1.0f, 1.0f);
    // 	test_point = transform.TransformPoint(test_point);
    // 	var overlap = Physics.OverlapSphere(test_point, 0.01f, 1 << 0 | 1 << 6 | 1 << 10);
    // 	if (overlap.Length > 0) {
    // 		Debug.Log("Overlap");
    // 		return;
    // 	}

    // 	MakeDeflatedPetalLink(leaf);
    // }

    // [ContextMenu("MakeExternalCornerLinksForSides")]
    // public void MakeExternalCornerLinksForSides()
    // {
    // 	Init();
    // 	foreach (var corner in vertical_corners)
    // 	{
    // 		TryMakeCornerLeafForLeaf(corner.ALeaf());
    // 		TryMakeCornerLeafForLeaf(corner.BLeaf());
    // 	}
    // }

    // [ContextMenu("MakeExternalCornerLinksForBottom")]
    // public void MakeExternalCornerLinksForBottom()
    // {
    // 	Init();
    // 	foreach (var corner in horizontal_corners)
    // 	{
    // 		//float tang_offset = 1.0f;

    // 		var vertical_leaf = corner.VerticalLeaf();
    // 		TryMakeCornerLeafForLeaf(vertical_leaf);
    // 	}
    // }


    [ContextMenu("MakeLeanZones")]
    public void MakeLeanZones()
    {
        Init();
        CleanBoxes();
        foreach (var corner in vertical_corners)
        {
            if (corner.IsExteriorCorner())
                MakeLeanZone(corner, 1.0f, 1.8f, 0.2f);
        }
    }

    static Vector3 ElementWiseProduct(Vector3 a, Vector3 b)
    {
        return new Vector3(a.x * b.x, a.y * b.y, a.z * b.z);
    }

    bool IsLean(Vector3 position, Quaternion rotation, Vector3 scale)
    {
        Vector3 back = rotation * Vector3.back;

        Vector3 a = new Vector3(-0.49f, -0.49f, -0.49f);
        Vector3 b = new Vector3(0.49f, -0.49f, -0.49f);
        Vector3 c = new Vector3(-0.49f, 0.49f, -0.49f);
        Vector3 d = new Vector3(0.49f, 0.49f, -0.49f);

        Vector3 a_s = ElementWiseProduct(scale, a);
        Vector3 b_s = ElementWiseProduct(scale, b);
        Vector3 c_s = ElementWiseProduct(scale, c);
        Vector3 d_s = ElementWiseProduct(scale, d);

        Vector3 a_rot = rotation * a_s;
        Vector3 b_rot = rotation * b_s;
        Vector3 c_rot = rotation * c_s;
        Vector3 d_rot = rotation * d_s;

        Vector3 a_pos = position + a_rot;
        Vector3 b_pos = position + b_rot;
        Vector3 c_pos = position + c_rot;
        Vector3 d_pos = position + d_rot;

        Vector3[] vectors = new Vector3[] { a_pos, b_pos, c_pos, d_pos };

        var layer_mask = 1 << 0 | 1 << 6 | 1 << 10;
        RaycastHit[] hits;
        foreach (var vec in vectors)
        {
            hits = Physics.RaycastAll(vec, back, 0.5f, layer_mask);
            if (hits.Length == 0)
            {
                return false;
            }
        }
        return true;
    }

    void DoLeansForCorner(
        Vector3 bottom_point,
        Vector3 normal,
        Vector3 tang,
        Vector3 updir,
        float width,
        float height,
        float deep
    )
    {
        Vector3 scale = new Vector3(width, height, deep);

        var global_point = (bottom_point);
        var global_normal = (normal).normalized;
        var global_up_dir = (updir).normalized;
        var global_tang = (tang).normalized;

        var position =
            global_point
            + global_normal * deep / 2
            + global_tang * width / 2
            + global_up_dir * height / 2;

        float offset = 0;

        Vector3 offseted = position + global_up_dir * offset;
        Quaternion rot = Quaternion.LookRotation(global_normal, global_up_dir);

        bool has_space_in_side = Utility.HasSpace(position, -global_tang, 2.0f);
        if (!has_space_in_side)
        {
            Debug.Log("No space in side");
            return;
        }

        bool is_grounded = IsGrounded(position, height + 0.001f, out offset);
        if (is_grounded || !GroundLeanZones)
        {
            bool a_check_lean = IsLean(position, rot, scale);

            if (a_check_lean)
            {
                var leans = transform.Find("Leans");
                if (leans == null)
                {
                    var leans_go = new GameObject("Leans");
                    leans_go.layer = (int)Layers.CORNER_LEAN_LAYER;
                    leans_go.transform.parent = transform;
                    leans = leans_go.transform;
                }

                var box_a = GameObject.CreatePrimitive(PrimitiveType.Cube);
                box_a.name = "MeshAnalyzeMonoBeh.BoxA";
                box_a.transform.localScale = scale;
                box_a.transform.position = offseted;
                box_a.transform.rotation = rot;
                box_a.layer = (int)Layers.CORNER_LEAN_LAYER;
                var lean_zone = box_a.AddComponent<CornerLeanZone>();
                boxes.Add(box_a);
                box_a.transform.parent = leans.transform;

                bool is_left = IsLeftTriad(global_tang, global_normal, global_up_dir);

                if (is_left)
                {
                    box_a.GetComponent<Renderer>().material = MaterialKeeper.Instance.GetMaterial(
                        "LeanMaterial"
                    );
                    lean_zone.Type = CornerLeanZoneType.Left;
                }
                else
                {
                    box_a.GetComponent<Renderer>().material = MaterialKeeper.Instance.GetMaterial(
                        "LeanMaterialSecond"
                    );
                    lean_zone.Type = CornerLeanZoneType.Right;
                }
            }
        }

#if UNITY_EDITOR
        // set it dirty
        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(gameObject.scene);
#endif
    }

    void MakeLeanZone(Wire verwire, float width, float height, float deep)
    {
        var bottom_point = verwire.BottomPoint();
        var a_tang = verwire.ATangDirection();
        var b_tang = verwire.BTangDirection();
        var a_normal = verwire.ANormalDirection();
        var b_normal = verwire.BNormalDirection();
        var up_dir = verwire.UpDirection();

        DoLeansForCorner(bottom_point, a_normal, a_tang, up_dir, width, height, deep);
        DoLeansForCorner(bottom_point, b_normal, b_tang, up_dir, width, height, deep);
    }

    public bool IsGrounded(Vector3 position, float height, out float offset)
    {
        var ray = new Ray(position, Vector3.down);
        var layer_mask = 1 << 0 | 1 << 6 | 1 << 10;
        var hits = Physics.RaycastAll(ray, height, layer_mask);
        foreach (var hit in hits)
        {
            offset = height - hit.distance;
            return true;
        }
        offset = 0;
        return false;
    }

    [ContextMenu("CleanBoxes")]
    void CleanBoxes()
    {
        // get Leans child
        var leans = transform.Find("Leans");
        if (leans != null)
        {
            GameObject.DestroyImmediate(leans.gameObject);
        }
    }

    [ContextMenu("CleanLinks")]
    void CleanLinks()
    {
        // get Leans child
        var leans = transform.Find("Links");
        if (leans != null)
        {
            GameObject.DestroyImmediate(leans.gameObject);
        }
    }

    bool IsLeftTriad(Vector3 a, Vector3 b, Vector3 c)
    {
        return Vector3.Dot(Vector3.Cross(b - a, c - a), Vector3.up) > 0;
    }

    // void MakeBoxesFromCenterCorner(Wire verwire, float width, float height, float deep)
    // {
    // 	Quaternion q = transform.rotation;
    // 	var center_point = verwire.CenterPoint();
    // 	var a_tang = verwire.ATangDirection();
    // 	var b_tang = verwire.BTangDirection();
    // 	var a_normal = verwire.ANormalDirection();
    // 	var b_normal = verwire.BNormalDirection();
    // 	var up_dir = verwire.UpDirection();

    // 	Vector3 box_size = new Vector3(width, height, deep);
    // 	var global_a_point = transform.TransformPoint(center_point);
    // 	var global_b_point = transform.TransformPoint(center_point);
    // }

    public void DrawEdge(MeshAnalyze.Edge edge, Color color)
    {
        Vector3 p1 = mesh.vertices[edge.a.index];
        Vector3 p2 = mesh.vertices[edge.b.index];

        p1 = transform.TransformPoint(p1);
        p2 = transform.TransformPoint(p2);

        Debug.DrawLine(p1, p2, color, 1000);
    }

    // public void DrawWire(MeshAnalyze.Wire wire, Color color)
    // {
    // 	for (int i = 0; i < wire.edges.Count; i++)
    // 	{
    // 		DrawEdge(wire.edges[i], color);
    // 	}
    // }
}
