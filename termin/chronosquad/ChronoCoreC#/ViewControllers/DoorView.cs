using System.Collections;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
using UnityEngine.AI;
#endif

public class DoorView : ObjectController
{
    LinkData _link_data;

    Vector3 _forward_point;
    Vector3 _backward_point;

    Vector3 _forward_point_hit;
    Vector3 _backward_point_hit;

    public BracedCoordinates BracedCoordinates(Vector3 exit_side)
    {
        var distance_to_forward = Vector3.Distance(_forward_point_hit, exit_side);
        var distance_to_backward = Vector3.Distance(_backward_point_hit, exit_side);

        if (distance_to_forward > distance_to_backward)
            return new BracedCoordinates(
                top_position: _forward_point_hit,
                braced_hit: _forward_point_hit,
                rotation: Quaternion.LookRotation(_backward_point_hit - _forward_point_hit),
                nav_position: _forward_point_hit,
                bot_position: _backward_point_hit
            );
        else
            return new BracedCoordinates(
                top_position: _backward_point_hit,
                braced_hit: _backward_point_hit,
                rotation: Quaternion.LookRotation(_forward_point_hit - _backward_point_hit),
                nav_position: _backward_point_hit,
                bot_position: _forward_point_hit
            );
    }

    // public void MakeDoorLink()
    // {
    // 	_link_data = LinkData.ConstructLink(
    // 		_forward_point_hit,
    // 		_backward_point_hit,
    // 		source: this.gameObject,
    // 		type: LinkType.Door,
    // 		width: 0.0f,
    // 		braced_coordinates: new BracedCoordinates(
    // 			top_position: _backward_point_hit,
    // 			braced_hit: _backward_point_hit,
    // 			rotation: Quaternion.LookRotation(_forward_point_hit - _backward_point_hit),
    // 			nav_position: _backward_point_hit,
    // 			bot_position: _forward_point_hit
    // 	));

    // 	_link_data.collider.name = "DoorCollider";
    // }

    [ContextMenu("Make door link")]
    public void MakeDoorLink2()
    {
        Init();
        NML_Utility.RemoveLinks(transform);
        NML_Utility.MakeLink(
            a: _forward_point_hit,
            b: _backward_point_hit,
            orientation: transform.rotation,
            area: (int)Areas.DOOR_LINK_AREA,
            storage_transform: transform,
            agent: GameCore.GetNavMeshAgentID("Common").Value
        );
    }

    void Start()
    {
        Init();
    }

    void Init()
    {
        _forward_point = transform.TransformPoint(new Vector3(0.5f, 0, 0));
        _backward_point = transform.TransformPoint(new Vector3(-0.5f, 0, 0));

        RaycastHit hit;
        var layerMask = 1 << 0 | 1 << 6 | 1 << 10;

        if (Physics.Raycast(_forward_point, -transform.up, out hit, Mathf.Infinity, layerMask))
        {
            _forward_point_hit = hit.point;
        }
        else
        {
            _forward_point_hit = _forward_point;
        }

        if (Physics.Raycast(_backward_point, -transform.up, out hit, Mathf.Infinity, layerMask))
        {
            _backward_point_hit = hit.point;
        }
        else
        {
            _backward_point_hit = _backward_point;
        }
    }

    public override void InitObjectController(ITimeline tl)
    {
        CreateObject<DoorObject>(name, tl);
    }

    public override void UpdateView()
    {
        var object_of_timeline = GetObject();
        Pose pose = object_of_timeline.PoseProphet();
        transform.position = pose.position;
        transform.rotation = pose.rotation;
    }
}
