class RecombinateAbility : Ability
{
    public RecombinateAbility() { }

    bool HasLinked(IAbilityListPanel last_used_stamp)
    {
        var _actor = last_used_stamp.Actor();
        return _actor.LinkedInTimeWithName() != null;
    }

    public override void UseSelfImpl(ITimeline tl, IAbilityListPanel last_used_stamp)
    {
        var _actor = last_used_stamp.Actor();
        if (HasLinked(last_used_stamp))
        {
            var rcmd = new RestoreReverseCommand(
                _actor.LinkedObjectInTime().ObjectId(),
                _actor.LocalStep() + 1
            );
            _actor.AddExternalCommand(rcmd);
            return;
        }
    }
}
