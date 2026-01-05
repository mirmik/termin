using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using MeshAnalyze;

public class Upstairs : MonoBehaviour
{
    public float height = 3.0f;

    GameObject GetModel()
    {
        return transform.Find("Surface/Model").gameObject;
    }

    [ContextMenu("Update Height")]
    void UpdateHeight()
    {
        var model = GetModel();

        model.transform.localScale = new Vector3(1, height, 0.1f);
        model.transform.localPosition = new Vector3(0, 0, -height / 2.0f);
    }

    public Bounds Bounds()
    {
        return GetModel().GetComponent<MeshRenderer>().bounds;
    }

    MyList<Wire> EvalHorizontalCorners()
    {
        var meshAnalyzer = new MeshAnalyzer(
            GetModel().GetComponent<MeshFilter>().sharedMesh,
            GetModel().transform
        );
        var wires = meshAnalyzer.FindAllTwoLeavesWires();
        Debug.Log("wires: " + wires.Count);
        var horizontal_wires = MeshAnalyzer.HorizontalWires(wires, Quaternion.identity);
        Debug.Log("horizontal_wires: " + horizontal_wires.Count);
        var horizontal_corners = MeshAnalyzer.FilterCorners(horizontal_wires);
        Debug.Log("horizontal_corners: " + horizontal_corners.Count);
        return horizontal_corners;
    }

    public BracedCoordinates BracedCoordinates()
    {
        return new BracedCoordinates(
            rotation: Quaternion.LookRotation(-transform.forward, transform.up)
        );
    }

    [ContextMenu("Generate Stairs Links")]
    void GenerateStairsLinks()
    {
        var horizontal_corners = EvalHorizontalCorners();
        NML_Utility.RemoveLinks(GetModel().transform);

        MyList<Wire> fcorners = new MyList<Wire>();
        Debug.Log("horizontal_corners: " + horizontal_corners.Count);
        foreach (var corner in horizontal_corners)
        {
            var center_point = GetModel().transform.InverseTransformPoint(corner.CenterPoint());
            if (center_point.z < -0.01f)
            {
                fcorners.Add(corner);
            }
        }

        Debug.Log("fcorners: " + fcorners.Count);

        if (fcorners.Count != 2)
        {
            Debug.Log("Not 2 corners");
        }

        var top = fcorners[0];
        var bot = fcorners[1];
        var top_point = top.CenterPoint();
        var bot_point = bot.CenterPoint();

        if (top_point.y < bot_point.y)
        {
            var tmp = top;
            bot = top;
            top = tmp;
            var tmpp = top_point;
            top_point = bot_point;
            bot_point = tmpp;
        }

        var back = GetModel().transform.TransformDirection(Vector3.back);
        var forw = GetModel().transform.TransformDirection(Vector3.forward);
        var up = GetModel().transform.TransformDirection(Vector3.up);
        var down = GetModel().transform.TransformDirection(Vector3.down);

        var link1 = NML_Utility.MakeLink(
            a: top_point + forw + down * 0.1f,
            b: top_point + up + back * 0.1f,
            orientation: Quaternion.LookRotation(back, up),
            area: (int)Areas.UPSTAIRS_AREA,
            storage_transform: GetModel().transform,
            agent: GameCore.GetNavMeshAgentID("Common").Value
        );
        var link2 = NML_Utility.MakeLink(
            a: bot_point + back + down * 0.1f,
            b: bot_point + down + back * 0.1f,
            orientation: Quaternion.LookRotation(forw, up),
            area: (int)Areas.UPSTAIRS_AREA,
            storage_transform: GetModel().transform,
            agent: GameCore.GetNavMeshAgentID("Common").Value
        );

#if UNITY_EDITOR
        UnityEditor.SceneManagement.EditorSceneManager.MarkSceneDirty(gameObject.scene);
#endif
    }
}
