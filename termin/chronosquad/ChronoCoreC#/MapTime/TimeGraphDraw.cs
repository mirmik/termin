#if UNITY_64
using UnityEngine;
#endif

using System.Collections.Generic;

public class TimelineGraphDraw
{
    TimelineGraph _timeline_graph;

    Timeline tl;
    Timeline parent_timeline = null;
    ArrowMeshObject arrowMeshObject;
    ArrowMeshObject sub_arrowMeshObject;

    TimelineCursor _timeline_cursor;

    public float Level;

    public TimelineGraphDraw(Timeline tl, GameObject canvas, TimelineGraph _timeline_graph)
    {
        this._timeline_graph = _timeline_graph;
        this.tl = tl;
        arrowMeshObject = new ArrowMeshObject(canvas);
        sub_arrowMeshObject = new ArrowMeshObject(canvas);
        sub_arrowMeshObject.SetWidth(3.0f);

        var parent_timeline_key = tl.PrimaryEntrancePoint.parent_timeline_key;
        if (parent_timeline_key != null)
        {
            _timeline_graph.TimelineDraws.TryGetValue(
                parent_timeline_key,
                out var parent_timeline_draw
            );
            if (parent_timeline_draw == null)
            {
                return;
            }
            parent_timeline = parent_timeline_draw.Timeline;
        }

        var timelineCursor_go = new GameObject("TimelineCursor");
        _timeline_cursor = timelineCursor_go.AddComponent<TimelineCursor>();
    }

    public float DistanceToMainArrow(Vector2 vector2)
    {
        return arrowMeshObject.DistanceTo(vector2);
    }

    public Vector2 FindNearestMainPoint(Vector2 pnt)
    {
        return arrowMeshObject.FindNearest(pnt);
    }

    public Timeline Timeline => tl;

    public void SetLevel(float val)
    {
        Level = val;
    }

    public long ParentStart()
    {
        return tl.PrimaryEntrancePoint.parent_step;
    }

    // public void UpdateCoordinates(float left, float right)
    // {
    // 	float multiplier = 1000;
    // 	float l = Start() / multiplier;
    // 	float r = Maximal() / multiplier;

    // 	arrowMeshObject.SetPoints(new Vector3(l, Level, 0), new Vector3(r, Level, 0));
    // }

    public void UpdateCoordinates()
    {
        long start = Start();
        long maximal = Maximal();
        long minimal = Minimal();

        if (arrowMeshObject != null)
            arrowMeshObject.SetPoints(
                new Vector3(minimal, Level, 0),
                new Vector3(maximal, Level, 0)
            );

        var current_step = tl.CurrentStep();

        if (_timeline_cursor == null)
            return;

        _timeline_cursor.SetPosition(new Vector3(current_step, Level, 0));

        var parent = Parent();
        if (parent != null)
        {
            var entry_point = tl.PrimaryEntrancePoint;
            var parent_level = parent.Level;
            sub_arrowMeshObject.SetPoints(
                new Vector3(entry_point.parent_step, parent_level, 0),
                new Vector3(entry_point.child_step, Level, 0)
            );
        }

        arrowMeshObject.SetIsCurrent(tl.IsCurrent());
    }

    public bool HasParent()
    {
        return parent_timeline != null;
    }

    public TimelineGraphDraw Parent()
    {
        if (tl.PrimaryEntrancePoint != null && tl.PrimaryEntrancePoint.parent_timeline_key != null)
            return _timeline_graph.TimelineDraws[tl.PrimaryEntrancePoint.parent_timeline_key];
        return null;
    }

    public long Minimal()
    {
        return tl.LastNegativeTimelineStep();
    }

    public long Start()
    {
        return tl.PrimaryEntranceStep();
    }

    public long Maximal()
    {
        return tl.LastPositiveTimelineStep();
    }

    long StepForPoint(Vector2 pnt)
    {
        var nearest = FindNearestMainPoint(pnt);
        var step = (long)nearest.x;
        return step;
    }

    public void OnClick(Vector2 pnt)
    {
        var chronosphere = tl.GetChronosphere();
        if (chronosphere.CurrentTimeline() != tl)
            chronosphere.SetCurrentTimeline(tl);

        if (chronosphere.IsPaused())
        {
            var step_for_pnt = StepForPoint(pnt);
            chronosphere.SetTargetTimeInPauseMode(step_for_pnt / Utility.GAME_GLOBAL_FREQUENCY);
        }
        else
            tl.Promote(StepForPoint(pnt));
    }
}
