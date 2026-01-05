using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class SlugSnipeAction : TargetChooseAction
{
    public float ShootDistance = 50.0f;

    public GameObject Slug;

    SlugSnipeAction() : base(KeyCode.G) { }

    protected override Ability MakeAbility()
    {
        string slug_name = Slug.name;
        var ability = new SlugSnipeAbility(shoot_distance: ShootDistance, slug_name: slug_name);
        return ability;
    }

    public override string TooltipText()
    {
        return "Выстрелить дроном";
    }

    protected override void ActionTo(GameObject other)
    {
        var objctr = other.GetComponent<ObjectController>();
        var tl = objctr.GetObject().GetTimeline();
        _actor.GetObject().AbilityUseOnObject<SlugSnipeAbility>(objctr.GetObject());
    }

    public override bool CanUseOnObject(GameObject other)
    {
        var objctr = other.GetComponent<ObjectController>();
        var tl = objctr.GetObject().GetTimeline();
        return _actor.GetObject().CanUseAbility<SlugSnipeAbility>(objctr.GetObject());
    }

    protected override void ActionToEnvironment(ReferencedPoint target)
    {
        _actor.GetObject().AbilityUseOnEnvironment<SlugSnipeAbility>(target);
    }

    public bool IsSlugOnBase()
    {
        var current_timeline = GameCore.CurrentTimeline();
        ObjectId slug_name = new ObjectId(Slug.name);
        var slug = current_timeline.GetObject(slug_name);
        var slug_hosted = slug._hosted;
        var meobjid = _actor.GetObject().ObjectId();
        if (slug_hosted == meobjid)
        {
            return true;
        }
        return false;
    }

    public override void OnIconClick()
    {
        if (IsSlugOnBase() == false)
        {
            var current_timeline = GameCore.CurrentTimeline();
            ObjectId slug_name = new ObjectId(Slug.name);
            var slug = current_timeline.GetObject(slug_name);
            GameCore.CurrentTimeline().GetChronoSphere().Select(slug);
            return;
        }

        base.OnIconClick();
    }
}
