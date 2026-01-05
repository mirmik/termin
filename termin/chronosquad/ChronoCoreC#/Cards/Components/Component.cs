using System;
using System.Collections.Generic;

public abstract class ItemComponent
{
    protected ObjectOfTimeline _owner;
    bool _started = false;

    public ItemComponent(ObjectOfTimeline obj)
    {
        _owner = obj;
    }

    public virtual void ApplyInteraction(ObjectOfTimeline interacted) { }

    public ObjectOfTimeline Owner
    {
        get { return _owner; }
        set { SetOwner(value); }
    }

    public void SetOwner(ObjectOfTimeline newowner)
    {
        _owner = newowner;
    }

    public ITimeline GetTimeline()
    {
        return _owner.GetTimeline();
    }

    public virtual void OnAdd() { }

    public virtual void Start() { }

    public void InvokeStart()
    {
        if (!_started)
        {
            Start();
            _started = true;
        }
    }

    public virtual void Promote(long local_step) { }

    public virtual void Execute(long timeline_step, long local_step) { }

    public abstract ItemComponent Copy(ObjectOfTimeline newowner);
    public string Name => _owner.Name();
}
