class ReturnToMasterAbility : Ability
{
    public ObjectId master_name;

    public ReturnToMasterAbility(ObjectId master_name) : base(cooldown: 0.0f)
    {
        this.master_name = master_name;
    }

    public override void UseSelfImpl(ITimeline tl, IAbilityListPanel last_used_stamp)
    {
        var _actor = last_used_stamp.Actor();

        var rcmd = new ReturnToMasterCommand(master_name, _actor.LocalStep() + 1);
        _actor.AddExternalCommand(rcmd);
    }
}
