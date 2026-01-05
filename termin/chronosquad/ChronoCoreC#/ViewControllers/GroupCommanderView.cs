using System.Collections;
using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif

public class GroupCommanderView : ObjectController
{
    public List<GameObject> GroupMembers = new List<GameObject>();
    bool _inited = false;

    void Update() { }

    GroupController GroupController()
    {
        return GetObject() as GroupController;
    }

    public override void InitObjectController(ITimeline tl)
    {
        CreateObject<GroupController>(gameObject.name, tl);
    }

    public override void InitSecondPhase()
    {
        if (_inited)
            return;

        var commander = GroupController();
        foreach (var member in GroupMembers)
        {
            var member_controller = member.GetComponent<ObjectController>();
            commander.AddMember(member_controller.GetObject() as Actor);
        }
        _inited = true;
    }

    public void SetGroupCommander(GroupController commander)
    {
        SetObject(commander);
        _inited = true;
    }
}
