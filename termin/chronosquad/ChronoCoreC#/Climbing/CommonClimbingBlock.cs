using MeshAnalyze;
using UnityEngine;
using Unity.AI.Navigation;

public class CommonClimbingBlock : MonoBehaviour
{
    public bool ForwardSide = true;
    public bool BackwardSide = true;
    public bool LeftSide = true;
    public bool RightSide = true;
    public bool AutoUpdate = false;

    public bool UseBlockUp = true;

    MyList<Wire> EvalHorizontalCorners(Quaternion rotation)
    {
        var meshAnalyzer = new MeshAnalyzer(GetComponent<MeshFilter>().sharedMesh, this.transform);
        var wires = meshAnalyzer.FindAllTwoLeavesWires();
        var horizontal_wires = MeshAnalyzer.HorizontalWires(wires, rotation);
        var horizontal_corners = MeshAnalyzer.FilterCorners(horizontal_wires);
        return horizontal_corners;
    }

    [ContextMenu("Generate UpDown Links")]
    void GenerateStairsLinks()
    {
        Quaternion rotation = UseBlockUp ? this.transform.rotation : Quaternion.identity;

        var horizontal_corners = EvalHorizontalCorners(rotation);
        CleanLinks();
        MyList<Wire> top_corners = new MyList<Wire>();
        foreach (var wire in horizontal_corners)
        {
            if (wire.IsTopExteriorCorner(rotation))
            {
                top_corners.Add(wire);
            }
        }
        foreach (var corner in top_corners)
        {
            MakeUpDownLinkForCorner(corner, rotation);
        }
    }

    [ContextMenu("Clean Links")]
    void CleanLinks()
    {
        NML_Utility.RemoveLinks(transform, "UpDownLinks");
    }

    void MakeUpDownLinkForCorner(Wire corner, Quaternion rotation)
    {
        var platform = GameCore.FindInParentTree<PlatformAreaBase>(this.gameObject);

        //var reference_object = platform.ObjectReference.transform;

        var upoints = corner.UniformPoints(1.0f);
        upoints = Utility.CentersOfUniformPoints(upoints);
        var top_leaf = corner.UpSideLeaf(rotation);
        var bottom_leaf = corner.DownSideLeaf(rotation);
        var forward = top_leaf.tang;
        var down = rotation * Vector3.down;
        var up = rotation * Vector3.up;

        foreach (var upoint in upoints)
        {
            var raycast_start = upoint - forward;

            RaycastHit hit;
            Vector3 bottom_point = upoint + down;

            // raycast to down dir
            if (
                Physics.Raycast(
                    raycast_start,
                    down,
                    out hit,
                    10000.0f,
                    layerMask: Utility.ToMask(Layers.DEFAULT_LAYER)
                        | Utility.ToMask(Layers.OBSTACLES_LAYER)
                        | Utility.ToMask(Layers.GROUND_LAYER)
                )
            )
            {
                bottom_point = hit.point;
            }
            else
            {
                continue;
            }

            var rot = Quaternion.LookRotation(forward, up);
            var link = NML_Utility.MakeLink(
                upoint + forward,
                bottom_point,
                Quaternion.LookRotation(-forward, up),
                storage_transform: transform,
                storage_name: "UpDownLinks",
                area: (int)Areas.BRACED_UPDOWN_LINK_AREA,
                agent: GameCore.GetNavMeshAgentID("Common").Value,
                autoupdate: AutoUpdate
            );

            var bcs = link.gameObject.AddComponent<UpDownBracedCoordinateGenerator>();
            bcs.Reference = platform.ObjectReference;
            bcs.link = link;
            bcs.EdgePositionInLinkFrame = link.transform.InverseTransformPoint(upoint);

            var recaster = link.gameObject.AddComponent<NMLAutoRecasterUpDown>();
            recaster.SetLink(link);
            recaster.SetCastStart(link.transform.InverseTransformPoint(raycast_start));
            recaster.SetCastDir(
                link.transform.InverseTransformDirection((bottom_point - raycast_start).normalized)
            );
        }
    }

    public BracedCoordinates BracedCoordinates(NavMeshLink link)
    {
        // Vector3 apoint = link.transform.TransformPoint(link.startPoint);
        // Vector3 bpoint = link.transform.TransformPoint(link.endPoint);
        // var diff = bpoint - apoint;
        // var up = link.transform.up;
        // var dot = Vector3.Dot(diff, up);
        // var hor = diff - dot * up;
        // var forw = hor.normalized;
        // var rot = Quaternion.LookRotation(-hor, transform.up);

        // var apose = new BracedCoordinates(
        // 	braced_hit : bpoint,
        // 	rotation: rot,
        // 	top_position: apoint + forw,
        // 	nav_position: apoint,
        // 	bot_position: null
        // );

        // var platform = NavMeshLinkSupervisor.Instance.FoundPlatformGO(this.gameObject);
        // var lapoint = platform.transform.InverseTransformPoint(apoint);
        // var lbpoint = platform.transform.InverseTransformPoint(bpoint);
        // var qrot = Quaternion.Inverse(platform.transform.rotation) * rot;

        // var rpose = new ReferencedPose(
        // 	lapoint,
        // 	qrot,
        // 	new ObjectId(platform.name));
        // apose.APose = rpose;

        // return apose;

        UpDownBracedCoordinateGenerator bcs = link.GetComponent<UpDownBracedCoordinateGenerator>();
        return bcs.GenerateBracedCoordinates();
    }

    [ContextMenu("Make Climbing Surface")]
    void CreateClimbingNavMeshSurface()
    {
        RemoveClimbingSurface();
        CreateClimbingNavMeshSurface_DoIt();

        GameCore.SceneDirty(this.gameObject.scene);
    }

    void RemoveClimbingSurface()
    {
        var go = transform.Find("ClimbingNavMeshSurface")?.gameObject;
        if (go != null)
            GameObject.DestroyImmediate(go);
    }

    GameObject CreateBox(GameObject parent)
    {
        var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
        go.transform.parent = parent.transform;
        go.transform.localPosition = Vector3.zero;
        go.transform.localRotation = Quaternion.identity;
        go.transform.localScale = Vector3.one;
        go.GetComponent<MeshRenderer>().material = MaterialKeeper.Instance.FindMaterialInList(
            "ClimbingSurface"
        );
        go.layer = 24;
        return go;
    }

    Vector3 Clamp(Vector3 pos_in_source, float min, float max)
    {
        var x = Mathf.Clamp(pos_in_source.x, min, max);
        var y = Mathf.Clamp(pos_in_source.y, min, max);
        var z = Mathf.Clamp(pos_in_source.z, min, max);
        return new Vector3(x, y, z);
    }

    Vector3 DirectionFromPos(Vector3 pos_in_source)
    {
        Vector3 dir_in_source = new Vector3(-1.0f, 0, 0);
        if (Mathf.Abs(pos_in_source.x - 0.5f) < 0.01f)
            dir_in_source = new Vector3(-0.5f, 0, 0);
        if (Mathf.Abs(pos_in_source.x + 0.5f) < 0.01f)
            dir_in_source = new Vector3(0.5f, 0, 0);
        if (Mathf.Abs(pos_in_source.z - 0.5f) < 0.01f)
            dir_in_source = new Vector3(0, 0, -1.0f);
        if (Mathf.Abs(pos_in_source.z + 0.5f) < 0.01f)
            dir_in_source = new Vector3(0, 0, 1.0f);
        return dir_in_source;
    }

    public float DistanceToBlock(Vector3 glbpos)
    {
        var boxcollider = this.gameObject.GetComponent<BoxCollider>();
        var dist_to_block = boxcollider.ClosestPoint(glbpos) - glbpos;
        return dist_to_block.magnitude;
    }

    public BracedCoordinates GetBracedCoordinates(Vector3 glbpos)
    {
        float Y = 1.5f;

        var center_of_source = this.gameObject.transform.position;

        var pos_in_source = this.gameObject.transform.InverseTransformPoint(glbpos);

        var down_direction = -this.transform.up;

        pos_in_source = Clamp(pos_in_source, -0.5f, 0.5f);
        pos_in_source.y = 0.5f;
        var top_position = this.gameObject.transform.TransformPoint(pos_in_source);

        Vector3 dir_in_source = DirectionFromPos(pos_in_source);

        var dir_in_global = this.gameObject.transform.TransformDirection(dir_in_source).normalized;
        var dir_to_bot_in_global = (-dir_in_global + down_direction * Y).normalized;

        Vector3? bot_position;
        RaycastHit hit;
        var layerMask = 1 << LayerMask.NameToLayer("FieldOfView") | 1 << 0 | 1 << 6;

        if (
            !Physics.Raycast(
                top_position + dir_to_bot_in_global * 0.1f,
                dir_to_bot_in_global,
                out hit,
                Mathf.Infinity,
                layerMask
            )
        )
        {
            bot_position = null;
        }
        else
        {
            bot_position = hit.point;
        }

        var rotation = MathUtil.XZDirectionToQuaternion(dir_in_global);
        var nav_position = top_position + (rotation * Vector3.forward) * 0.5f;
        BracedCoordinates bc = new BracedCoordinates(
            braced_hit: glbpos,
            rotation: rotation,
            top_position: top_position,
            nav_position: nav_position,
            bot_position: bot_position,
            target_point: new ReferencedPoint(nav_position, default(ObjectId))
        );
        return bc;
    }

    [ContextMenu("Make Box Collider")]
    BoxCollider MakeBoxCollider()
    {
        float BoxColliderTopYOffset = -0.05f;
        float BoxColliderBotYOffset = -1.0f;

        var cgo = this.gameObject;
        var go = new GameObject("BracedCollider");

        go.transform.parent = cgo.transform;
        go.transform.localRotation = Quaternion.identity;

        var global_x_size = cgo.transform.localScale.x + 0.2f;
        var global_y_size = BoxColliderTopYOffset - BoxColliderBotYOffset;
        var global_z_size = cgo.transform.localScale.z + 0.2f;

        var local_x_size = global_x_size / cgo.transform.localScale.x;
        var local_y_size = global_y_size / cgo.transform.localScale.y;
        var local_z_size = global_z_size / cgo.transform.localScale.z;

        var global_y_position =
            cgo.transform.localScale.y / 2.0f
            + BoxColliderBotYOffset
            + (BoxColliderTopYOffset - BoxColliderBotYOffset) / 2.0f;

        var local_y_position = global_y_position / cgo.transform.localScale.y;

        go.transform.localScale = new Vector3(local_x_size, local_y_size, local_z_size);

        go.transform.localPosition = new Vector3(0.0f, local_y_position, 0.0f);

        var collider = go.AddComponent<BoxCollider>();
        //go.AddComponent<BracedZone>();
        go.layer = LayerMask.NameToLayer("BracedCollider");
        return collider;
    }

    void CreateClimbingNavMeshSurface_DoIt()
    {
        float W = 0.747f;

        var go = new GameObject("ClimbingNavMeshSurface");
        // var _climbing_nav_mesh = go.AddComponent<NavMeshSurface>();
        // _climbing_nav_mesh.agentTypeID = GameCore.GetNavMeshAgentID("Common").Value;
        // _climbing_nav_mesh.collectObjects = CollectObjects.Children;
        // _climbing_nav_mesh.defaultArea = UnityEngine.AI.NavMesh.GetAreaFromName("BracedSurface");
        // _climbing_nav_mesh.overrideVoxelSize = true;
        // _climbing_nav_mesh.voxelSize = 0.01f;
        go.transform.parent = this.gameObject.transform;

        go.transform.localPosition = Vector3.zero;
        go.transform.localRotation = Quaternion.identity;
        go.transform.localScale = Vector3.one;

        if (ForwardSide)
        {
            var box_a = CreateBox(go);
            box_a.transform.localScale = new Vector3(
                1.0f + W / transform.localScale.x,
                1.0f,
                W / transform.localScale.z
            );
            box_a.transform.localPosition = new Vector3(0.0f, 0.0f, 0.5f);
        }

        if (BackwardSide)
        {
            var box_b = CreateBox(go);
            box_b.transform.localScale = new Vector3(
                1.0f + W / transform.localScale.x,
                1.0f,
                W / transform.localScale.z
            );
            box_b.transform.localPosition = new Vector3(0.0f, 0.0f, -0.5f);
        }

        if (LeftSide)
        {
            var box_c = CreateBox(go);
            box_c.transform.localScale = new Vector3(
                W / transform.localScale.x,
                1.0f,
                1.0f + W / transform.localScale.z
            );
            box_c.transform.localPosition = new Vector3(0.5f, 0.0f, 0.0f);
        }

        if (RightSide)
        {
            var box_d = CreateBox(go);
            box_d.transform.localScale = new Vector3(
                W / transform.localScale.x,
                1.0f,
                1.0f + W / transform.localScale.z
            );
            box_d.transform.localPosition = new Vector3(-0.5f, 0.0f, 0.0f);
        }

        //_climbing_nav_mesh.BuildNavMesh();

        float Offset = 0.5f;
        var XInside = (0.5f * transform.localScale.x - Offset) / transform.localScale.x;
        var ZInside = (0.5f * transform.localScale.z - Offset) / transform.localScale.z;

        // MakeNavMeshLinks_Climbing(
        // 	source: _climbing_nav_mesh.gameObject,
        // 	density: 1.5f,
        // 	ZInside: ZInside,
        // 	XInside: XInside);
    }

    MyList<float> UniformesForCount(int count, float step)
    {
        MyList<float> result = new MyList<float>();

        if (count % 2 == 0)
        {
            for (int i = 0; i < count / 2; i++)
            {
                result.Add(0.0f + i * step + step / 2.0f);
                result.Add(0.0f - i * step - step / 2.0f);
            }
        }

        if (count % 2 == 1)
        {
            result.Add(0.0f);
            for (int i = 1; i <= count / 2; i++)
            {
                result.Add(0.0f + i * step);
                result.Add(0.0f - i * step);
            }
        }

        return result;
    }

#if UNITY_EDITOR
    [UnityEditor.MenuItem("Tools/CommonClimbingBlock/GenerateClimbingLinksForAll")]
    static void GenerateClimbingLinksForAll()
    {
        var climbing_blocks = GameObject.FindObjectsByType<CommonClimbingBlock>(
            FindObjectsSortMode.None
        );
        foreach (var block in climbing_blocks)
        {
            block.GenerateStairsLinks();
        }
        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(
            UnityEngine.SceneManagement.SceneManager.GetActiveScene()
        );
    }
#endif

    [ContextMenu("Make NavMesh Links Climbing")]
    public void MakeNavMeshLinks_Climbing_menu()
    {
        float Offset = 0.5f;
        var XInside = (0.5f * transform.localScale.x - Offset) / transform.localScale.x;
        var ZInside = (0.5f * transform.localScale.z - Offset) / transform.localScale.z;

        MakeNavMeshLinks_Climbing(
            source: this.gameObject,
            density: 1.5f,
            ZInside: ZInside,
            XInside: XInside
        );
    }

    void MakeNavMeshLinks_Climbing(GameObject source, float density, float ZInside, float XInside)
    {
        //float BotToBracedCost = 0.95f;
        //float TopToBracedCost = 2.0f;
        //float BotToTopCost = 0.95f;
        //float Density = 1.0f;

        var xmeters = transform.localScale.x;
        var zmeters = transform.localScale.z;

        var xcount = (int)(xmeters / density);
        var zcount = (int)(zmeters / density);

        var xstep_in_source = density / xmeters;
        var zstep_in_source = density / zmeters;

        MyList<float> xside = UniformesForCount(xcount, xstep_in_source);
        MyList<float> zside = UniformesForCount(zcount, zstep_in_source);

        foreach (var x in xside)
        {
            if (BackwardSide)
            {
                var apoint = transform.TransformPoint(new Vector3(x, 0.5f, -ZInside));
                var bpoint = transform.TransformPoint(new Vector3(x, 0.5f, -0.5f));
                NML_Utility.MakeLink(
                    a: apoint,
                    b: bpoint,
                    orientation: MathUtil.XZDirectionToQuaternion(
                        transform.TransformDirection(new Vector3(0.0f, 0.0f, 1.0f))
                    ),
                    storage_transform: source.transform,
                    storage_name: "ClimbingLinks",
                    area: (int)Areas.CLIMBING_LINK_AREA,
                    agent: GameCore.GetNavMeshAgentID("Common").Value
                );
            }
            // if (ForwardSide)
            // {
            // 	var apoint = transform.TransformPoint(new Vector3(x, 0.5f, ZInside));
            // 	var bpoint = transform.TransformPoint(new Vector3(x, 0.5f, 0.5f));
            // 	LinkData.ConstructLink(
            // 		start: apoint,
            // 		final: bpoint,
            // 		type: LinkType.Climb,
            // 		width: Density,
            // 		source: source,
            // 		cost: TopToBracedCost,
            // 		braced_coordinates: new BracedCoordinates(
            // 			braced_hit : apoint,
            // 			rotation: MathUtil.XZDirectionToQuaternion(
            // 				transform.TransformDirection(new Vector3(0.0f, 0.0f, -1.0f))
            // 			),
            // 			top_position: bpoint,
            // 			nav_position: apoint,
            // 			bot_position: null
            // 		));
            // }
        }

        foreach (var z in zside)
        {
            // if (LeftSide)
            // {
            // 	var apoint = transform.TransformPoint(new Vector3(-XInside, 0.5f, z));
            // 	var bpoint = transform.TransformPoint(new Vector3(-0.5f, 0.5f, z));
            // 	LinkData.ConstructLink(
            // 		start: apoint,
            // 		final: bpoint,
            // 		type: LinkType.Climb,
            // 		width: Density,
            // 		source: source,
            // 		cost: TopToBracedCost,
            // 		braced_coordinates: new BracedCoordinates(
            // 			braced_hit : apoint,
            // 			rotation: MathUtil.XZDirectionToQuaternion(
            // 				transform.TransformDirection(new Vector3(1.0f, 0.0f, 0.0f))
            // 			),
            // 			top_position: bpoint,
            // 			nav_position: apoint,
            // 			bot_position: null
            // 		));
            // }
            // if (RightSide)
            // {
            // 	var apoint = transform.TransformPoint(new Vector3(XInside, 0.5f, z));
            // 	var bpoint = transform.TransformPoint(new Vector3(0.5f, 0.5f, z));
            // 	LinkData.ConstructLink(
            // 		start: apoint,
            // 		final: bpoint,
            // 		type: LinkType.Climb,
            // 		width: Density,
            // 		source: source,
            // 		cost: TopToBracedCost,
            // 		braced_coordinates: new BracedCoordinates(
            // 			braced_hit : apoint,
            // 			rotation: MathUtil.XZDirectionToQuaternion(
            // 				transform.TransformDirection(new Vector3(-1.0f, 0.0f, 0.0f))
            // 			),
            // 			top_position: bpoint,
            // 			nav_position: apoint,
            // 			bot_position: null
            // 	));
            // }
        }
    }

    // public void Init()
    // {
    // 	XInside = (0.5f * transform.localScale.x - Offset) / transform.localScale.x;
    // 	ZInside = (0.5f * transform.localScale.z - Offset) / transform.localScale.z;

    // 	_source_collider = this.gameObject.GetComponent<BoxCollider>();
    // 	_climbing_collider = MakeBoxCollider();

    // 	MakeNavMeshLinks();
    // 	CreateClimbingNavMeshSurface();

    // 	NavMeshLinkSupervisor.Instance.RegisterClimbingBlock(this);
    // }
}
