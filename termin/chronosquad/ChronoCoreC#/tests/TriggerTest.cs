#if !UNITY_64

public static class TriggerTests
{
    public static void TriggerTest(Checker checker)
    {
        var tl = new Timeline();
        var actor = new Actor();
        tl.AddObject("actor", actor);

        Quaternion q = Quaternion.identity;
        Vector3 v = new Vector3(10, 0, 0);
        Pose pose = new Pose(v, q);
        Vector3 size = new Vector3(2, 2, 2);

        var story_trigger = new StartDialogTrigger(new DialogueGraph("HelloWorld"));
        BoxColliderTrig trigger = new BoxColliderTrig(
            pose,
            size,
            Utility.StringHash("actor"),
            story_trigger
        );
        tl.AddTrigger(trigger);

        tl.Promote(50);

        actor.MoveToCommand(new Vector3(10, 0, 0));

        long step = 2500;
        tl.Promote(step);
        var text = tl.NarativeState.CompileText(step);
        checker.Equal(text, "HelloWorld");
    }

    public static void TimeTriggerTest(Checker checker)
    {
        var tl = new Timeline();
        var actor = new Actor();
        tl.AddObject("actor", actor);

        var story_trigger = new StartDialogTrigger(new DialogueGraph("HelloWorld"));
        TimeTrigger trigger = new TimeTrigger(500, story_trigger);
        tl.AddTrigger(trigger);

        tl.Promote(50);

        actor.MoveToCommand(new Vector3(10, 0, 0));

        long step = 600;
        tl.Promote(step);
        var text = tl.NarativeState.CompileText(step);
        checker.Equal(text, "HelloWorld");
    }
}

#endif
