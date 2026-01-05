// using System.Collections;
// using System.Collections.Generic;
// using UnityEngine;
// using UnityEngine.AI;
// using Unity.AI.Navigation;

// public class DynamicNavMeshUpdater : MonoBehaviour
// {
// 	public NavMeshSurface surface;
// 	public float updateInterval = 1.0f;
// 	private float timeSinceLastUpdate = 0.0f;

// 	private void OnEnable()
// 	{
// 		surface.BuildNavMesh();
// 	}

// 	private void Update()
// 	{
// 		timeSinceLastUpdate += Time.deltaTime;
// 		if (timeSinceLastUpdate > updateInterval)
// 		{
// 			surface.BuildNavMesh();
// 			timeSinceLastUpdate = 0.0f;
// 		}
// 	}

// 	// Start is called before the first frame update
// 	void Start()
// 	{

// 	}
// }
