#if !UNITY_64
public static class AttentionTestClass
{
    public static void AttentionTest(Checker checker)
    {
        ChronoSphere chronosphere = new ChronoSphere();
        var tl = chronosphere.CreateEmptyTimeline();
        var lure = tl.CreateObject<PhysicalObject>("lure");
        var guard = tl.CreateObject<Actor>("guard");
        var lure_component = new LureComponent(lure);
        lure_component.EnableLuring(true);
        guard.SetDirection(new Vector3(1, 0, 0));

        lure.DisableBehaviour();
        lure.SetPosition(new Vector3(3, 0, 0));
        lure.AddComponent(lure_component);

        guard.SetAiController(new BasicAiController(guard));
        var patrol = (BasicAiController)guard.AiController();
        patrol.AddCommander(new GuardReactionCommander(), "reaction", 1);

        tl.Promote(100);
        checker.Equal(guard.Direction(), new Vector3(1, 0, 0), 0.1f);
        checker.Equal(lure.Position(), new Vector3(3, 0, 0), 0.1f);
    }
}

#endif
