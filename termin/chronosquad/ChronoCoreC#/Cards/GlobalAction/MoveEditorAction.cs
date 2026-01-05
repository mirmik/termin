#if UNITY_64
using UnityEngine;
#endif

using System;
using System.Collections.Generic;

public class MoveEditorAction : NonObjectAction
{
    public override void Init()
    {
        ManualAwake();
    }

    public override void OnIconClick()
    {
        var selected_object = EditorMarker.Instance.GetMarkedObject();
        var mouse_pos = Input.mousePosition;
        var click = GameCore.CursorEnvironmentHit(mouse_pos);
        var pe = selected_object.GetComponent<PatrolPointEditor>();
        if (pe != null)
        {
            pe.MoveEditorPoint(click.point);
        }
    }

    public override string TooltipText()
    {
        return "Переместить точку";
    }
}
