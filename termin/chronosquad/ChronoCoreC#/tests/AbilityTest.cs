#if !UNITY_64

public static class AbilityTest
{
    public static void ShootAbilityTest_CanUse(Checker checker)
    {
        var tl = new Timeline();
        var guard = new Actor("obj");
        var target = new Actor("target");
        tl.AddObject(guard);
        tl.AddObject(target);
        var activity = new ShootAbility(10);
        guard.AddAbility(activity);

        checker.IsTrue(activity.CanUse(tl, guard.AbilityListPanel()));
        tl.Promote(100);

        guard.AbilityUseOnObject<ShootAbility>(target);

        tl.Promote(200);
        checker.IsFalse(activity.CanUse(tl, guard.AbilityListPanel()));
    }

    public static void ShootAbilityTest(Checker checker)
    {
        var tl = new Timeline();
        var guard = new Actor("obj");

        tl.AddObject(guard);
        var activity = new ShootAbility(10);
        guard.AddAbility(activity);

        checker.IsTrue(activity.CanUse(tl, guard.AbilityListPanel()));

        var target = new Actor("target");
        tl.AddObject(target);

        guard.MoveToCommand(new Vector3(1, 0, 0), WalkingType.Walk);
        tl.PromoteToTime(0.5f);

        checker.Equal(guard.Position(), new Vector3(0.5f, 0, 0), 0.01f);

        guard.AbilityUseOnObject<ShootAbility>(target);

        tl.PromoteToTime(1.0f);
        checker.Equal(guard.Position(), new Vector3(0.5f, 0, 0), 0.01f);
        tl.PromoteToTime(2.0f);
        checker.IsTrue(target.IsDead || target.IsPreDead);
        tl.PromoteToTime(1.0f);
        checker.IsFalse(activity.CanUse(tl, guard.AbilityListPanel()));
    }

    public static void ReverseAbilityTest(Checker checker)
    {
        var chronosphere = new ChronoSphere();
        var tl = new Timeline();
        var guard = new Actor("obj");
        tl.AddObject(guard);
        chronosphere.AddTimeline(tl);
        tl.SetCurrentTimeline();

        guard.MoveToCommand(new Vector3(100, 0, 0), is_run: false);
        tl.PromoteToTime(0.05f);
        checker.Equal(guard.Animatronics().Count, 1);

        var activity = new ReverseAbility();
        guard.AddAbility(activity);

        tl.PromoteToTime(10.0f);
        checker.Equal(guard.Position(), new Vector3(9.9955f, 0, 0), 0.1f);
        checker.Equal(guard.Animatronics().Count, 1);

        guard
            .GetAbility<ReverseAbility>()
            .UseSelf(tl, guard.AbilityListPanel(), ignore_cooldown: true);
        tl.PromoteToTime(10.1f);
        checker.Equal(chronosphere.Timelines().Count, 2);

        var ntl = chronosphere.Timelines().Values.ToList()[1];
        checker.Equal(ntl.Objects().Count, 2);

        //bntl.PromoteToTime(10.0f);

        var ntl_obj_1 = ntl.Objects().Values.ToList()[0] as Actor;
        var ntl_obj_2 = ntl.Objects().Values.ToList()[1] as Actor;
        checker.Equal(guard.Animatronics().Count, 1);
        checker.Equal(ntl_obj_1.Animatronics().Count, 1);
        checker.Equal(ntl_obj_2.Animatronics().Count, 1);

        checker.Equal(ntl_obj_1.Position(), new Vector3(9.9955f, 0, 0), 0.1f);
        checker.Equal(ntl_obj_2.Position(), new Vector3(9.9955f, 0, 0), 0.1f);

        ntl.PromoteToTime(9.0f);
        checker.IsTrue(ntl_obj_1.IsMaterial());
        checker.IsTrue(ntl_obj_2.IsMaterial());

        ntl.PromoteToTime(16.0f);
        checker.IsFalse(ntl_obj_1.IsMaterial());
        checker.IsFalse(ntl_obj_2.IsMaterial());
        checker.Equal(ntl_obj_1.Animatronics().Count, 1);
        checker.Equal(ntl_obj_2.Animatronics().Count, 1);

        ntl.PromoteToTime(10.0f);
        checker.Equal(ntl_obj_1.Position(), new Vector3(9.9955f, 0, 0), 0.1f);
        checker.Equal(ntl_obj_1.Animatronics().Count, 1);
        checker.Equal(ntl_obj_2.Animatronics().Count, 1);

        ntl.Promote(0);
        checker.Equal(ntl_obj_1.Position(), new Vector3(0f, 0, 0), 0.1f);
        checker.Equal(ntl_obj_2.Position(), new Vector3(19.995998f, 0, 0), 0.2f);
        checker.IsTrue(ntl_obj_1.IsMaterial());
        checker.IsTrue(ntl_obj_2.IsMaterial());
        checker.Equal(ntl_obj_1.Animatronics().Count, 1);
        checker.Equal(ntl_obj_2.Animatronics().Count, 1);
        checker.Equal(ntl_obj_1.Animatronics().AsListByStart().Count, 1);
        //checker.Equal(ntl_obj_1.Animatronics().AsListByFinish().Count, 1);
        checker.Equal(ntl_obj_2.Animatronics().AsListByStart().Count, 1);
        //checker.Equal(ntl_obj_2.Animatronics().AsListByFinish().Count, 1);
    }

    // public static void ReverseAbilityTest_WithControllers(Checker checker)
    // {
    //     var chronosphere_controller_go = new GameObject("Timelines");
    //     var chronosphere_controller =
    //         chronosphere_controller_go.AddComponent<ChronosphereController>();

    //     var tl_go = new GameObject("Original");
    //     var tl_ctr = tl_go.AddComponent<TimelineController>();

    //     tl_ctr.transform.parent = chronosphere_controller.transform;

    //     var go = new GameObject("guard1");
    //     go.AddComponent<ControlableActor>();
    //     go.AddComponent<AnimateController>();
    //     go.AddComponent<GuardView>();
    //     go.AddComponent<ObjectController>();
    //     go.AddComponent<RigController>();
    //     var objctr = go.GetComponent<ObjectController>(); //.CreateObject<Actor>(null, null);
    //     go.transform.parent = tl_ctr.transform;

    //     //chronosphere_controller.AddTimelineToChronosphere(tl_ctr);
    //     // chronosphere_controller.InitChronosphere();
    //     // chronosphere_controller.InitInstancePool();
    //     // tl_ctr.Init();

    //     chronosphere_controller.InvokeAwake();
    //     tl_ctr.InvokeAwake();
    //     objctr.InvokeAwake();
    //     chronosphere_controller.InvokeStart();
    //     tl_ctr.InvokeStart();
    //     objctr.InvokeStart();

    //     var chronosphere = chronosphere_controller.Chronosphere();

    //     checker.Equal(chronosphere.Timelines().Count, 1);
    //     checker.Equal(chronosphere.Timelines().Values.ToList()[0].Objects().Count, 1);
    //     checker.Equal(chronosphere_controller.Timelines().Count, 1);
    //     checker.Equal(chronosphere_controller.Timelines()[0].Objects().Count, 1);

    //     checker.Equal(
    //         chronosphere.Timelines().Values.ToList()[0].Objects().ToList()[0].Value.Name(),
    //         "guard1"
    //     );
    //     var guard = chronosphere.Timelines().Values.ToList()[0].Objects()["guard1"] as Actor;
    //     var tl = chronosphere.Timelines().Values.ToList()[0];

    //     guard.MoveTo(new Vector3(100, 0, 0), is_run: false);

    //     var activity = new ReverseAbility(null);
    //     guard.AddAbility(activity);

    //     tl.PromoteToTime(10.0f);
    //     checker.Equal(guard.Position(), new Vector3(9.9955f, 0, 0), 0.1f);

    //     //checker.Equal(chronosphere_controller.InstancePool().Count, 1);

    //     guard.GetAbility<ReverseAbility>().UseSelf(tl, guard.AbilityListPanel());
    //     tl.PromoteToTime(10.1f);

    //     checker.Equal(chronosphere.Timelines().Count, 2);
    //     checker.Equal(chronosphere.Timelines().Values.ToList()[1].Objects().Count, 2);
    //     checker.Equal(chronosphere_controller.Timelines().Count, 2);
    //     checker.Equal(chronosphere_controller.Timelines()[1].Objects().Count, 2);
    // }

    public static void ReverseAbilityMultyTest(Checker checker)
    {
        var chronosphere = new ChronoSphere();
        var tl = new Timeline();
        var guard = new Actor("obj");
        checker.IsTrue(guard.CommandBuffer() != null);
        tl.AddObject(guard);
        chronosphere.AddTimeline(tl);
        tl.SetCurrentTimeline();

        tl.PromoteToTime(0.01f);

        guard.MoveToCommand(new Vector3(100, 0, 0), WalkingType.Walk);

        var activity = new ReverseAbility();
        guard.AddAbility(activity);

        tl.PromoteToTime(10.0f);
        checker.Equal(tl.IsReversedPass(), false);
        checker.Equal(guard.Position(), new Vector3(9.9955f, 0, 0), 0.1f);

        checker.Equal(tl.NonDropableGlobalEvents().Count, 0);
        guard.AbilityUseSelf<ReverseAbility>();
        tl.PromoteToTime(10.1f);
        //checker.Equal(tl.NonDropableGlobalEvents().Count, 1);
        //tl.PromoteToTime(2001 / 480.0f);
        checker.Equal(chronosphere.Timelines().Count, 2);

        var ntl = chronosphere.Timelines().Values.ToList()[1];
        checker.Equal(ntl.IsReversedPass(), true);
        checker.Equal(ntl.Objects().Count, 2);

        var ntl_obj_1 = ntl.Objects().Values.ToList()[0] as Actor;
        var ntl_obj_2 = ntl.Objects().Values.ToList()[1] as Actor;
        ntl.PromoteToTime(10.1f);
        checker.IsFalse(ntl_obj_1.IsMaterial());
        checker.IsFalse(ntl_obj_2.IsMaterial());

        ntl.PromoteToTime(10.0f);
        checker.Equal(ntl_obj_1.Position(), new Vector3(9.9955f, 0, 0), 0.1f);
        checker.Equal(ntl_obj_2.Position(), new Vector3(9.9955f, 0, 0), 0.1f);
        ntl.PromoteToTime(9.9f);
        checker.IsTrue(ntl_obj_1.IsMaterial());
        checker.IsTrue(ntl_obj_2.IsMaterial());

        ntl.PromoteToTime(15.0f);
        checker.Equal(chronosphere.Timelines().Count, 2);
        //checker.Equal(ntl.NonDropableGlobalEvents().Count, 2);
        // checker.Equal(
        //     ntl.NonDropableGlobalEvents().AsList()[0].GetType(),
        //     typeof(AnigilationEvent)
        // );
        // checker.Equal(
        //     ntl.NonDropableGlobalEvents().AsList()[1].GetType(),
        //     typeof(AnigilationEvent)
        // );

        checker.IsFalse(ntl_obj_1.IsMaterial());
        checker.IsFalse(ntl_obj_2.IsMaterial());
        checker.Equal(ntl_obj_1.LinkedObjectInTime(), ntl_obj_2);

        ntl.Promote(0);
        checker.Equal(ntl_obj_1.Position(), new Vector3(0f, 0, 0), 0.1f);
        checker.Equal(ntl_obj_2.Position(), new Vector3(19.995998f, 0, 0), 0.1f);
        checker.IsTrue(ntl_obj_1.IsMaterial());
        checker.IsTrue(ntl_obj_2.IsMaterial());

        checker.Equal(ntl_obj_1.LinkedObjectInTime(), ntl_obj_2);
        checker.Equal(chronosphere.Timelines().Count, 2);
        ntl_obj_2.AbilityUseSelf<ReverseAbility>();
        ntl.PromoteToTime(-0.1f);
        //ntl.Promote(0);

        checker.Equal(chronosphere.Timelines().Count, 3);
        var nntl = chronosphere.Timelines().Values.ToList()[2];
        checker.Equal(nntl.IsReversedPass(), false);
        checker.Equal(nntl.Objects().Count, 3);

        nntl.PromoteToTime(10.0f);

        checker.Equal(
            nntl.Objects().Values.ToList()[0].Position(),
            new Vector3(9.9955f, 0, 0),
            0.1f
        );
        checker.Equal(
            nntl.Objects().Values.ToList()[1].Position(),
            new Vector3(9.9955f, 0, 0),
            0.1f
        );
        checker.Equal(
            nntl.Objects().Values.ToList()[2].Position(),
            new Vector3(29.9965f, 0, 0),
            0.1f
        );

        ((Actor)(nntl.Objects().Values.ToList()[2])).AbilityUseSelf<ReverseAbility>();
        nntl.PromoteToTime(10.1f);
        var nnntl = chronosphere.Timelines().Values.ToList()[3];

        nnntl.Promote(0);
        checker.Equal(nnntl.IsReversedPass(), true);

        checker.Equal(nnntl.Objects().Values.ToList()[0].Position(), new Vector3(0f, 0, 0), 0.1f);
        checker.Equal(
            ((Actor)(nnntl.Objects().Values.ToList()[1])).Position(),
            new Vector3(20.0f, 0, 0),
            0.1f
        );
        checker.Equal(
            ((Actor)(nnntl.Objects().Values.ToList()[2])).Position(),
            new Vector3(20.0f, 0, 0),
            0.1f
        );
        checker.Equal(
            ((Actor)(nnntl.Objects().Values.ToList()[3])).Position(),
            new Vector3(40.0f, 0, 0),
            0.1f
        );
    }

    public static void ReverseInMiddleTest(Checker checker)
    {
        var chronosphere = new ChronoSphere();
        var tl = new Timeline();
        var guard = new Actor("obj");
        checker.IsTrue(guard.CommandBuffer() != null);
        tl.AddObject(guard);
        chronosphere.AddTimeline(tl);
        tl.SetCurrentTimeline();

        guard.AddAbility(new ReverseAbility());

        tl.PromoteToTime(1000 / 480.0f);
        guard.AbilityUseSelf<ReverseAbility>();
        tl.PromoteToTime(1000 / 480.0f + 0.1f);

        checker.Equal(chronosphere.Timelines().Count, 2);

        checker.NotEqual(tl, chronosphere.CurrentTimeline());
        var c_tl = chronosphere.CurrentTimeline();
        var c_guard = c_tl.Objects().Values.ToList()[1] as Actor;

        c_tl.Promote(100);
        c_guard.AbilityUseSelf<ReverseAbility>(ignore_cooldown: true);
        c_tl.Promote(90);

        checker.Equal(chronosphere.Timelines().Count, 3);

        var cc_tl = chronosphere.CurrentTimeline();
        cc_tl.Promote(90);
        var cc_guard = cc_tl.Objects().Values.ToList()[2] as Actor;
        cc_tl.Promote(900);

        cc_guard.AbilityUseSelf<ReverseAbility>();
        cc_tl.Promote(905);
        checker.Equal(chronosphere.Timelines().Count, 4);

        var ccc_tl = chronosphere.CurrentTimeline();

        guard = ccc_tl.Objects().Values.ToList()[0] as Actor;
        c_guard = ccc_tl.Objects().Values.ToList()[1] as Actor;
        cc_guard = ccc_tl.Objects().Values.ToList()[2] as Actor;
        var ccc_guard = ccc_tl.Objects().Values.ToList()[3] as Actor;

        checker.Equal(guard.LinkedObjectInTime(), c_guard);
        checker.Equal(c_guard.LinkedObjectInTime(), cc_guard);
        checker.Equal(cc_guard.LinkedObjectInTime(), ccc_guard);

        //checker.Equal(c_guard.parent, guard);

        ccc_tl.Promote(200);
    }

    public static void UseReverseInReversePass_Test(Checker checker)
    {
        var chronosphere = new ChronoSphere();
        var tl = new Timeline();
        var guard = new Actor("obj");
        tl.AddObject(guard);
        chronosphere.AddTimeline(tl);
        tl.SetCurrentTimeline();

        guard.AddAbility(new ReverseAbility());

        tl.PromoteToTime(1000 / 480.0f);

        checker.Equal(chronosphere.Timelines().Count, 1);
        var c_tl = tl.Copy(reverse: true);
        chronosphere.AddTimeline(c_tl);
        checker.Equal(chronosphere.Timelines().Count, 2);
        var c_guard = c_tl.Objects().Values.ToList()[0] as Actor;

        c_tl.Promote(900);
        checker.Equal(chronosphere.Timelines().Count, 2);
        c_guard.AbilityUseSelf<ReverseAbility>();
        //checker.Equal(chronosphere.Timelines().Count, 3);
        c_tl.Promote(910);
        checker.Equal(c_guard.CommandBuffer().GetCommandQueue().Count, 0);

        checker.Equal(chronosphere.Timelines().Count, 4);

        var cc_tl = chronosphere.CurrentTimeline();
        checker.Equal(cc_tl.IsReversedPass(), true);
        checker.Equal(cc_tl.Objects().Count, 2);
    }

    public static void RevSimple_Test(Checker checker)
    {
        var chronosphere = new ChronoSphere();
        var tl = new Timeline();
        var guard = new Actor("obj");

        tl.AddObject(guard);
        chronosphere.AddTimeline(tl);
        tl.SetCurrentTimeline();

        guard.MoveToCommand(new Vector3(100, 0, 0), is_run: false);
        tl.PromoteToTime(0.05f);
        checker.Equal(guard.Animatronics().Count, 1);

        var activity = new ReverseAbility();
        guard.AddAbility(activity);

        tl.PromoteToTime(10.0f);
        checker.Equal(guard.Position(), new Vector3(9.9955f, 0, 0), 0.1f);
        checker.Equal(guard.Animatronics().Count, 1);

        guard
            .GetAbility<ReverseAbility>()
            .UseSelf(tl, guard.AbilityListPanel(), ignore_cooldown: true);
        tl.PromoteToTime(10.1f);
        checker.Equal(chronosphere.Timelines().Count, 2);
    }

    public static void StepToPastAbilityTest(Checker checker)
    {
        var chronosphere = new ChronoSphere();
        var tl = new Timeline();
        var guard = new Actor("obj");
        guard.MarkAsHero();
        tl.AddObject(guard);
        chronosphere.AddTimeline(tl);
        tl.SetCurrentTimeline();

        tl.PromoteToTime(0.7f);
        guard.MoveToCommand(new Vector3(1.0f, 0, 0), WalkingType.Walk);

        tl.PromoteToTime(1.0f);
        guard.AddAbility(new StepToPastAbility(0.5f));
        guard.AbilityUseSelf<StepToPastAbility>();
        tl.PromoteToTime(1.01f);

        checker.Equal(chronosphere.Timelines().Count, 2);
        checker.Equal(tl.GlobalEvents().Count, 1);

        var ntl = chronosphere.Timelines().Values.ToList()[1];
        checker.Equal(tl.CurrentTime(), 1.0f, 0.1f);
        checker.Equal(ntl.CurrentTime(), 0.5f, 0.1f);

        checker.Equal(ntl.Objects().Count, 2);
        checker.Equal(ntl.GlobalEvents().MyList.Count, 0);
        checker.Equal(ntl.NonDropableGlobalEvents().MyList.Count, 1);
        //checker.Equal(tl.CheckTimeParadox(), ParadoxStatus.NoParadox);
        //checker.Equal(ntl.CheckTimeParadox(), ParadoxStatus.NoParadox);

        var gcopy0 = ntl.Objects().Values.ToList()[0] as Actor;
        var gcopy1 = ntl.Objects().Values.ToList()[1] as Actor;
        checker.Equal(gcopy0.LocalTimeByStep(), 0.5f, 0.1f);
        checker.Equal(gcopy1.LocalTimeByStep(), 1.0f, 0.1f);
        checker.Equal(gcopy0.ObjectTime().TimelineToLocal_Seconds(1.0f), 1.0f);
        checker.Equal(gcopy1.ObjectTime().TimelineToLocal_Seconds(1.0f), 1.5f);

        checker.Equal(tl.NonDropableGlobalEvents().MyList.Count, 0);
        checker.Equal(tl.GlobalEvents().MyList.Count, 1);
        tl.Promote(0);
        tl.DropTimelineToCurrentState();
        tl.PromoteToTime(1.0f);
        checker.Equal(tl.NonDropableGlobalEvents().MyList.Count, 0);
        //checker.Equal(tl.GlobalEvents().MyList.Count, 1);

        checker.Equal(ntl.NonDropableGlobalEvents().MyList.Count, 1);
        checker.Equal(ntl.GlobalEvents().MyList.Count, 0);
        ntl.Promote(0);
        ntl.DropTimelineToCurrentState();
        ntl.PromoteToTime(0.5f);
        checker.Equal(ntl.NonDropableGlobalEvents().MyList.Count, 1);
        checker.Equal(ntl.GlobalEvents().MyList.Count, 0);

        //checker.Equal(tl.CheckTimeParadox(), ParadoxStatus.NoParadox);
        //checker.Equal(ntl.CheckTimeParadox(), ParadoxStatus.NoParadox);
    }

    public static void DoubleStepToPastAbilityTest(Checker checker)
    {
        var chronosphere = new ChronoSphere();
        var tl = new Timeline();
        var guard = new Actor("obj");
        guard.MarkAsHero();
        tl.AddObject(guard);
        chronosphere.AddTimeline(tl);
        tl.SetCurrentTimeline();

        tl.PromoteToTime(0.7f);
        guard.MoveToCommand(new Vector3(1.0f, 0, 0), WalkingType.Walk);

        tl.PromoteToTime(1.0f);
        guard.AddAbility(new StepToPastAbility(0.5f));
        guard.AbilityUseSelf<StepToPastAbility>();
        tl.PromoteToTime(1.01f);
        var ntl = chronosphere.Timelines().Values.ToList()[1];

        var gcopy0 = ntl.Objects().Values.ToList()[0] as Actor;
        var gcopy1 = ntl.Objects().Values.ToList()[1] as Actor;

        checker.Equal(gcopy1.CanUseAbility<StepToPastAbility>(gcopy1), true);

        ntl.PromoteToTime(3.0f);
        gcopy1.AbilityUseSelf<StepToPastAbility>(ignore_cooldown: true);
        ntl.PromoteToTime(3.05f);

        checker.Equal(chronosphere.Timelines().Count, 3);
        var nntl = chronosphere.Timelines().Values.ToList()[2];
        checker.Equal(nntl.CurrentTime(), 2.5f, 0.1f);

        checker.Equal(nntl.Objects().Count, 3);
        gcopy0 = nntl.Objects().Values.ToList()[0] as Actor;
        gcopy1 = nntl.Objects().Values.ToList()[1] as Actor;
        var gcopy2 = nntl.Objects().Values.ToList()[2] as Actor;

        checker.Equal(gcopy0.LocalTimeByStep(), 2.5f, 0.04f);
        checker.Equal(gcopy1.LocalTimeByStep(), 3.0f, 0.04f);
        checker.Equal(gcopy2.LocalTimeByStep(), 3.5f, 0.04f);

        //checker.Equal(tl.CheckTimeParadox(), ParadoxStatus.NoParadox);
        //checker.Equal(ntl.CheckTimeParadox(), ParadoxStatus.NoParadox);
        //checker.Equal(nntl.CheckTimeParadox(), ParadoxStatus.NoParadox);
    }

    // TODO:
    // public static void StepToPastIsMaterialAbilityTest(Checker checker)
    // {
    // 	var chronosphere = new ChronoSphere();
    // 	var tl = new Timeline();
    // 	var guard = new Actor("obj");
    // 	guard.MarkAsHero();
    // 	tl.AddObject(guard);
    // 	chronosphere.AddTimeline(tl);
    // 	tl.SetCurrentTimeline();

    // 	tl.PromoteToTime(0.7f);
    // 	guard.MoveToCommand(new Vector3(1.0f, 0, 0), WalkingType.Walk);

    // 	tl.PromoteToTime(1.0f);
    // 	guard.AddAbility(new StepToPastAbility(0.5f));
    // 	guard.AbilityUseSelf<StepToPastAbility>();
    // 	checker.IsTrue(guard.IsMaterial());

    // 	tl.PromoteToTime(1.1f);
    // 	checker.IsFalse(guard.IsMaterial());

    // 	tl.PromoteToTime(0.9f);
    // 	checker.IsTrue(guard.IsMaterial());

    // 	var ntl = chronosphere.Timelines().Values.ToList()[1];
    // 	var gcopy0 = ntl.Objects().Values.ToList()[0] as Actor;
    // 	var gcopy1 = ntl.Objects().Values.ToList()[1] as Actor;

    // 	checker.Equal(ntl.CurrentTime(), 0.5f, 0.05f);
    // 	checker.IsTrue(gcopy0.IsMaterial());
    // 	checker.IsFalse(gcopy1.IsMaterial());

    // 	ntl.PromoteToTime(1.1f);
    // 	checker.IsFalse(gcopy0.IsMaterial());
    // 	checker.IsTrue(gcopy1.IsMaterial());

    // 	ntl.PromoteToTime(0.0f);
    // 	checker.IsTrue(gcopy0.IsMaterial());
    // 	checker.IsFalse(gcopy1.IsMaterial());

    // 	ntl.PromoteToTime(0.6f);
    // 	checker.IsTrue(gcopy0.IsMaterial());
    // 	checker.IsTrue(gcopy1.IsMaterial());


    // 	checker.Equal(ntl.NonDropableGlobalEvents().MyList.AsList()[0].StartStep, (long)121);
    // 	checker.Equal(gcopy1.ObjectTime().TimelineToLocal(120), (long)240);

    // 	ntl.PromoteToTime(2.0f);
    // 	checker.IsFalse(gcopy0.IsMaterial());
    // 	checker.IsTrue(gcopy1.IsMaterial());
    // }
}

#endif
