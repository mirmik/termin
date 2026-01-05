using System;
using System.Collections.Generic;
using UnityEngine;

public class AutomaticDoorView : ObjectController
{
    bool _is_init = false;

    GameObject _close1 = null;
    GameObject _close2 = null;
    GameObject _open1 = null;
    GameObject _open2 = null;

    GameObject _model1 = null;

    GameObject _model2 = null;

    Vector3 _open_position1;
    Vector3 _open_position2;

    Vector3 _close_position1;
    Vector3 _close_position2;

    void Start()
    {
        if (_model != null)
        {
            _close1 = transform.Find("Close1").gameObject;
            _close2 = transform.Find("Close2").gameObject;
            _model1 = _close1.transform.Find("Model1").gameObject;
            _model2 = _close2.transform.Find("Model2").gameObject;
            _open1 = _close1.transform.Find("Open1").gameObject;
            _open2 = _close2.transform.Find("Open2").gameObject;

            _close_position1 = _close1.transform.localPosition;
            _close_position2 = _close2.transform.localPosition;
            _open_position1 = _open1.transform.localPosition + _close_position1;
            _open_position2 = _open2.transform.localPosition + _close_position2;

            _model1.transform.parent = _model.transform;
            _model2.transform.parent = _model.transform;
        }
    }

    public override void InitObjectController(ITimeline tl)
    {
        if (_is_init)
            return;
        CreateObject<AutomaticDoorObject>();
        _is_init = true;

        var door = GetObject() as AutomaticDoorObject;
        door.AddAbility(new OpenDoorAbility());
    }

    void Update()
    {
        var door = GetObject() as AutomaticDoorObject;
        if (door == null)
            return;

        var phase = door.Phase();

        if (_model1 != null)
        {
            _model1.transform.localPosition = Vector3.Lerp(
                _close_position1,
                _open_position1,
                phase
            );
            _model2.transform.localPosition = Vector3.Lerp(
                _close_position2,
                _open_position2,
                phase
            );
        }
    }

    public override void UpdateHideOrMaterial(
        ObjectOfTimeline guard,
        bool force_hide = false,
        bool always_visible = false
    )
    {
        return;
    }
}
