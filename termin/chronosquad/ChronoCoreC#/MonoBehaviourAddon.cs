using System.Collections;
using System.Collections.Generic;
using System;

#if UNITY_64
using UnityEngine;
#endif

public static class MonoBehaviourGetOrAddComponent
{
    public static T GetOrAddComponent<T>(this GameObject self) where T : Component, new()
    {
        T component = self.GetComponent<T>();
        return component != null ? component : self.AddComponent<T>() as T;
    }

    static public GameObject FindInChildOrCreate(
        this MonoBehaviour self,
        string name,
        GameObject prefab
    )
    {
        var child = self.transform.Find(name);
        if (child == null)
        {
            child = GameObject.Instantiate(prefab).transform;
            child.parent = self.transform;
            child.localPosition = Vector3.zero;
        }
        return child.gameObject;
    }
}
