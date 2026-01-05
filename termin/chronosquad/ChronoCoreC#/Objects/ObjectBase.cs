using UnityEngine;

public abstract class ObjectBase
{
    protected ITimeline _timeline;
    protected Pose _preevaluated_global_pose = Pose.Identity;
    public int _timeline_index = 0;
    public bool _active = false;
    protected ObjectId _object_id;

    public FourDObject fourd = null;
    public FourDObject FourD => fourd;
    public long fourd_start = long.MinValue;
    public long fourd_finish = long.MaxValue;

    protected ObjectTime _object_time = new ObjectTime();

    public void SetObjectTimeReferencePoint(long timeline_step, bool is_reversed, long offset = 0)
    {
        _object_time.SetReferencePoint(timeline_step, is_reversed, offset: offset);
    }

    public void SetReversed(bool is_reversed)
    {
        SetObjectTimeReferencePoint(_timeline.CurrentStep(), is_reversed);
        fourd_start = _object_time.BrokenTimelineZero;
    }

    public void TimeMultipliersPromote(long timeline_step)
    {
        _object_time.Promote(timeline_step);
    }

    public abstract ObjectOfTimeline Copy(ITimeline newtimeline);

    public Pose GlobalPose()
    {
        return _preevaluated_global_pose;
    }

    public virtual void OnEnable() { }

    public virtual void OnDisable() { }

    public void SetName(string name)
    {
        _object_id = new ObjectId(name);
        if (fourd.IsUnical())
        {
            fourd.SetIdentifier(_object_id);
        }
    }

    public string Name()
    {
        return _object_id.name;
    }

    public ObjectId ObjectId()
    {
        return _object_id;
    }
}
