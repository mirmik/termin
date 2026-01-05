#if UNITY_64
using UnityEngine;
#endif

using System;
using System.Collections.Generic;

public class RemoveEditorAction : NonObjectAction
{
    public override void Init()
    {
        ManualAwake();
    }

    public override void OnIconClick()
    {
        var selected_object = EditorMarker.Instance.GetMarkedObject();
        var pe = selected_object.GetComponent<PatrolPointEditor>();
        if (pe != null)
        {
            pe.RemoveThis();
        }
    }

    public override string TooltipText()
    {
        return "Удалить точку";
    }
}
