#if !UNITY_64
public static class SituationTestClass
{
    public static void IdleTest(Checker checker)
    {
        Actor obj = new Actor();
        Timeline timeline = new Timeline();
        timeline.AddObject("obj", obj);

        timeline.PromoteToTime(1.0f);
        checker.Equal(obj.Animatronics().Count, 1);
        checker.Equal(obj.Animatronics().AsList()[0].GetType(), typeof(IdleAnimatronic));
    }

    public static void MoveTest(Checker checker)
    {
        Actor obj = new Actor();
        Timeline timeline = new Timeline();
        timeline.AddObject("obj", obj);
        var last_animatronic_state = obj.LastAnimatronicNode;
        var animatronic_list = obj.AnimatronicStates;
        checker.Equal(animatronic_list.Count, 0);
        checker.IsNull(last_animatronic_state);
        obj.MoveToCommand(new Vector3(1, 0, 0));
        timeline.PromoteToTime(0.05f);
        checker.Equal(animatronic_list.Count, 1);
        last_animatronic_state = obj.LastAnimatronicNode;
        checker.Equal(animatronic_list.AsList()[0].GetType(), typeof(MovingAnimatronic));
        var moving_animatronic_state = obj.Animatronics().AsList()[0] as MovingAnimatronic;

        checker.Equal(moving_animatronic_state.StartTime, 0.00f, 1e-2f);
        checker.Equal(moving_animatronic_state.FinishTime, 1.0f, 1e-2f);
        timeline.PromoteToTime(1.0f);
        checker.Equal(obj.position(), new Vector3(1, 0, 0), 1e-2f);
        checker.Equal(obj.Animatronics().Count, 1);

        timeline.PromoteToTime(0.5f);
        checker.Equal(obj.position(), new Vector3(0.5f, 0, 0), 1e-1f);
        checker.Equal(obj.Animatronics().Count, 1);

        timeline.Promote(0);
        checker.Equal(obj.position(), new Vector3(0, 0, 0));
        checker.Equal(obj.Animatronics().Count, 1);
    }

    public static void MoveTest2Test(Checker checker)
    {
        Actor obj = new Actor();
        Timeline timeline = new Timeline();
        timeline.AddObject("obj", obj);
        var last_animatronic_state = obj.LastAnimatronicNode;
        var animatronic_list = obj.AnimatronicStates;
        checker.Equal(animatronic_list.Count, 0);
        checker.IsNull(last_animatronic_state);

        obj.MoveToCommand(new Vector3(1, 0, 0));
        timeline.PromoteToTime(0.5f);

        obj.MoveToCommand(new Vector3(2, 0, 0));
        timeline.PromoteToTime(2.5f);

        checker.Equal(obj.Animatronics().Count, 3);
        checker.Equal(obj.Animatronics().AsList()[0].GetType(), typeof(MovingAnimatronic));
        checker.Equal(obj.Animatronics().AsList()[1].GetType(), typeof(MovingAnimatronic));
        checker.Equal(obj.Animatronics().AsList()[2].GetType(), typeof(IdleAnimatronic));
        checker.Equal(obj.position(), new Vector3(2, 0, 0));
    }

    public static void CroachMoveTest2Test(Checker checker)
    {
        Actor obj = new Actor();
        obj.croachControlComponent.IsCroach = true;
        Timeline timeline = new Timeline();
        timeline.AddObject("obj", obj);
        var last_animatronic_state = obj.LastAnimatronicNode;
        var animatronic_list = obj.AnimatronicStates;
        checker.Equal(animatronic_list.Count, 0);
        checker.IsNull(last_animatronic_state);

        obj.MoveToCommand(new Vector3(1, 0, 0));
        timeline.PromoteToTime(0.5f);

        obj.MoveToCommand(new Vector3(2, 0, 0));
        timeline.PromoteToTime(2.5f);

        checker.Equal(obj.Animatronics().Count, 3);
        checker.Equal(obj.Animatronics().AsList()[0].GetType(), typeof(MovingAnimatronic));
        checker.Equal(obj.Animatronics().AsList()[1].GetType(), typeof(MovingAnimatronic));
        checker.Equal(obj.Animatronics().AsList()[2].GetType(), typeof(IdleAnimatronic));

        checker.Equal(obj.position(), new Vector3(2, 0, 0));
    }

    public static void MoveCommandTest(Checker checker)
    {
        Actor obj = new Actor();
        Timeline timeline = new Timeline();
        timeline.AddObject("obj", obj);

        timeline.PromoteToTime(0.1f);
        checker.Equal(obj.Animatronics().Count, 1);
        checker.Equal(obj.Animatronics().AsList()[0].GetType(), typeof(IdleAnimatronic));
        obj.MoveToCommand(new Vector3(10, 0, 0), WalkingType.Walk);
        checker.Equal(obj.Animatronics().Count, 1);
        checker.Equal(obj.Animatronics().AsList()[0].GetType(), typeof(IdleAnimatronic));
        timeline.PromoteToTime(0.2f);

        checker.Equal(obj.Animatronics().Count, 2);
        checker.Equal(obj.Animatronics().AsList()[0].GetType(), typeof(IdleAnimatronic));
        checker.Equal(obj.Animatronics().AsList()[1].GetType(), typeof(MovingAnimatronic));

        checker.Equal(obj.CommandBuffer().GetCommandQueue().Count, 1);
        checker.Equal(obj.CommandBuffer().GetCommandQueue().AsList()[0].FinishStep, long.MaxValue);
        //checker.Equal(obj.CommandBuffer().GetCommandQueue().ActiveStates().Count, 1);
        timeline.PromoteToTime(0.5f);
        //checker.Equal(obj.CommandBuffer().GetCommandQueue().ActiveStates().Count, 1);

        checker.Equal(obj.Animatronics().Count, 2);
        checker.Equal(obj.Animatronics().AsList()[0].GetType(), typeof(IdleAnimatronic));
        checker.Equal(obj.Animatronics().AsList()[1].GetType(), typeof(MovingAnimatronic));
        timeline.PromoteToTime(11.0f);
        checker.Equal(obj.position(), new Vector3(10, 0, 0));
    }

    public static void CroachMoveTest(Checker checker)
    {
        Actor obj = new Actor();
        obj.croachControlComponent.IsCroach = true;
        Timeline timeline = new Timeline();
        timeline.AddObject("obj", obj);

        timeline.PromoteToTime(0.1f);
        obj.MoveToCommand(new Vector3(1, 0, 0), WalkingType.Croach);
        timeline.PromoteToTime(1.0f);
        checker.Equal(obj.Animatronics().Count, 2);
        var moving_animatronic_state = obj.LastAnimatronicNode.Value as MovingAnimatronic;
        timeline.PromoteToTime(2.2f);
        checker.Equal(obj.position(), new Vector3(1, 0, 0));
    }

    public static void NonReversedMoveInTimelineTest2Test(Checker checker)
    {
        Actor obj = new Actor();
        Timeline timeline = new Timeline();
        timeline.AddObject("obj", obj);
        var last_animatronic_state = obj.LastAnimatronicNode;
        var animatronic_list = obj.AnimatronicStates;
        checker.Equal(animatronic_list.Count, 0);
        checker.IsNull(last_animatronic_state);
        checker.Equal(animatronic_list.Count, 0);
        obj.MoveToCommand(new Vector3(1, 0, 0), WalkingType.Walk);
        timeline.PromoteToTime(0.2f);
        checker.Equal(animatronic_list.Count, 1);
        checker.Equal(animatronic_list.AsList()[0].GetType(), typeof(MovingAnimatronic));
        timeline.PromoteToTime(1.1f);
        checker.Equal(obj.position(), new Vector3(1, 0, 0));
    }

    public static void ReversedMoveInTimelineTest2Test(Checker checker)
    {
        Actor obj = new Actor();
        Timeline timeline = new Timeline();
        timeline.SetReversedPass(true);
        obj.SetObjectTimeReferencePoint(0, true);
        timeline.AddObject("obj", obj);
        timeline.SetMinimalStep(long.MinValue);
        var last_animatronic_state = obj.LastAnimatronicNode;
        var animatronic_list = obj.AnimatronicStates;
        checker.Equal(animatronic_list.Count, 0);
        checker.IsNull(last_animatronic_state);
        checker.Equal(animatronic_list.Count, 0);
        obj.MoveToCommand(new Vector3(1, 0, 0), WalkingType.Walk);
        timeline.PromoteToTime(-0.2f);
        checker.Equal(animatronic_list.Count, 1);
        checker.Equal(animatronic_list.AsList()[0].GetType(), typeof(MovingAnimatronic));
        timeline.PromoteToTime(-1.1f);
        checker.Equal(obj.position(), new Vector3(1, 0, 0));
    }

    public static void HastTest(Checker checker)
    {
        Actor obj = new Actor();
        Timeline timeline = new Timeline();
        timeline.AddObject("obj", obj);
        var last_animatronic_state = obj.LastAnimatronicNode;
        var animatronic_list = obj.AnimatronicStates;
        checker.Equal(animatronic_list.Count, 0);
        checker.IsNull(last_animatronic_state);
        obj.hast(0);
        obj.MoveToCommand(new Vector3(1, 0, 0), WalkingType.Walk);
        timeline.PromoteToTime(0.05f);
        checker.Equal(animatronic_list.Count, 1);
        last_animatronic_state = obj.LastAnimatronicNode;
        timeline.PromoteToTime(0.1f);
        checker.Equal(obj.position(), new Vector3(1, 0, 0), 1e-1f);
    }

    public static void OnDeathReactionTest(Checker checker)
    {
        Timeline timeline = new Timeline();

        Actor obj = new Actor();
        timeline.AddObject("obj", obj);

        Actor killer = new Actor();
        timeline.AddObject("killer", killer);

        obj.MoveToCommand(new Vector3(10, 0, 0));
        killer.MoveToCommand(new Vector3(0, 10, 0));

        timeline.PromoteToTime(11.0f);

        checker.Equal(obj.Position(), new Vector3(10, 0, 0), 1e-2f);
        checker.Equal(killer.Position(), new Vector3(0, 10, 0), 1e-2f);

        timeline.AddEvent(
            new DeathEvent(
                step: timeline.CurrentStep(),
                actor: obj,
                who_kill_me: killer.Name(),
                false
            )
        );

        timeline.PromoteToTime(12.0f);

        checker.Equal(obj.IsDead || obj.IsPreDead, true);
        checker.Equal(killer.IsDead || killer.IsPreDead, false);
    }

    public static void OnDeathReactionTest2(Checker checker)
    {
        ChronoSphere sphere = new ChronoSphere();
        Timeline timeline = sphere.CreateTimeline("Original");
        sphere.SetCurrentTimeline(timeline);

        Actor obj = new Actor();
        timeline.AddObject("obj", obj);

        Actor killer = new Actor();
        timeline.AddObject("killer", killer);

        obj.MoveToCommand(new Vector3(10, 0, 0));
        killer.MoveToCommand(new Vector3(0, 10, 0));

        obj.AddAbility(new PastStepOnDeath(distance: (long)Utility.GAME_GLOBAL_FREQUENCY));

        timeline.PromoteToTime(11.0f);
        checker.Equal(obj.Position(), new Vector3(10, 0, 0));
        checker.Equal(killer.Position(), new Vector3(0, 10, 0));
        timeline.AddEvent(
            new DeathEvent(
                step: timeline.CurrentStep() + 10,
                actor: obj,
                who_kill_me: killer.Name(),
                false
            )
        );
        timeline.PromoteToTime(12.0f);

        var ntl = sphere.CurrentTimeline();
        checker.NotEqual(ntl, timeline);

        checker.IsNotNull(ntl);
        obj = ntl.GetActor("obj");
        killer = ntl.GetActor("killer");

        ntl.PromoteToTime(12.0f);
        checker.Equal(obj.IsDead, false);
        checker.Equal(killer.IsDead, false);
    }

    public static void MoveWithCancelTest(Checker checker)
    {
        Actor obj = new Actor();
        Timeline timeline = new Timeline();
        timeline.AddObject("obj", obj);

        timeline.PromoteToTime(1.0f);
        obj.MoveToCommand(new Vector3(10, 0, 0), WalkingType.Walk);

        timeline.PromoteToTime(6.02f);
        checker.Equal(obj.Position(), new Vector3(5, 0, 0), 1e-1f);

        obj.MoveToCommand(new Vector3(0, 7, 0), WalkingType.Walk);
        timeline.PromoteToTime(15.0f);
        checker.Equal(obj.Position(), new Vector3(0, 7, 0), 1e-1f);
    }

    public static void HastAbilityTest(Checker checker)
    {
        Actor obj = new Actor();
        Timeline timeline = new Timeline();
        timeline.AddObject("obj", obj);

        obj.AddAbility(new HastAbility());

        timeline.PromoteToTime(1.0f);
        checker.Equal(obj.Animatronics().Count, 1);

        obj.MoveToCommand(new Vector3(10, 0, 0), WalkingType.Walk);

        timeline.PromoteToTime(15.0f);
        checker.Equal(obj.Position(), new Vector3(10, 0, 0), 1e-2f);

        obj.AbilityUseSelf<HastAbility>();
        timeline.PromoteToTime(16.0f);

        var objecttime = obj.ObjectTime();
        checker.Equal(objecttime.Modifiers.Count, 1);

        checker.Equal(objecttime.FinishedOffset, (long)0);
        checker.IsTrue(objecttime.NonFinishedOffset >= (long)2350);
        var timeline_step = timeline.CurrentStep();
        var local_step = obj.LocalStep();
        checker.IsTrue(local_step - 2350 >= timeline_step);

        obj.MoveToCommand(new Vector3(0, 7, 0), WalkingType.Walk);
        timeline.PromoteToTime(17.5f);

        checker.Equal(obj.Position(), new Vector3(0, 7, 0), 1e-1f);
        timeline.PromoteToTime(30.0f);
        checker.Equal(obj.Position(), new Vector3(0, 7, 0), 1e-1f);
        obj.MoveToCommand(new Vector3(0, 7, 0), WalkingType.Walk);
        timeline.PromoteToTime(50.0f);
        checker.Equal(obj.Position(), new Vector3(0, 7, 0), 1e-1f);
    }
}
#endif
