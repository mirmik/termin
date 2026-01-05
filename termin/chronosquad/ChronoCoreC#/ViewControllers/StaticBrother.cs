using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Unity.AI.Navigation;

public class StaticBrother : MonoBehaviour
{
    void DisableAutoUpdateForAllLinksRecursively_Internal(Transform transform)
    {
        var link = transform.GetComponent<NavMeshLink>();
        if (link != null)
        {
            link.autoUpdate = false;
        }

        for (int i = 0; i < transform.childCount; i++)
        {
            DisableAutoUpdateForAllLinksRecursively_Internal(transform.GetChild(i));
        }
    }

    [ContextMenu("DisableAutoUpdateForAllLinksRecursively")]
    public void DisableAutoUpdateForAllLinksRecursively()
    {
        DisableAutoUpdateForAllLinksRecursively_Internal(transform);
    }

    void Start()
    {
        RemoveAllRenderersRecursively();
        RemoveAllCollidersRecursively();
    }

    void RemoveAllRenderersRecursively()
    {
        RemoveAllRenderersRecursively_Internal(transform);
    }

    void RemoveAllRenderersRecursively_Internal(Transform transform)
    {
        var renderer = transform.GetComponent<Renderer>();
        if (renderer != null)
        {
            DestroyImmediate(renderer);
        }

        for (int i = 0; i < transform.childCount; i++)
        {
            RemoveAllRenderersRecursively_Internal(transform.GetChild(i));
        }
    }

    void RemoveAllCollidersRecursively()
    {
        RemoveAllCollidersRecursively_Internal(transform);
    }

    void RemoveAllCollidersRecursively_Internal(Transform transform)
    {
        var collider = transform.GetComponent<Collider>();
        if (collider != null)
        {
            DestroyImmediate(collider);
        }

        for (int i = 0; i < transform.childCount; i++)
        {
            RemoveAllCollidersRecursively_Internal(transform.GetChild(i));
        }
    }
}
