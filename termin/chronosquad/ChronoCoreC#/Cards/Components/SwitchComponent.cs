using System.Collections.Generic;

#if UNITY_64
using UnityEngine;
#endif
public class SwitchComponent : ItemComponent
{
    ObjectId door_id;

    public SwitchComponent(ObjectOfTimeline owner, ObjectId door_id) : base(owner)
    {
        this.door_id = door_id;
    }

    public override ItemComponent Copy(ObjectOfTimeline newowner)
    {
        var obj = new SwitchComponent(newowner, door_id);
        return obj;
    }

    public override void OnAdd()
    {
        _owner.SetInteraction(this);
    }

    public override void ApplyInteraction(ObjectOfTimeline interacted)
    {
        var door = Owner.GetTimeline().GetObject(door_id);
        door.AbilityUseSelf<OpenDoorAbility>();
    }
}
