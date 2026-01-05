using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.AI;
using Unity.AI.Navigation;

public class BurrowAspect : ObjectController
{
    public List<GameObject> Objects = new List<GameObject>();

    [ContextMenu("MakeLinks")]
    public void MakeLinks()
    {
        CleanLinks();
        foreach (var obj in Objects)
        {
            MakeLink(
                obj.transform.position,
                transform.position,
                0.0f,
                Quaternion.identity,
                costModifier: 0
            );
        }
    }

    BurrowInternalAspect Aspect
    {
        get { return GetObject().GetComponent<BurrowInternalAspect>(); }
    }

    void Start()
    {
        foreach (var obj in Objects)
        {
            var burrow = obj.GetComponent<BurrowView>();
            Aspect.AddEntrance(burrow.name);
        }
    }

    public override void InitObjectController(ITimeline timeline)
    {
        var obj = CreateObject<PhysicalObject>(gameObject.name, timeline);
        obj.HasSpecificInteractionPose = UseInteractionPosition;
        var burrow = new BurrowInternalAspect(obj);
        obj.AddComponent(burrow);
    }

    void CleanLinks()
    {
        var links = transform.Find("Links");
        if (links != null)
        {
            DestroyImmediate(links.gameObject);
        }
    }

    public void MakeLink(
        Vector3 a,
        Vector3 b,
        float width,
        Quaternion orientation,
        int area = (int)Areas.BURROW_LINK_AREA,
        int costModifier = 0
    )
    {
        var links = transform.Find("Links");
        if (links == null)
        {
            links = new GameObject("Links").transform;
            links.parent = transform;
        }

        var link = new GameObject("Link");
        link.layer = (int)Layers.LINK_LAYER;
        link.transform.position = (a + b) / 2;
        link.transform.rotation = orientation;

        var aa = link.transform.InverseTransformPoint(a);
        var bb = link.transform.InverseTransformPoint(b);
        link.transform.parent = links;

        link.AddComponent<NavMeshLink>();
        var nav_mesh_link = link.GetComponent<NavMeshLink>();
        nav_mesh_link.startPoint = aa;
        nav_mesh_link.endPoint = bb;
        nav_mesh_link.width = width;
        nav_mesh_link.costModifier = costModifier;
        nav_mesh_link.bidirectional = true;
        nav_mesh_link.area = area;
        nav_mesh_link.agentTypeID = GameCore.GetNavMeshAgentID("S").Value;

#if UNITY_EDITOR
        // set it dirty
        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(gameObject.scene);
#endif
    }
}
