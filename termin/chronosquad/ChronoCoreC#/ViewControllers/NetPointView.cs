using System.Collections;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

//[ExecuteAlways]
public class NetPointView : MonoBehaviour
{
    public List<NetPointView> _linked_with = new List<NetPointView>();
    ObjectController _object_controller;

    GameObject DevNullVisualisation;

    void Awake()
    {
        _object_controller = GetComponent<ObjectController>();
    }

    public void StartNetwork()
    {
        _object_controller.GetObject().AddComponent<NetPoint>();
        foreach (var linked_with in _linked_with)
        {
            if (linked_with == null)
            {
                continue;
            }
            _object_controller
                .GetObject()
                .GetComponent<NetPoint>()
                .AddLink(new ObjectId(linked_with.gameObject.name), false);
        }
    }

    public MyList<NetPointConnectionRec> GetLinks()
    {
        return _object_controller.GetObject().GetComponent<NetPoint>().GetLinks();
    }

    GameObject GetOrCreateDevNullVisualisation()
    {
        if (DevNullVisualisation == null)
        {
            DevNullVisualisation = GameObject.Instantiate(
                MaterialKeeper.Instance.GetPrefab("DevNullVisualisation")
            );
            Debug.Assert(DevNullVisualisation != null);
            DevNullVisualisation.name = "DevNullVisualisation";
            DevNullVisualisation.transform.SetParent(transform);
            DevNullVisualisation.transform.localPosition = new Vector3(0, 2, 0);
            DevNullVisualisation.transform.localRotation = Quaternion.identity;
            DevNullVisualisation.transform.localScale = Vector3.one;
        }
        return DevNullVisualisation;
    }

#if UNITY_EDITOR
    void DrawGizmos()
    {
        foreach (var linked_with in _linked_with)
        {
            if (linked_with == null)
            {
                continue;
            }
            Gizmos.color = new Color(0.0f, 0.8f, 0.8f, 1.0f);
            Gizmos.DrawLine(transform.position, linked_with.transform.position);
        }
    }
#endif

    void Update()
    {
        var obj = _object_controller.GetObject();
        var netpoint = obj.GetComponent<NetPoint>();
        var devnull = GetOrCreateDevNullVisualisation();

        bool need_active = netpoint.IsFormatThisNetpointActive();
        if (need_active && !devnull.activeSelf)
            devnull.SetActive(true);
        if (!need_active && devnull.activeSelf)
            devnull.SetActive(false);
    }

    void OnDrawGizmos()
    {
#if UNITY_EDITOR
        DrawGizmos();
#endif
    }
}
