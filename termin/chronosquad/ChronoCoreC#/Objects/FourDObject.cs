using System;
using System.Collections.Generic;

public class FourDObject
{
    long promise_start_step = long.MinValue;
    public List<ObjectOfTimeline> views = new List<ObjectOfTimeline>();
    public ObjectId id;

    public FourDObject() { }

    public bool IsUnical()
    {
        return views.Count == 1;
    }

    public void SetIdentifier(ObjectId id)
    {
        this.id = id;
    }

    void CheckValidity()
    {
        long iterator = promise_start_step;

        foreach (var view in views)
        {
            if (view.fourd_start != iterator)
            {
                throw new Exception(
                    "Invalid start step fs:" + view.fourd_start + " it:" + iterator
                );
            }

            iterator = view.fourd_finish;
        }

        if (iterator != long.MaxValue)
        {
            throw new Exception("Invalid finish step" + iterator);
        }
    }

    public void AddView(ObjectOfTimeline view)
    {
        //Debug.Log("AddView: " + view.fourd_start);

        if (views.Count != 0)
        {
            //Debug.Assert(view.fourd_start != views[views.Count - 1].fourd_start);
            if (view.fourd_start == views[views.Count - 1].fourd_start)
                throw new Exception("fourd_start step equality fourd_start: " + view.fourd_start);

            views[views.Count - 1].fourd_finish = view.fourd_start;
        }

        views.Add(view);
        CheckValidity();
    }

    public void RemoveView(ObjectOfTimeline view)
    {
        int index = views.IndexOf(view);
        if (index == -1)
        {
            throw new Exception("View not found");
        }

        if (index != 0)
        {
            views[index - 1].fourd_finish = view.fourd_finish;
        }

        views.Remove(view);
        CheckValidity();
    }

    public ObjectOfTimeline NextFrom(ObjectOfTimeline view)
    {
        int index = views.IndexOf(view);
        if (index == -1)
        {
            throw new Exception("View not found");
        }

        if (index + 1 >= views.Count)
        {
            return null;
        }

        return views[index + 1];
    }

    public FourDObject TearAfter(ObjectOfTimeline view)
    {
        List<ObjectOfTimeline> views_for_promise_fourd = new List<ObjectOfTimeline>();

        int index = views.IndexOf(view);

        for (int i = index + 1; i < views.Count; i++)
        {
            views_for_promise_fourd.Add(views[i]);
        }

        foreach (var view_for_promise_fourd in views_for_promise_fourd)
        {
            views.Remove(view_for_promise_fourd);
        }
        CheckValidity();

        var new_fourd = new FourDObject();
        foreach (var view_for_promise_fourd in views_for_promise_fourd)
        {
            new_fourd.AddView(view_for_promise_fourd);
        }
        new_fourd.promise_start_step = new_fourd.views[0].fourd_start;
        return new_fourd;
    }

    public void Tear(ObjectOfTimeline view, long tl_curstep)
    {
        var broken_step = view.ObjectTime().TimelineToBroken(tl_curstep);
        var next = NextFrom(view);
        next.fourd_start = broken_step;
        TearAfter(view);
    }

    public int CountOfViewedViews()
    {
        int count = 0;
        foreach (var view in views)
        {
            if (view.InBrokenInterval())
            {
                count++;
            }
        }
        return count;
    }
}
