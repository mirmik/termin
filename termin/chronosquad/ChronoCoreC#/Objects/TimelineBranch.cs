using UnityEngine;
using System.Collections;
using System.Collections.Generic;

class TimelineFork
{
    long step;
    ObjectId from;
    ObjectId to;

    //TimeDirection direction;

    public TimelineFork(long step, ObjectId from, ObjectId to)
    {
        this.step = step;
        this.from = from;
        this.to = to;
    }
}

public class TimelineBranch
{
    MyList<TimelineFork> forks;

    //long current_step;

    public void AddFork(long step, ObjectId from, ObjectId to)
    {
        forks.Add(new TimelineFork(step, from, to));
    }
}

class Iggdrasil
{
    List<TimelineBranch> branches;
    TimelineBranch current_branch;

    public Iggdrasil()
    {
        branches = new List<TimelineBranch>();
        current_branch = new TimelineBranch();
        branches.Add(current_branch);
    }

    public void AddBranch(TimelineBranch branch)
    {
        branches.Add(branch);
    }
}
