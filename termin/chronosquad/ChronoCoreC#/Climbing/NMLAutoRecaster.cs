using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Unity.AI.Navigation;

public class NMLAutoRecasterUpDown : MonoBehaviour
{
    public NavMeshLink _link;
    public Vector3 _cast_start;
    public Vector3 _cast_dir;

    // void Awake()
    // {
    // 	_link = GetComponent<NavMeshLink>();
    // }

    public void SetLink(NavMeshLink link)
    {
        _link = link;
    }

    public void SetCastStart(Vector3 start)
    {
        _cast_start = start;
    }

    public void SetCastDir(Vector3 dir)
    {
        _cast_dir = dir;
    }

    public void SetCastGlobalStart(Vector3 start)
    {
        _cast_start = _link.transform.InverseTransformPoint(start);
    }

    public void SetCastGlobalDir(Vector3 dir)
    {
        _cast_dir = _link.transform.InverseTransformDirection(dir);
    }

    public Vector3 CastGlobal(out bool success)
    {
        var start = _link.transform.TransformPoint(_cast_start);
        var dir = _link.transform.TransformDirection(_cast_dir);

        RaycastHit hit;
        if (Physics.Raycast(start, dir, out hit, 1000, 1 << 0))
        {
            success = true;
            return hit.point;
        }
        success = false;
        return Vector3.zero;
    }

    public void ReCastDownLinkPoint()
    {
        var cast = CastGlobal(out bool success);
        if (!success)
            return;
        _link.endPoint = _link.transform.InverseTransformPoint(cast);
    }

    void Update()
    {
        ReCastDownLinkPoint();
    }
}
