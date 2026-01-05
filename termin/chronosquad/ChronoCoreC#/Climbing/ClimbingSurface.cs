// using System.Collections;
// using System.Collections.Generic;

// #if UNITY_64
// using UnityEngine;
// using UnityEngine.AI;
// #endif

// public class ClimbingSurface : MonoBehaviour
// {
// 	float SelfOffset = 0.5f;
// 	float Offset = 0.5f;


// 	float UpperOffset = 0.5f;

// 	Vector3 SelfTopPoint = new Vector3(0, 0.5f, 0.5f);
// 	Vector3 SelfTopPointTest;
// 	Vector3 SelfUpperTopPointTest;

// 	Vector3 SelfBottomPoint = new Vector3(0, 0.5f, -0.5f);

// 	Vector3 SelfBottomLinkPoint;
// 	Vector3 SelfTopLinkPoint;

// 	Vector3 SelfBottomPointTest;
// 	Vector3 SelfUpperBottomPointTest;


// 	GameObject _collider_go;

// 	//LinkData bottom_link_data;

// 	void MakeCollider()
// 	{
// 		_collider_go = new GameObject("ClimbingSurfaceCollider");
// 		_collider_go.transform.parent = this.transform;
// 		_collider_go.transform.localPosition = new Vector3(0, 0, 0);
// 		_collider_go.transform.localRotation = Quaternion.identity;
// 		_collider_go.transform.localScale = new Vector3(1, 1, 1);

// 		var collider = _collider_go.AddComponent<BoxCollider>();
// 		collider.size = new Vector3(1, 1, 1);
// 		collider.center = new Vector3(0, 0.3f / transform.localScale.y, 0);
// 	}

// 	void Start()
// 	{
// 		SelfTopPointTest = SelfTopPoint + new Vector3(0, Offset / transform.localScale.y, 0);
// 		SelfBottomPointTest = SelfBottomPoint + new Vector3(0, Offset / transform.localScale.y, 0);
// 		SelfBottomLinkPoint = SelfBottomPoint + new Vector3(0, 0, SelfOffset / transform.localScale.z);

// 		var top_test_point_in_global = transform.TransformPoint(SelfTopPointTest);

// 		var bottom_test_point_in_global = transform.TransformPoint(SelfBottomPointTest);

// 		var raycast_direction = bottom_test_point_in_global - top_test_point_in_global;
// 		var bottom_point_in_global = transform.TransformPoint(SelfBottomPoint);
// 		var top_point_in_global = transform.TransformPoint(SelfTopPoint);

// 		var self_bottom_link_point_in_global = transform.TransformPoint(SelfBottomLinkPoint);

// 		var width = transform.localScale.x;

// 		SelfUpperTopPointTest = SelfTopPoint + new Vector3(0, -UpperOffset / transform.localScale.y, UpperOffset / transform.localScale.z);
// 		SelfUpperBottomPointTest = SelfTopPoint + new Vector3(0, -UpperOffset / transform.localScale.y, 0);
// 		SelfTopLinkPoint = SelfTopPoint - new Vector3(0, 0, SelfOffset / transform.localScale.z);

// 		var self_upper_top_point_in_global = transform.TransformPoint(SelfUpperTopPointTest);
// 		var self_upper_bottom_point_in_global = transform.TransformPoint(SelfUpperBottomPointTest);

// 		var self_top_link_point_in_global = transform.TransformPoint(SelfTopLinkPoint);

// 		var layerMask = 1 << 0 | 1 << 6 | 1 << 10;

// 		RaycastHit hit;
// 		if (Physics.Raycast(top_test_point_in_global, raycast_direction, out hit, float.MaxValue, layerMask))
// 		{
// 				LinkData.ConstructLink(
// 					self_bottom_link_point_in_global,
// 					hit.point,
// 					source: this.gameObject,
// 					type: LinkType.Climb,
// 					width: width,
// 					braced_coordinates: new BracedCoordinates(
// 						hit.point,
// 						Quaternion.LookRotation(raycast_direction),
// 						hit.point,
// 						hit.point)
// 				);
// 		}
// 		else
// 		{
// 			Debug.LogError("no hit");
// 		}

// 		var raycast_direction2 = self_upper_bottom_point_in_global - self_upper_top_point_in_global;
// 		RaycastHit hit2;
// 		if (Physics.Raycast(self_upper_top_point_in_global, raycast_direction2, out hit2, float.MaxValue, layerMask))
// 		{
// 				LinkData.ConstructLink(
// 					self_top_link_point_in_global,
// 					hit2.point,
// 					source: this.gameObject,
// 					type: LinkType.Climb,
// 					width: width,
// 					braced_coordinates: new BracedCoordinates(
// 						hit.point,
// 						Quaternion.LookRotation(raycast_direction),
// 						hit.point,
// 						hit.point)
// 				);
// 		}
// 		else
// 		{
// 			Debug.LogError("no hit");
// 		}

// 		MakeCollider();
// 	}

// 	// Update is called once per frame
// 	void Update()
// 	{

// 	}
// }
