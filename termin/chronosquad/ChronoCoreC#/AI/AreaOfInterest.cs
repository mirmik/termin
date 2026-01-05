using UnityEngine;
using System.Collections.Generic;

public class PointOfInterest : IAStarNode
{
    public ReferencedPoint point;

    public string Name
    {
        get { return "interestpoint"; }
    }

    MyList<PointOfInterest> links = new MyList<PointOfInterest>();

    public PointOfInterest(ReferencedPoint vec)
    {
        point = vec;
    }

    public float HeuristicDistance(IAStarNode target)
    {
        var a = point.LocalPosition;
        var b = ((PointOfInterest)target).point.LocalPosition;
        return Vector3.Distance(a, b);
    }

    public MyList<IAStarEdge> EdgesOfThisNode(MyList<IAStarEdge> edges)
    {
        MyList<IAStarEdge> result = new MyList<IAStarEdge>();
        foreach (IAStarEdge edge in edges)
        {
            if (edge.Contains(this))
            {
                result.Add(edge);
            }
        }
        return result;
    }
}

public class ThreatFactor
{
    public Vector3 position;
    public Vector3 direction;
}

public class AreaOfInterest
{
    MyList<InterestAreaView> interest_areas = new MyList<InterestAreaView>();

    MyList<InterestPoint> interest_point_views = new MyList<InterestPoint>();
    MyList<PointOfInterest> interest_points = new MyList<PointOfInterest>();

    public AreaOfInterest()
    {
        //this.interest_points = interest_points;
    }

    public MyList<ObjectOfTimeline> GetALarmPatrol()
    {
        var result = new MyList<ObjectOfTimeline>();
        return result;
    }

    public PointOfInterest FindNearestInterestPoint(Vector3 glbpoint, Timeline timeline)
    {
        PointOfInterest nearest = null;
        float min_dist = float.MaxValue;

        foreach (PointOfInterest point in interest_points)
        {
            float dist = Vector3.Distance(glbpoint, point.point.GlobalPosition(timeline));
            if (dist < min_dist)
            {
                min_dist = dist;
                nearest = point;
            }
        }

        return nearest;
    }

    public void InvokeAlarmForActor_FoundAlarmSource(
        ObjectOfTimeline actor,
        ObjectOfTimeline corpse
    )
    {
        //var alarm_source = new FoundCorpseAlarmSource
        var alarm_source = new FoundCorpseAlarmSource(
            actor.GetTimeline().CurrentStep(),
            actor.GetTimeline().CurrentStep() + 3000,
            corpse.ObjectId()
        );

        actor.GetAttentionModule().AlarmSourcesList().Add(alarm_source);
    }

    public void InvokeAlarmInTimelineCorpse(Timeline timeline, ObjectOfTimeline corpse)
    {
        var alarm_patrol = GetALarmPatrol();

        foreach (ObjectOfTimeline actor in alarm_patrol)
        {
            InvokeAlarmForActor_FoundAlarmSource(actor, corpse);
        }
    }

    public void AddInterestPointsViews(MyList<InterestPoint> points)
    {
        foreach (InterestPoint point in points)
        {
            interest_point_views.Add(point);
        }
    }

    public void CompileInterestPoints()
    {
        interest_points.Clear();
        foreach (InterestPoint point in interest_point_views)
        {
            interest_points.Add(new PointOfInterest(point.GetReferencedPoint()));
        }
    }
}
