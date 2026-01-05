#if UNITY_64
using UnityEngine;
#endif

using System;
using System.Collections.Generic;

public class CreateYetOnePointAction : NonObjectAction
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
            pe.CreateOneYet();
        }
    }

    public override string TooltipText()
    {
        return "Создать еще одну точку";
    }
}
