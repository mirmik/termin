using System.Collections;
using System.Collections.Generic;
using UnityEngine;

public class BurrowInternalAspect : ItemComponent
{
    MyList<string> _burrowed = new MyList<string>();
    MyList<string> _entrances = new MyList<string>();

    public BurrowInternalAspect(ObjectOfTimeline new_owner) : base(new_owner) { }

    public BurrowInternalAspect(string entrance, ObjectOfTimeline new_owner) : base(new_owner)
    {
        _entrances.Add(entrance);
    }

    public override ItemComponent Copy(ObjectOfTimeline new_owner)
    {
        if (_entrances.Count == 0)
        {
            return null;
        }

        var newaspect = new BurrowInternalAspect(new_owner);
        newaspect._burrowed = new MyList<string>(_burrowed);
        newaspect._entrances = new MyList<string>(_entrances);
        return newaspect;
    }

    public MyList<string> Burrowed()
    {
        return _burrowed;
    }

    public void Add(string name)
    {
        _burrowed.Add(name);
    }

    public void Remove(string name)
    {
        _burrowed.Remove(name);
    }

    public void Merge(BurrowInternalAspect aspect)
    {
        foreach (var name in aspect.Burrowed())
        {
            if (!_burrowed.Contains(name))
            {
                _burrowed.Add(name);
            }
        }

        foreach (var name in aspect._entrances)
        {
            if (!_entrances.Contains(name))
            {
                _entrances.Add(name);
            }
        }
    }

    public void RemoveEntrance(string name)
    {
        if (_entrances.Contains(name))
        {
            _entrances.Remove(name);
        }
    }

    public void AddEntrance(string name)
    {
        var timeline = _owner.GetTimeline();
        if (!_entrances.Contains(name))
        {
            _entrances.Add(name);
            var obj = timeline.GetObject(name);
            var burrow = obj.GetComponent<BurrowComponent>();
            burrow.BindBurrowAspect(Owner.Name());
        }
    }

    void UnboundBorrowEntrance(BurrowComponent burrow)
    {
        RemoveEntrance(burrow.Owner.Name());
    }

    // public void UpdateLinksToAspect(Timeline timeline)
    // {
    // 	foreach (var name in _entrances)
    // 	{
    // 		var obj = timeline.GetObject(name);
    // 		var burrow = obj.GetComponent<BurrowComponent>();
    // 		var aspect = burrow.Aspect;

    // 		if (aspect == this)
    // 			continue;

    // 		aspect.UnboundBorrowEntrance(burrow);
    // 		AddEntrance(name);
    // 	}
    // }
}

public class BurrowComponent : ItemComponent
{
    string _burrow_aspect;
    MyList<string> linked = new MyList<string>();

    public BurrowComponent(ObjectOfTimeline owner) : base(owner) { }

    public void BindBurrowAspect(string aspect)
    {
        _burrow_aspect = aspect;
    }

    public ObjectOfTimeline BurrowAspectObject()
    {
        return GetTimeline().GetObject(_burrow_aspect);
    }

    public BurrowInternalAspect BurrowAspect()
    {
        return BurrowAspectObject().GetComponent<BurrowInternalAspect>();
    }

    public ReferencedPose InteractionPose()
    {
        return BurrowAspectObject().CurrentReferencedPose();
    }

    public void BindBurrowAspect(string name, Timeline timeline)
    {
        BindBurrowAspect(name);
    }

    public bool Contains(string name)
    {
        return BurrowAspect().Burrowed().Contains(name);
    }

    public void AddLinked(string name)
    {
        linked.Add(name);
    }

    public MyList<string> NamesOfCovered()
    {
        return BurrowAspect().Burrowed();
    }

    public override ItemComponent Copy(ObjectOfTimeline newowner)
    {
        var newcomponent = new BurrowComponent(newowner);
        newcomponent._burrow_aspect = _burrow_aspect;
        return newcomponent;
    }

    // public void MergeBurrowAspects()
    // {
    // 	var myaspect = _burrow_aspect;
    // 	foreach (var name in linked)
    // 	{
    // 		var obj = GetTimeline().GetObject(name);
    // 		var burrow = obj.GetComponent<BurrowComponent>();
    // 		var aspect = burrow.Aspect;
    // 		myaspect.Merge(aspect);
    // 		myaspect.UpdateLinksToAspect(_owner.GetTimeline());
    // 	}
    // }

    public override void OnAdd()
    {
        _owner.SetInteraction(this);
        //BindBurrowAspect(_owner.Name());
        //MergeBurrowAspects();
    }

    public override void ApplyInteraction(ObjectOfTimeline interacted)
    {
        var hideevent = new HideIntoBurrow(
            GetTimeline().CurrentStep(),
            _burrow_aspect,
            interacted.Name()
        );
        GetTimeline().AddEvent(hideevent);
    }
}

public class HideIntoBurrow : EventCard<ITimeline>
{
    string _aspect_name;
    string _object_name;

    public HideIntoBurrow(long step, string aspect_name, string object_name) : base(step)
    {
        _aspect_name = aspect_name;
        _object_name = object_name;
    }

    public override void on_forward_enter(global::System.Int64 current_step, ITimeline tl)
    {
        var obj = tl.GetObject(_object_name);
        var aspect = obj.GetTimeline().GetObject(_aspect_name).GetComponent<BurrowInternalAspect>();
        if (aspect != null)
        {
            aspect.Add(obj.Name());
            obj.SetBurrowAspect(aspect);
        }
    }

    public override void on_backward_leave(global::System.Int64 current_step, ITimeline tl)
    {
        var obj = tl.GetObject(_object_name);
        var aspect = obj.GetTimeline().GetObject(_aspect_name).GetComponent<BurrowInternalAspect>();
        if (aspect != null)
        {
            aspect.Remove(obj.Name());
            obj.SetBurrowAspect(null);
        }
    }

    //BEGIN################################################################
    // This code was generated by FieldScanner

    public override long HashCode()
    {
        long result = 0;
        result = FieldScanner.ModifyHash(result, _aspect_name);
        result = FieldScanner.ModifyHash(result, _object_name);
        result = FieldScanner.ModifyHash(result, start_step);
        result = FieldScanner.ModifyHash(result, finish_step);
        return result;
    }

    public override bool Equals(object obj)
    {
        if (obj == null)
            return false;
        if (obj.GetType() != GetType())
            return false;
        var other = obj as HideIntoBurrow;
        return _aspect_name == other._aspect_name
            && _object_name == other._object_name
            && start_step == other.start_step
            && finish_step == other.finish_step
            && true;
    }

    public override int GetHashCode()
    {
        return (int)HashCode();
    }
    //END################################################################
}
