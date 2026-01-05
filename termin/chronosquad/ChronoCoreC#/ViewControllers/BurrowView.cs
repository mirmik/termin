using System;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;

public class BurrowView : ObjectController
{
    //bool _is_init = false;
    ObjectController _object_controller;

    Dictionary<string, BurrowView_IntRecord> records =
        new Dictionary<string, BurrowView_IntRecord>();

    void Awake()
    {
        _object_controller = GetComponent<ObjectController>();
    }

    void Start() { }

    public override void InitObjectController(ITimeline timeline)
    {
        var obj = CreateObject<PhysicalObject>(gameObject.name, timeline);
        obj.HasSpecificInteractionPose = UseInteractionPosition;
        var burrow = new BurrowComponent(obj);
        obj.AddComponent(burrow);
    }

    MyList<string> NamesOfCovered()
    {
        var obj = _object_controller.GetObject();
        var book = obj.GetComponent<BurrowComponent>();
        if (book == null)
            return new MyList<string>();
        return book.NamesOfCovered();
    }

    void ZerrifyMarks()
    {
        foreach (var keyValue in records)
        {
            keyValue.Value.mark = 0;
        }
    }

    InAirIconView CreateIconFor(string name)
    {
        var curtlctr = GameCore.CurrentTimelineController();
        var objctr = curtlctr.GetObjectController(name);
        var iconed = objctr.GetComponent<IconedActor>();
        Image image = iconed.ActorIcon;

        var keeper = MaterialKeeper.Instance;
        GameObject icon_go = keeper.Instantiate("InAirIcon");
        InAirIconView icon = icon_go.GetComponent<InAirIconView>();
        icon.SetImage(image);
        icon.transform.SetParent(transform);
        records[name] = new BurrowView_IntRecord(1, icon);
        return icon;
    }

    void set_position_for_icon(InAirIconView icon, int no, int total)
    {
        var up = GameCore.CameraUp();
        icon.transform.localPosition = up * 1.0f + up * 0.5f * no;

        var direction_to_camera = GameCore.CameraPosition() - icon.transform.position;
        var rot = Quaternion.LookRotation(direction_to_camera, up);
        icon.transform.rotation = rot;
    }

    void Update()
    {
        ZerrifyMarks();
        var names = NamesOfCovered();

        foreach (var name in names)
        {
            InAirIconView icon;
            if (records.ContainsKey(name))
                icon = records[name].icon;
            else
                icon = CreateIconFor(name);
            records[name].mark = 1;
        }

        MyList<string> to_destroy = new MyList<string>();
        foreach (var keyValue in records)
        {
            var record = keyValue.Value;
            if (record.mark == 0)
            {
                var icon = record.icon;
                GameObject.Destroy(icon.gameObject);
                to_destroy.Add(keyValue.Key);
            }
        }

        foreach (var td in to_destroy)
        {
            records.Remove(td);
        }

        var count_of_icons = records.Count;
        int i = 0;
        foreach (var keyValue in records)
        {
            var record = keyValue.Value;
            set_position_for_icon(record.icon, i, count_of_icons);
            i++;
        }
    }
}

public class BurrowView_IntRecord
{
    public int mark;
    public InAirIconView icon;

    public BurrowView_IntRecord(int mark, InAirIconView icon)
    {
        this.mark = mark;
        this.icon = icon;
    }
}
