using System.Collections;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
using Unity.AI.Navigation;
using UnityEngine.AI;
#endif

public class SphericalNavMeshLinkGenerator : MonoBehaviour
{
    MyList<NavMeshLink> _links = new MyList<NavMeshLink>();
    float radius = 5.0f;

    private int? GetNavMeshAgentID(string name)
    {
        for (int i = 0; i < NavMesh.GetSettingsCount(); i++)
        {
            UnityEngine.AI.NavMeshBuildSettings settings = NavMesh.GetSettingsByIndex(index: i);
            if (name == NavMesh.GetSettingsNameFromID(agentTypeID: settings.agentTypeID))
            {
                return settings.agentTypeID;
            }
        }
        return null;
    }

    NavMeshLink CreateLink(Vector3 start_point, Vector3 end_point)
    {
        var link = new GameObject("Link").AddComponent<NavMeshLink>();
        link.transform.parent = transform;
        link.transform.localPosition = Vector3.zero;
        link.startPoint = start_point;
        link.endPoint = end_point;
        link.width = 2f;
        link.bidirectional = true;
        link.autoUpdate = true;
        link.area = 0;
        // found agent type 'S'
        link.agentTypeID = GetNavMeshAgentID("S").Value;
        link.tag = "Untagged";
        link.enabled = true;
        link.hideFlags = HideFlags.None;
        _links.Add(link);
        return link;
    }

    public void CreateLinkZ(float angle, Vector3 rotate)
    {
        float angle1 = angle + 5.0f;
        float angle2 = angle - 5.0f;

        var l = CreateLink(
            new Vector3(
                Mathf.Sin(angle1 * Mathf.Deg2Rad) * radius,
                Mathf.Cos(angle1 * Mathf.Deg2Rad) * radius,
                0
            ),
            new Vector3(
                Mathf.Sin(angle2 * Mathf.Deg2Rad) * radius,
                Mathf.Cos(angle2 * Mathf.Deg2Rad) * radius,
                0
            )
        );

        l.transform.Rotate(rotate);
    }

    // public void CreateLinkY(float angle)
    // {
    // 	float angle1 = angle + 5.0f;
    // 	float angle2 = angle - 5.0f;

    // 	var l = CreateLink(new Vector3(
    // 		Mathf.Sin(angle1 * Mathf.Deg2Rad) * radius,
    // 		0,
    // 		Mathf.Cos(angle1 * Mathf.Deg2Rad) * radius),
    // 		new Vector3(
    // 		Mathf.Sin(angle2 * Mathf.Deg2Rad) * radius,
    // 		0,
    // 		Mathf.Cos(angle2 * Mathf.Deg2Rad) * radius));
    // }

    // public void CreateLinkX(float angle)
    // {
    // 	float angle1 = angle + 5.0f;
    // 	float angle2 = angle - 5.0f;

    // 	var l = CreateLink(new Vector3(
    // 		0,
    // 		Mathf.Sin(angle1 * Mathf.Deg2Rad) * radius,
    // 		Mathf.Cos(angle1 * Mathf.Deg2Rad) * radius),
    // 		new Vector3(
    // 		0,
    // 		Mathf.Sin(angle2 * Mathf.Deg2Rad) * radius,
    // 		Mathf.Cos(angle2 * Mathf.Deg2Rad) * radius));
    // }

    void Start()
    {
        for (int i = 0; i < 4; i++)
            CreateLinkZ(45.0f + i * 90.0f, rotate: new Vector3(0, 0, 0));
        // for (int i = 0; i < 4; i++)
        // 	CreateLinkZ(45.0f + i * 90.0f, rotate:new Vector3(0,30,0));
        // for (int i = 0; i < 4; i++)
        // 	CreateLinkZ(45.0f + i * 90.0f, rotate:new Vector3(0,-30,0));

        for (int i = 0; i < 4; i++)
            CreateLinkZ(45.0f + i * 90.0f, rotate: new Vector3(0, 90, 0));

        for (int i = 0; i < 4; i++)
            CreateLinkZ(45.0f + i * 90.0f, rotate: new Vector3(90, 0, 0));
    }

    // Update is called once per frame
    void Update() { }
}
