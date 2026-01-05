using System.Collections.Generic;
using UnityEngine;

public abstract class EventCard<T> : BasicMultipleAction where T : class
{
    public EventCard(long step) : base(step, step) { }

    public EventCard(long sstep, long fstep) : base(sstep, fstep) { }

    public virtual void on_forward_enter(long current_step, T obj) { }

    public virtual void on_forward_leave(long current_step, T obj) { }

    public virtual void on_backward_enter(long current_step, T obj) { }

    public virtual void on_backward_leave(long current_step, T obj) { }

    public virtual void on_leave(long current_step, T obj) { }

    public virtual void on_enter(long current_step, T obj) { }

    public virtual void update(long current_step, T obj) { }
};

public class EventLine<T> where T : class
{
    public MultipleActionList<EventCard<T>> list;

    // public MyList<EventCard<T>> AsList()
    // {
    // 	return list.AsList();
    // }

    public void Clean()
    {
        list.Clean();
    }

    public string Info()
    {
        string s = "EventLine: size: " + list.CountOfCards();
        var lst = list.AsList();
        foreach (var ev in lst)
        {
            if (ev == null)
            {
                s += "\nnull";
                continue;
            }
            s += "\n" + ev.info();
        }
        return s;
    }

    public EventLine(bool stub)
    {
        list = new MultipleActionList<EventCard<T>>(true);
    }

    public EventLine(EventLine<T> other)
    {
        list = new MultipleActionList<EventCard<T>>(other.list);
    }

    public void Add(EventCard<T> card)
    {
        list.Add(card);
    }

    public long PromotionStep()
    {
        return list.PromotionStep();
    }

    public void Promote(long curstep, T priv)
    {
        MyList<EventCard<T>> added;
        MyList<EventCard<T>> goned;
        TimeDirection direction;
        list.Promote(curstep, out added, out goned, out direction);

        foreach (var ev in added)
        {
            if (ev == null)
                continue;

            if (direction == TimeDirection.Forward)
                ev.on_forward_enter(curstep, priv);
            else
                ev.on_backward_enter(curstep, priv);

            ev.on_enter(curstep, priv);
        }

        foreach (var ev in goned)
        {
            if (ev == null)
                continue;

            if (direction == TimeDirection.Forward)
                ev.on_forward_leave(curstep, priv);
            else
                ev.on_backward_leave(curstep, priv);
            ev.on_leave(curstep, priv);
        }

        foreach (var ev in list.ActiveStates())
        {
            if (ev == null)
                continue;

            ev.update(curstep, priv);
        }
    }

    public MyList<EventCard<T>> ActiveStates() => list.ActiveStates();

    public void DropToCurrentState()
    {
        list.DropToCurrentState();
    }

    public void DropToCurrentStateInverted()
    {
        list.DropToCurrentStateInverted();
    }

    public int CountOfCards()
    {
        return list.CountOfCards();
    }

    public int Count => list.Count;

    public void RemoveByHashCode(long hash) => list.RemoveByHashCode(hash);

    public MultipleActionList<EventCard<T>> MyList => list;

    public bool ContainsHash(long hash) => list.ContainsHash(hash);

    public bool IsEqual(EventLine<T> other) => list.IsEqual(other.list);

    public Dictionary<string, object> ToTrent()
    {
        var dct = new Dictionary<string, object>();
        dct.Add("list", list.ToTrent());
        return dct;
    }

    public void FromTrent(MyDictionary<string, object> dict)
    {
        list.FromTrent((Dictionary<string, object>)dict["list"]);
    }
}
