using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class EnvironmentSelfTester : MonoBehaviour
{
    MyList<GameObject> _objects = new MyList<GameObject>();

    // Start is called before the first frame update
    void Start()
    {
        var ground_layer = 1 << 6;
        var obstacle_layer = 1 << 9;
        var half_obstacle_layer = 1 << 14;
        var default_layer = 1 << 0;
        var mask = ground_layer | obstacle_layer | half_obstacle_layer | default_layer;

        var all_objects = GameObject.FindObjectsByType<GameObject>(FindObjectsSortMode.None);

        foreach (GameObject obj in all_objects)
        {
            var obj_layer_mask = 1 << obj.layer;
            if ((obj_layer_mask & mask) != 0)
            {
                _objects.Add(obj);
            }
        }

        return;
        //CheckColliders();
    }

    bool HasMesh(GameObject obj)
    {
        var mesh_filter = obj.GetComponent<MeshFilter>();
        if (mesh_filter != null)
            return true;

        var skinned_mesh_renderer = obj.GetComponent<SkinnedMeshRenderer>();
        if (skinned_mesh_renderer != null)
            return true;

        return false;
    }

    void CheckObject(GameObject obj)
    {
        try
        {
            if (!HasMesh(obj))
                return;

            var collider = obj.GetComponent<Collider>();

            if (collider == null || collider.isTrigger == true)
                Debug.LogError("Object has mesh but no collider: " + obj.name);
        }
        catch (System.Exception e)
        {
            Debug.Log("Exception: " + e.Message);
            Debug.Log("Object: " + obj.name);
        }
    }

    void CheckColliders()
    {
        foreach (GameObject obj in _objects)
        {
            CheckObject(obj);
        }
    }

    // Update is called once per frame
    void Update() { }
}
