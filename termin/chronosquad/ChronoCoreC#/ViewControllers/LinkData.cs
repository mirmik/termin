#if UNITY_64
using UnityEngine;
using Unity.AI.Navigation;
using UnityEngine.AI;
#endif

using System.Collections.Generic;

public enum LinkType
{
    Walk,
    JumpBraced,
    Climb,
    Door,
    Portal
}

public class LinkData
{
    public float MaxBiDirectionalDistance = 4.5f;
    public float MaxOneDirectionalDistance = float.MaxValue;

    public NavMeshLinkData link;
    public NavMeshLinkInstance instance;
    public Vector3 direction_in_source;
    public Vector3 position_in_source;
    public GameObject source;

    public BoxCollider collider;

    string ColliderName => "NavMeshLinkColliderCoordination";

    BracedCoordinates _braced_coordinates;

    public LinkData(
        NavMeshLinkData link,
        NavMeshLinkInstance instance,
        GameObject source,
        Vector3 direction_in_source,
        Vector3 position_in_source,
        //LinkInGameHighlighter link_highliter,
        BracedCoordinates braced_coordinates = default,
        string ColliderName = "NavMeshLinkColliderCoordination"
    )
    {
        this.link = link;
        this.source = source;
        this.direction_in_source = direction_in_source;
        this.position_in_source = position_in_source;
        this.instance = instance;
        //this.link_highliter = link_highliter;
        _braced_coordinates = braced_coordinates;
    }

    public string info()
    {
        return "LinkData: "
            + link.startPosition
            + " "
            + link.endPosition
            + " area:"
            + link.area
            + " agentID:"
            + link.agentTypeID
            + " source:"
            + source.name;
    }

    public BracedCoordinates BracedCoordinates()
    {
        return _braced_coordinates;
    }

    // Dispose
    public void OnRemove()
    {
        NavMesh.RemoveLink(instance);
        //link_highliter.Disable(new Vector3(0,0,0), new Vector3(0,0,0));
    }

    static string AreaNameByLinkType(LinkType type)
    {
        switch (type)
        {
            case LinkType.Walk:
                return "Walking";
            case LinkType.JumpBraced:
                return "Braced";
            case LinkType.Climb:
                return "ClimbingLink";
            case LinkType.Door:
                return "DoorLink";
            case LinkType.Portal:
                return "Portal";
            default:
                return "Walking";
        }
    }

    // static public LinkData ConstructLink(
    // 	Vector3 start,
    // 	Vector3 final,
    // 	GameObject source,
    // 	LinkType type,
    // 	float width = 0.5f,
    // 	BracedCoordinates braced_coordinates = default,
    // 	float cost = 2.0f,
    // 	string ColliderName = "NavMeshLinkColliderCoordination")
    // {
    // 	var link = new NavMeshLinkData();
    // 	//var link_highliter_object = new GameObject("LinkInGameHighlighter")
    // 	//	.AddComponent<LinkInGameHighlighter>();
    // 	link.agentTypeID = GameCore.GetNavMeshAgentID("S").Value;
    // 	var area_name = AreaNameByLinkType(type);
    // 	link.area = UnityEngine.AI.NavMesh.GetAreaFromName(area_name);
    // 	link.bidirectional = true;
    // 	link.width = width;
    // 	link.costModifier = cost;

    // 	//link_highliter_object.transform.parent = source.transform;
    // 	//link_highliter_object.transform.localPosition = Vector3.zero;
    // 	link.startPosition = start;
    // 	link.endPosition = final;
    // 	NavMeshLinkInstance result = UnityEngine.AI.NavMesh.AddLink(link);

    // 	result.owner = source;

    // 	var link_data = new LinkData(
    // 		link : link,
    // 		instance : result,
    // 		direction_in_source : source.transform.InverseTransformDirection(final - start),
    // 		position_in_source : source.transform.InverseTransformPoint(start),
    // 	//	link_highliter : link_highliter_object,
    // 		source : source,
    // 		braced_coordinates : braced_coordinates,
    // 		ColliderName : ColliderName
    // 	);

    // 	link_data.UpdateCollider();
    // 	link_data.UpdateHighLigter();
    // 	NavMeshLinkSupervisor.Instance.AddLink(link_data);
    // 	return link_data;
    // }

    void UpdateRaycast()
    {
        NavMesh.RemoveLink(instance);

        var direction_in_global = source.transform.TransformDirection(direction_in_source);
        var pos_in_global = source.transform.TransformPoint(position_in_source);
        int layerMask = 1 << LayerMask.NameToLayer("FieldOfView");

        RaycastHit hit;
        if (
            !Physics.Raycast(
                pos_in_global + direction_in_global * 0.01f,
                direction_in_global,
                out hit,
                Mathf.Infinity,
                layerMask
            )
        )
        {
            //link_highliter.Disable(pos_in_global, direction_in_global);
            return;
        }
        var pos_in_global_end = hit.point;

        link.startPosition = pos_in_global;
        link.endPosition = pos_in_global_end;

        float distance = Vector3.Distance(link.startPosition, link.endPosition);
        if (distance > MaxBiDirectionalDistance)
        {
            link.bidirectional = false;
        }
        else
        {
            link.bidirectional = true;
        }

        if (distance > MaxOneDirectionalDistance)
        {
            //link_highliter.Disable(pos_in_global, direction_in_global);
            return;
        }

        instance = NavMesh.AddLink(link);

        Color color;
        if (link.bidirectional)
            color = new Color(1, 0, 1);
        else
            color = Color.red;
        //link_highliter.UpdateFromLinkData(this, color);
    }

    public void UpdateFromLinkData()
    {
        UpdateRaycast();
        UpdateCollider();
    }

    public void UpdateHighLigter()
    {
        var color = Color.white;
        //link_highliter.UpdateFromLinkData(this, color);
    }

    public void UpdateCollider()
    {
        if (collider != null)
        {
            //GameObject.Destroy(collider.gameObject);
            UpdateColliderGameObjectForNavMeshLink(collider, this);
            return;
        }
        collider = MakeColliderGameObjectForNavMeshLink(this, ColliderName);
    }

    static BoxCollider MakeColliderGameObjectForNavMeshLink(
        LinkData lnk,
        string ColliderName = "NavMeshLinkColliderCoordination"
    )
    {
        var go = new GameObject(ColliderName);
        var collider = go.AddComponent<BoxCollider>();
        var link_data_store = go.AddComponent<LinkDataStore>();
        link_data_store.link_data = lnk;
        UpdateColliderGameObjectForNavMeshLink(collider, lnk);
        go.transform.parent = lnk.source.transform;
        return collider;
    }

    static void UpdateColliderGameObjectForNavMeshLink(BoxCollider collider, LinkData lnk)
    {
        var go = collider.gameObject;

        float width = lnk.link.width;
        Vector3 start = lnk.link.startPosition;
        Vector3 final = lnk.link.endPosition;

        Vector3 center = (start + final) / 2;
        Vector3 direction = final - start;
        float diff_length = direction.magnitude;

        if (width < 0.1f)
        {
            width = 0.1f;
        }

        collider.size = new Vector3(width, 0.1f, diff_length);
        go.transform.position = center;
        go.transform.rotation = Quaternion.LookRotation(direction, Vector3.up);

        go.layer = LayerMask.NameToLayer("NavMeshLinkColliderCoordination");
    }
}
