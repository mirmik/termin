public abstract class GroupStrategy : EventCard<ObjectOfTimeline>
{
    public GroupStrategy(long step) : base(step, long.MaxValue) { }

    public abstract void Execute(ITimeline tl, ObjectOfTimeline group);

    public override void update(long step, ObjectOfTimeline priv)
    {
        var group = priv as GroupController;
        group.SetStrategy(this);
    }

    public override void on_leave(long step, ObjectOfTimeline priv)
    {
        var group = priv as GroupController;
        group.SetStrategy(null);
    }
}
