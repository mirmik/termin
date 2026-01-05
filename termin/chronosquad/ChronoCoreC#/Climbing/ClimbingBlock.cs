// using System.Collections;
// using System.Collections.Generic;
// using System;

// #if UNITY_64
// using UnityEngine;
// using Unity.AI.Navigation;
// using UnityEngine.AI;
// #endif

// public class ClimbingBlock : MonoBehaviour
// {
// 	float BotToBracedCost = 0.95f;
// 	float TopToBracedCost = 2.0f;

// 	float BotToTopCost = 0.95f;

// 	BoxCollider _source_collider;
// 	BoxCollider _climbing_collider;

// 	public float Offset = 0.5f;
// 	public float Density = 1.0f;

// 	float XInside;
// 	float ZInside;

// 	public bool UpdateLinksRaycast = false;

// 	public bool ForwardSide = true;
// 	public bool BackwardSide = true;
// 	public bool LeftSide = true;
// 	public bool RightSide = true;

// 	NavMeshSurface _climbing_nav_mesh;
// 	MyList<GameObject> _climbing_nav_mesh_boxes;

// 	MyList<LinkData> _links_and_directions = new MyList<LinkData>();

// 	float BoxColliderTopYOffset = -0.05f;
// 	float BoxColliderBotYOffset = -1.0f;
// 		float Y = 1.5f;

// 	GameObject CreateBox(GameObject parent)
// 	{
// 		var go = GameObject.CreatePrimitive(PrimitiveType.Cube);
// 		go.transform.parent = parent.transform;
// 		go.transform.localPosition = Vector3.zero;
// 		go.transform.localRotation = Quaternion.identity;
// 		go.transform.localScale = Vector3.one;
// 		return go;
// 	}

// 	void CreateClimbingNavMeshSurface()
// 	{
// 		float W = 0.747f;

// 		var go = new GameObject("ClimbingNavMeshSurface");
// 		_climbing_nav_mesh = go.AddComponent<NavMeshSurface>();
// 		_climbing_nav_mesh.agentTypeID = GameCore.GetNavMeshAgentID("S").Value;
// 		_climbing_nav_mesh.collectObjects = CollectObjects.Children;
// 		_climbing_nav_mesh.defaultArea = UnityEngine.AI.NavMesh.GetAreaFromName("BracedSurface");
// 		go.transform.parent = this.gameObject.transform;

// 		go.transform.localPosition = Vector3.zero;
// 		go.transform.localRotation = Quaternion.identity;
// 		go.transform.localScale = Vector3.one;

// 		var box_a = CreateBox(go);
// 		var box_b = CreateBox(go);
// 		var box_c = CreateBox(go);
// 		var box_d = CreateBox(go);

// 		box_a.transform.localScale = new Vector3(1.0f + W / transform.localScale.x, 1.0f, W / transform.localScale.z);
// 		box_b.transform.localScale = new Vector3(1.0f + W / transform.localScale.x, 1.0f, W / transform.localScale.z);
// 		box_c.transform.localScale = new Vector3(W / transform.localScale.x, 1.0f, 1.0f + W / transform.localScale.z);
// 		box_d.transform.localScale = new Vector3(W / transform.localScale.x, 1.0f, 1.0f + W / transform.localScale.z);

// 		box_a.transform.localPosition = new Vector3(0.0f, 0.0f, 0.5f);
// 		box_b.transform.localPosition = new Vector3(0.0f, 0.0f, -0.5f);
// 		box_c.transform.localPosition = new Vector3(0.5f, 0.0f, 0.0f);
// 		box_d.transform.localPosition = new Vector3(-0.5f, 0.0f, 0.0f);

// 		_climbing_nav_mesh_boxes = new MyList<GameObject> {box_a, box_b, box_c, box_d};
// 		_climbing_nav_mesh.BuildNavMesh();

// 		box_a.SetActive(false);
// 		box_b.SetActive(false);
// 		box_c.SetActive(false);
// 		box_d.SetActive(false);

// 		MakeNavMeshLinks_Climbing();
// 	}

// 	void MakeNavMeshLinks_Climbing()
// 	{
// 		var xmeters = transform.localScale.x;
// 		var zmeters = transform.localScale.z;

// 		var xcount = (int)(xmeters / Density);
// 		var zcount = (int)(zmeters / Density);

// 		var xstep_in_source = Density / xmeters;
// 		var zstep_in_source = Density / zmeters;

// 		MyList<float> xside = UniformesForCount(xcount, xstep_in_source);
// 		MyList<float> zside = UniformesForCount(zcount, zstep_in_source);


// 		foreach (var x in xside)
// 		{
// 			if (BackwardSide)
// 			{
// 				var apoint = transform.TransformPoint(new Vector3(x, 0.5f, -ZInside));
// 				var bpoint = transform.TransformPoint(new Vector3(x, 0.5f, -0.5f));
// 				LinkData.ConstructLink(
// 					start: apoint,
// 					final: bpoint,
// 					type: LinkType.Climb,
// 					width: Density,
// 					source: _climbing_nav_mesh.gameObject,
// 					cost: TopToBracedCost,
// 					braced_coordinates: new BracedCoordinates(
// 						braced_hit : apoint,
// 						rotation: MathUtil.XZDirectionToQuaternion(
// 							transform.TransformDirection(new Vector3(0.0f, 0.0f, 1.0f))
// 						),
// 						top_position: bpoint,
// 						nav_position: apoint,
// 						bot_position: null
// 					));
// 			}
// 			if (ForwardSide)
// 			{
// 				var apoint = transform.TransformPoint(new Vector3(x, 0.5f, ZInside));
// 				var bpoint = transform.TransformPoint(new Vector3(x, 0.5f, 0.5f));
// 				LinkData.ConstructLink(
// 					start: apoint,
// 					final: bpoint,
// 					type: LinkType.Climb,
// 					width: Density,
// 					source: _climbing_nav_mesh.gameObject,
// 					cost: TopToBracedCost,
// 					braced_coordinates: new BracedCoordinates(
// 						braced_hit : apoint,
// 						rotation: MathUtil.XZDirectionToQuaternion(
// 							transform.TransformDirection(new Vector3(0.0f, 0.0f, -1.0f))
// 						),
// 						top_position: bpoint,
// 						nav_position: apoint,
// 						bot_position: null
// 					));
// 			}
// 		}

// 		foreach (var z in zside)
// 		{
// 			if (LeftSide)
// 			{
// 				var apoint = transform.TransformPoint(new Vector3(-XInside, 0.5f, z));
// 				var bpoint = transform.TransformPoint(new Vector3(-0.5f, 0.5f, z));
// 				LinkData.ConstructLink(
// 					start: apoint,
// 					final: bpoint,
// 					type: LinkType.Climb,
// 					width: Density,
// 					source: _climbing_nav_mesh.gameObject,
// 					cost: TopToBracedCost,
// 					braced_coordinates: new BracedCoordinates(
// 						braced_hit : apoint,
// 						rotation: MathUtil.XZDirectionToQuaternion(
// 							transform.TransformDirection(new Vector3(1.0f, 0.0f, 0.0f))
// 						),
// 						top_position: bpoint,
// 						nav_position: apoint,
// 						bot_position: null
// 					));
// 			}
// 			if (RightSide)
// 			{
// 				var apoint = transform.TransformPoint(new Vector3(XInside, 0.5f, z));
// 				var bpoint = transform.TransformPoint(new Vector3(0.5f, 0.5f, z));
// 				LinkData.ConstructLink(
// 					start: apoint,
// 					final: bpoint,
// 					type: LinkType.Climb,
// 					width: Density,
// 					source: _climbing_nav_mesh.gameObject,
// 					cost: TopToBracedCost,
// 					braced_coordinates: new BracedCoordinates(
// 						braced_hit : apoint,
// 						rotation: MathUtil.XZDirectionToQuaternion(
// 							transform.TransformDirection(new Vector3(-1.0f, 0.0f, 0.0f))
// 						),
// 						top_position: bpoint,
// 						nav_position: apoint,
// 						bot_position: null
// 				));
// 			}
// 		}
// 	}

// 	BoxCollider MakeBoxCollider()
// 	{
// 		var cgo = this.gameObject;
// 		var go = new GameObject("BracedCollider");

// 		go.transform.parent = cgo.transform;
// 		go.transform.localRotation = Quaternion.identity;


// 		var global_x_size = cgo.transform.localScale.x + 0.2f;
// 		var global_y_size = BoxColliderTopYOffset - BoxColliderBotYOffset;
// 		var global_z_size = cgo.transform.localScale.z + 0.2f;

// 		var local_x_size = global_x_size / cgo.transform.localScale.x;
// 		var local_y_size = global_y_size / cgo.transform.localScale.y;
// 		var local_z_size = global_z_size / cgo.transform.localScale.z;

// 		var global_y_position = cgo.transform.localScale.y / 2.0f
// 			+ BoxColliderBotYOffset
// 			+ (BoxColliderTopYOffset - BoxColliderBotYOffset) / 2.0f;

// 		var local_y_position = global_y_position / cgo.transform.localScale.y;

// 		go.transform.localScale = new Vector3(local_x_size, local_y_size, local_z_size);

// 		go.transform.localPosition = new Vector3(
// 			0.0f,
// 			local_y_position,
// 			0.0f);


// 		var collider = go.AddComponent<BoxCollider>();
// 		go.layer = LayerMask.NameToLayer("BracedCollider");
// 		return collider;
// 	}

// 	float Length0(Vector3 pos_in_source)
// 	{
// 		var length0 = Mathf.Abs(pos_in_source.y);

// 		if (length0 < Mathf.Abs(pos_in_source.x))
// 		{
// 			length0 = Mathf.Abs(pos_in_source.x);
// 		}

// 		if (length0 < Mathf.Abs(pos_in_source.z))
// 		{
// 			length0 = Mathf.Abs(pos_in_source.z);
// 		}

// 		return length0;
// 	}

// 	Vector3 Normalize0(Vector3 pos_in_source)
// 	{
// 		var length0 = Length0(pos_in_source);
// 		return pos_in_source / length0;
// 	}

// 	Vector3 DirectionFromPos(Vector3 pos_in_source)
// 	{
// 		Vector3 dir_in_source =new Vector3(-1.0f, 0, 0);
// 		if (Mathf.Abs(pos_in_source.x - 0.5f) < 0.01f)
// 			dir_in_source = new Vector3(-0.5f, 0, 0);
// 		if (Mathf.Abs(pos_in_source.x + 0.5f) < 0.01f)
// 			dir_in_source = new Vector3(0.5f, 0, 0);
// 		if (Mathf.Abs(pos_in_source.z - 0.5f) < 0.01f)
// 			dir_in_source = new Vector3(0, 0, -1.0f);
// 		if (Mathf.Abs(pos_in_source.z + 0.5f) < 0.01f)
// 			dir_in_source = new Vector3(0, 0, 1.0f);
// 		return dir_in_source;
// 	}

// 	Vector3 Clamp(Vector3 pos_in_source, float min, float max)
// 	{
// 		var x = Mathf.Clamp(pos_in_source.x, min, max);
// 		var y = Mathf.Clamp(pos_in_source.y, min, max);
// 		var z = Mathf.Clamp(pos_in_source.z, min, max);
// 		return new Vector3(x, y, z);
// 	}

// 	public bool InMyZone(Vector3 global_pos)
// 	{
// 		Vector3 source_pos = transform.InverseTransformPoint(global_pos);
// 		Vector3 abs_source_pos = new Vector3(
// 			Mathf.Abs(source_pos.x),
// 			Mathf.Abs(source_pos.y),
// 			Mathf.Abs(source_pos.z));

// 		return  abs_source_pos.x < (0.5f + 0.5f / transform.localScale.x)
// 			&&  abs_source_pos.y < (0.5f + 0.5f / transform.localScale.y)
// 			&&  abs_source_pos.z < (0.5f + 0.5f / transform.localScale.z);
// 	}

// 	public BracedCoordinates GetBracedCoordinates(Vector3 glbpos)
// 	{
// 		var center_of_source = this.gameObject.transform.position;

// 		var pos_in_source = this.gameObject.transform
// 			.InverseTransformPoint(glbpos);

// 		var down_direction = -this.transform.up;

// 		pos_in_source = Clamp(pos_in_source, -0.5f, 0.5f);
// 		pos_in_source.y = 0.5f;
// 		var top_position = this.gameObject.transform.TransformPoint(pos_in_source);

// 		Vector3 dir_in_source = DirectionFromPos(pos_in_source);

// 		var dir_in_global = this.gameObject.transform.TransformDirection(dir_in_source).normalized;
// 		var dir_to_bot_in_global = (-dir_in_global + down_direction * Y).normalized;


// 		Vector3? bot_position;
// 		RaycastHit hit;
// 		var layerMask = 1 << LayerMask.NameToLayer("FieldOfView") | 1 << 0 | 1 << 6;

// 		if (!Physics.Raycast(
// 			top_position + dir_to_bot_in_global * 0.1f, dir_to_bot_in_global, out hit, Mathf.Infinity, layerMask))
// 		{
// 			bot_position = null;
// 		}
// 		else {
// 			bot_position = hit.point;
// 		}

// 		var rotation = MathUtil.XZDirectionToQuaternion(dir_in_global);
// 		BracedCoordinates bc = new BracedCoordinates(
// 			braced_hit : glbpos,
// 			rotation: rotation,
// 			top_position: top_position,
// 			nav_position: top_position + (rotation * Vector3.forward) * 0.5f,
// 			bot_position: bot_position
// 		);
// 		return bc;
// 	}

// 	MyList<float> UniformesForCount(int count, float step)
// 	{

// 		MyList<float> result = new MyList<float>();

// 		if (count % 2 == 0)
// 		{
// 			for (int i = 0; i < count / 2; i++)
// 			{
// 				result.Add(0.0f + i * step + step / 2.0f);
// 				result.Add(0.0f - i * step - step / 2.0f);
// 			}
// 		}

// 		if (count % 2 == 1)
// 		{
// 			result.Add(0.0f);
// 			for (int i = 1; i <= count / 2; i++)
// 			{
// 				result.Add(0.0f + i * step);
// 				result.Add(0.0f - i * step);
// 			}
// 		}

// 		return result;
// 	}

// 	void MakeNavMeshLinks()
// 	{
// 		var xmeters = transform.localScale.x;
// 		var zmeters = transform.localScale.z;

// 		var xcount = (int)(xmeters / Density);
// 		var zcount = (int)(zmeters / Density);

// 		var xstep_in_source = Density / xmeters;
// 		var zstep_in_source = Density / zmeters;

// 		MyList<float> xside = UniformesForCount(xcount, xstep_in_source);
// 		MyList<float> zside = UniformesForCount(zcount, zstep_in_source);

// 		foreach (var x in xside)
// 		{
// 			if (BackwardSide)
// 				MakeLinkForPoint(
// 					new Vector3(x, 0.5f, -ZInside),
// 					new Vector3(x, 0.5f, -0.5f),
// 					new Vector3(0.0f,-Y,-1.0f));
// 			if (ForwardSide)
// 				MakeLinkForPoint(
// 					new Vector3(x, 0.5f, ZInside),
// 					new Vector3(x, 0.5f, 0.5f),
// 					new Vector3(0.0f,-Y,1.0f));
// 		}

// 		foreach (var z in zside)
// 		{
// 			if (LeftSide)
// 				MakeLinkForPoint(
// 					new Vector3(-XInside, 0.5f, z),
// 					new Vector3(-0.5f, 0.5f, z),
// 					new Vector3(-1.0f,-Y,0.0f));
// 			if (RightSide)
// 				MakeLinkForPoint(
// 					new Vector3(XInside, 0.5f, z),
// 					new Vector3(0.5f, 0.5f, z),
// 					new Vector3(1.0f,-Y,0.0f));
// 		}
// 	}

// 	void UpdateLinksRaycast_DoIt()
// 	{
// 		foreach (var link_and_direction in _links_and_directions)
// 		{
// 			link_and_direction.UpdateFromLinkData();
// 		}
// 	}

// 	void MakeLinkForPoint(
// 		Vector3 pos_in_source,
// 		Vector3 pos_in_source_noinside,
// 		Vector3 direction_in_source)
// 	{
// 		var direction_in_global = transform.TransformDirection(direction_in_source);
// 		var pos_in_global = transform.TransformPoint(pos_in_source);
// 		var pos_in_global_noinside = transform.TransformPoint(pos_in_source_noinside);
// 		var	pos_in_global_end = pos_in_global + direction_in_global * 1.0f;

// 		BracedCoordinates braced_coordinates = new BracedCoordinates(
// 			braced_hit : pos_in_global,
// 			rotation: MathUtil.XZDirectionToQuaternion(-direction_in_global),
// 			top_position: pos_in_global_noinside,
// 			nav_position: pos_in_global + direction_in_global * 0.5f,
// 			bot_position: null
// 		);

// 		var link = LinkData.ConstructLink(
// 			start: pos_in_global,
// 			final: pos_in_global_end,
// 			type: LinkType.JumpBraced,
// 			width: Density,
// 			source: this.gameObject,
// 			braced_coordinates: braced_coordinates,
// 			cost: BotToTopCost);
// 		link.UpdateFromLinkData();

// 		var link2 = LinkData.ConstructLink(
// 			start: pos_in_global_noinside,
// 			final: pos_in_global_end,
// 			type: LinkType.JumpBraced,
// 			width: Density,
// 			source: this.gameObject,
// 			braced_coordinates: braced_coordinates,
// 			cost: BotToBracedCost);
// 		link2.UpdateFromLinkData();
// 	}

// 	public void Init()
// 	{
// 		XInside = (0.5f * transform.localScale.x - Offset) / transform.localScale.x;
// 		ZInside = (0.5f * transform.localScale.z - Offset) / transform.localScale.z;

// 		_source_collider = this.gameObject.GetComponent<BoxCollider>();
// 		_climbing_collider = MakeBoxCollider();

// 		MakeNavMeshLinks();
// 		CreateClimbingNavMeshSurface();

// 		NavMeshLinkSupervisor.Instance.RegisterClimbingBlock(this);
// 	}

// 	void Update()
// 	{
// 		if (UpdateLinksRaycast)
// 			UpdateLinksRaycast_DoIt();
// 	}


// }
