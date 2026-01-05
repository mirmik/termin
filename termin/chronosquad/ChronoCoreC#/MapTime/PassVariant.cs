#if UNITY_64
using UnityEngine;
#endif

using System;
using System.Collections.Generic;

public struct PassVariantPathfindingResult
{
    MyList<Tuple<Timeline, long>> _path;

    public PassVariantPathfindingResult(MyList<Tuple<Timeline, long>> path)
    {
        _path = path;
    }

    public void AddNode(Timeline timeline, long step)
    {
        _path.Add(new Tuple<Timeline, long>(timeline, step));
    }
}

public struct PassVariantNode
{
    public PassVariantNode(Timeline timeline, long start, long finish)
    {
        this.timeline = timeline;
        this.start = start;
        this.finish = finish;
    }

    public Timeline timeline;
    public long start;
    public long finish;

    bool IsReversed()
    {
        return timeline.IsReversedPass();
    }
}

public class PassVariant
{
    MyList<PassVariantNode> _nodes = new MyList<PassVariantNode>();

    public PassVariant() { }

    public int Level
    {
        get { return _nodes.Count; }
    }

    public bool IsTimelineInVariant(Timeline timeline)
    {
        foreach (var node in _nodes)
        {
            if (node.timeline == timeline)
            {
                return true;
            }
        }
        return false;
    }

    public void AddNode(Timeline timeline, long start, long finish)
    {
        _nodes.Add(new PassVariantNode(timeline, start, finish));
    }

    public long BrokenLength
    {
        get
        {
            long length = 0;
            foreach (var node in _nodes)
            {
                length += node.finish - node.start;
            }
            return length;
        }
    }

    public long BrokenStepForTimelineStep(Timeline timeline, long step)
    {
        long brokenStep = 0;
        foreach (var node in _nodes)
        {
            if (node.timeline == timeline)
            {
                if (step < node.start)
                {
                    return brokenStep;
                }
                if (step < node.finish)
                {
                    return brokenStep + step - node.start;
                }
                brokenStep += node.finish - node.start;
            }
        }
        return brokenStep;
    }

    public Tuple<Timeline, long> TimelineStepForBrokenStep(long brokenStep)
    {
        foreach (var node in _nodes)
        {
            if (brokenStep < node.finish - node.start)
            {
                return new Tuple<Timeline, long>(node.timeline, node.start + brokenStep);
            }
            brokenStep -= node.finish - node.start;
        }
        return null;
    }

    public static int FindRootLevel(PassVariant a, PassVariant b)
    {
        int level = 0;
        int alevel = a.Level;
        int blevel = b.Level;
        while (level < alevel && level < blevel)
        {
            if (a._nodes[level].timeline != b._nodes[level].timeline)
            {
                break;
            }
            level++;
        }

        return level;
    }

    public static PassVariantPathfindingResult PassVariantPathfinding(PassVariant a, PassVariant b)
    {
        int root = FindRootLevel(a, b);

        PassVariantPathfindingResult result = new PassVariantPathfindingResult();

        for (int i = a.Level - 1; i >= root; i--)
        {
            result.AddNode(a._nodes[i].timeline, a._nodes[i].start);
        }

        for (int i = root; i < b.Level; i++)
        {
            result.AddNode(b._nodes[i].timeline, b._nodes[i].start);
        }

        return result;
    }
}
