#if !UNITY_64
[Serializable]
class CommandMock : ActorCommand
{
    public CommandMock(long add_step) : base(add_step) { }

    public CommandMock(long s, long f) : base(s, f) { }

    public override bool Execute(ObjectOfTimeline actor, ITimeline timeline)
    {
        return true;
    }

    public override long HashCode()
    {
        long result = 0;
        result += start_step.GetHashCode();
        result += finish_step.GetHashCode() * 131231;
        return result;
    }
}

static class CommandBufferTests
{
    static public void MoveTest(Checker checker)
    {
        var tl = new Timeline();
        var guard = new Actor("obj");
        tl.AddObject(guard);

        var command_queue = guard.CommandBuffer().GetCommandQueue();
        checker.Equal(command_queue.Count, 0);

        var cmd1 = new MovingCommand(
            new ReferencedPoint(new Vector3(1, 0, 0), null),
            WalkingType.Walk,
            guard.LocalStep() + 1
        );
        guard.AddExternalCommand(cmd1);
        checker.Equal(guard.Position(), new Vector3(0, 0, 0));
        checker.Equal(command_queue.Count, 1);
        checker.Equal(command_queue.ByStartIteratorPosition(), -1);
        //checker.Equal(command_queue.ByFinishIteratorPosition(), 0);

        tl.Promote(2000);
        //checker.Equal(command_queue.ByStartIteratorPosition(), 1);
        //checker.Equal(command_queue.ByFinishIteratorPosition(), -1);
        checker.Equal(guard.Position(), new Vector3(1, 0, 0));
    }

    static public void MoveTestInReversePass(Checker checker)
    {
        var tl = new Timeline();
        tl.SetMinimalStep(long.MinValue);
        tl.SetReversedPass(true);
        var guard = new Actor("guard");
        tl.AddObject(guard);

        guard.SetObjectTimeReferencePoint(0, true);

        var command_queue = guard.CommandBuffer().GetCommandQueue();
        checker.Equal(command_queue.Count, 0);

        tl.Promote(-2000);
        checker.Equal(tl.CurrentStep(), (long)-2000);
        checker.Equal(guard.LocalStep(), (long)2000);

        var cmd1 = new MovingCommand(
            new ReferencedPoint(new Vector3(1, 0, 0), null),
            WalkingType.Walk,
            guard.LocalStep() + 1
        );
        guard.AddExternalCommand(cmd1);

        checker.Equal(cmd1.StartStep, (long)2001);
        checker.Equal(cmd1.FinishStep, (long)long.MaxValue);

        checker.Equal(guard.Position(), new Vector3(0, 0, 0));
        checker.Equal(command_queue.Count, 1);
        //checker.Equal(command_queue.ByStartIteratorPosition(), -1);
        //checker.Equal(command_queue.ByFinishIteratorPosition(), 0);

        tl.Promote(-4000);
        checker.Equal(guard.LocalStep(), (long)4000);

        //checker.Equal(command_queue.ByStartIteratorPosition(), 1);
        //checker.Equal(command_queue.ByFinishIteratorPosition(), -1);
        checker.Equal(guard.Position(), new Vector3(1, 0, 0));
    }
}
#endif
