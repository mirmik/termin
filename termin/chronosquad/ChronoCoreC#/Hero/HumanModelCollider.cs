using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class HumanModelCollider : MonoBehaviour
{
    public float scale = 1.0f;
    float OVERLAP_RADIUS = 0.023f;

    MyList<GameObject> _childs = new MyList<GameObject>();

    void FindChildsRecursive(GameObject obj, MyList<GameObject> list)
    {
        foreach (Transform child in obj.transform)
        {
            list.Add(child.gameObject);
            FindChildsRecursive(child.gameObject, list);
        }
    }

    [ContextMenu("RemoveAllColliders")]
    void RemoveAllColliders()
    {
        _childs.Clear();
        FindChildsRecursive(this.gameObject, _childs);
        foreach (GameObject child in _childs)
        {
            Collider[] colliders = child.GetComponents<Collider>();
            foreach (Collider collider in colliders)
            {
                DestroyImmediate(collider);
            }
        }

        // make scene dirty
#if UNITY_EDITOR
        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(gameObject.scene);
#endif
    }

    [ContextMenu("AddColliders")]
    void AddColliders()
    {
        RemoveAllColliders();
        bool is_effect = gameObject.layer == 13;

        _childs.Clear();
        FindChildsRecursive(this.gameObject, _childs);
        foreach (GameObject child in _childs)
        {
            if (is_effect)
                child.layer = 13;
            else
                child.layer = 11;

            if (child.name.EndsWith("Spine"))
            {
                CapsuleCollider collider = child.GetOrAddComponent<CapsuleCollider>();
                collider.radius = 0.014f + OVERLAP_RADIUS * scale;
                collider.height = 0.06f;
                collider.center = new Vector3(0, 0.003f, 0.001f);
            }
            else if (child.name.Contains("Head") && !child.name.Contains("HeadTop"))
            {
                SphereCollider collider = child.GetOrAddComponent<SphereCollider>();
                collider.radius = 0.011f * scale + OVERLAP_RADIUS * scale;
                collider.center = new Vector3(0, 0.009f * scale, 0.003f * scale);
            }
            else if (child.name.Contains("LeftUpLeg") || child.name.Contains("RightUpLeg"))
            {
                CapsuleCollider collider = child.GetOrAddComponent<CapsuleCollider>();
                collider.radius = 0.008f + OVERLAP_RADIUS * scale;
                collider.height = 0.05f * scale;
                collider.center = new Vector3(0, 0.02f * scale, 0);
            }
            else if (child.name.Contains("LeftLeg") || child.name.Contains("RightLeg"))
            {
                CapsuleCollider collider = child.GetOrAddComponent<CapsuleCollider>();
                collider.radius = 0.008f + OVERLAP_RADIUS * scale;
                collider.height = 0.05f * scale;
                collider.center = new Vector3(0, 0.02f * scale, 0);
            }
            else if (child.name.Contains("LeftArm") || child.name.Contains("RightArm"))
            {
                CapsuleCollider collider = child.GetOrAddComponent<CapsuleCollider>();
                collider.radius = 0.006f + OVERLAP_RADIUS * scale;
                collider.height = 0.03f * scale;
                collider.center = new Vector3(0, 0.01f * scale, 0);
            }
            else if (child.name.Contains("LeftForeArm") || child.name.Contains("RightForeArm"))
            {
                CapsuleCollider collider = child.GetOrAddComponent<CapsuleCollider>();
                collider.radius = 0.006f + OVERLAP_RADIUS * scale;
                collider.height = 0.03f * scale;
                collider.center = new Vector3(0, 0.01f * scale, 0);
            }
            else if (child.name.Contains("LeftFoot") || child.name.Contains("RightFoot"))
            {
                CapsuleCollider collider = child.GetOrAddComponent<CapsuleCollider>();
                collider.radius = 0.008f + OVERLAP_RADIUS * scale;
                collider.height = 0.03f * scale;
                collider.center = new Vector3(0, 0.007f * scale, 0);
            }
            else if (child.name.EndsWith("LeftHand") || child.name.EndsWith("RightHand"))
            {
                CapsuleCollider collider = child.GetOrAddComponent<CapsuleCollider>();
                collider.radius = 0.008f + OVERLAP_RADIUS * scale;
                collider.height = 0.03f * scale;
                collider.center = new Vector3(0, 0.007f * scale, 0);
            }
        }

        // make scene dirty
#if UNITY_EDITOR
        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(gameObject.scene);
#endif
    }

    // Update is called once per frame
    void Update() { }
}
