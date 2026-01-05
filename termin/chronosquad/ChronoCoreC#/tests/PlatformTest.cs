#if !UNITY_64
public static class PlatformTests
{
    static public void PlatformMoveTest(Checker checker)
    {
        var chronosphere = new ChronoSphere();
        var timeline = chronosphere.CreateEmptyTimeline();
        var actor = timeline.CreateObject<Actor>("actor");
        var platform = timeline.CreateObject<Platform>("platform");

        actor.SetMovedWith(new ObjectId("platform"));
        actor.DisableBehaviour();
        checker.Equal(actor.MovedWithObject(), platform);

        platform.SetPose(new Pose(new Vector3(10, 0, 0), Quaternion.identity));
        platform.PreEvaluate();
        actor.PreEvaluate();
        checker.Equal(actor.GlobalPosition(), new Vector3(10, 0, 0));

        platform.StartSinusAnimatronic(
            new Pose(new Vector3(10, 0, 0), Quaternion.identity),
            new Pose(new Vector3(20, 0, 0), Quaternion.identity),
            1
        );

        checker.Equal(actor.GlobalPose(), new Pose(new Vector3(10, 0, 0), Quaternion.identity));
        checker.Equal(platform.GlobalPose(), new Pose(new Vector3(10, 0, 0), Quaternion.identity));

        timeline.PromoteToTime(0.00f);
        checker.Equal(actor.GlobalPosition(), new Vector3(10, 0, 0));
        checker.Equal(actor.GlobalPose(), new Pose(new Vector3(10, 0, 0), Quaternion.identity));
        checker.Equal(platform.GlobalPose(), new Pose(new Vector3(10, 0, 0), Quaternion.identity));

        timeline.PromoteToTime(0.25f);
        checker.Equal(actor.GlobalPosition(), new Vector3(15, 0, 0), 1e-0f);
        checker.Equal(platform.GlobalPose(), new Pose(new Vector3(15, 0, 0), Quaternion.identity));

        timeline.PromoteToTime(0.5f);
        checker.Equal(actor.GlobalPosition(), new Vector3(20, 0, 0), 1e-0f);

        timeline.PromoteToTime(0.75f);
        checker.Equal(actor.GlobalPosition(), new Vector3(15, 0, 0), 1e-0f);

        timeline.PromoteToTime(1.0f);
        checker.Equal(actor.GlobalPosition(), new Vector3(10, 0, 0), 1e-0f);

        // actor.SetLocalPose(new Pose(new Vector3(2, 0, 0), Quaternion.identity));
        actor.ImmediateBlinkTo(
            new ReferencedPose(new Vector3(2, 0, 0), Quaternion.identity, "platform")
        );
        //checker.Equal(actor.GlobalPose(), new Pose(new Vector3(12, 0, 0), Quaternion.identity));
        //checker.Equal(platform.GlobalPose(), new Pose(new Vector3(10, 0, 0), Quaternion.identity));
        //checker.Equal(actor.GlobalPosition(), new Vector3(12, 0, 0));

        timeline.PromoteToTime(1.05f);
        checker.Equal(actor.GlobalPosition(), new Vector3(12, 0, 0), 1e-0f);

        timeline.PromoteToTime(1.25f);
        checker.Equal(actor.GlobalPosition(), new Vector3(17, 0, 0), 1e-0f);

        timeline.PromoteToTime(1.5f);
        checker.Equal(actor.GlobalPosition(), new Vector3(22, 0, 0), 1e-0f);

        timeline.PromoteToTime(1.75f);
        checker.Equal(actor.GlobalPosition(), new Vector3(17, 0, 0), 1e-0f);

        timeline.PromoteToTime(2.0f);
        checker.Equal(actor.GlobalPosition(), new Vector3(12, 0, 0), 1e-0f);
    }

    static public void PlatformBehaviourTest(Checker checker)
    {
        var chronosphere = new ChronoSphere();
        var timeline = chronosphere.CreateEmptyTimeline();
        var actor = timeline.CreateObject<Actor>("actor");
        var platform = timeline.CreateObject<Platform>("platform");

        actor.SetMovedWith(new ObjectId("platform"));

        platform.StartSinusAnimatronic(
            new Pose(new Vector3(0, 0, 0), Quaternion.identity),
            new Pose(new Vector3(20, 0, 0), Quaternion.identity),
            10
        );

        timeline.PromoteToTime(2.5f);

        checker.Equal(actor.Animatronics().AsList()[0].GetType(), typeof(IdleAnimatronic));
        checker.Equal(
            (actor.Animatronics().AsList()[0] as IdleAnimatronic).LocalPose().position,
            new Vector3(0, 0, 0)
        );
        checker.Equal(actor.GlobalPosition(), new Vector3(10, 0, 0), 1e-0f);
        checker.Equal(actor.LocalPosition(), new Vector3(0, 0, 0), 1e-0f);
        checker.Equal(platform.GlobalPosition(), new Vector3(10, 0, 0), 1e-0f);
    }

    static public void BlinkToPlatformTest(Checker checker)
    {
        var chronosphere = new ChronoSphere();
        var timeline = chronosphere.CreateEmptyTimeline();
        var actor = timeline.CreateObject<Actor>("actor");
        var platform = timeline.CreateObject<Platform>("platform");

        platform.StartSinusAnimatronic(
            new Pose(new Vector3(10, 0, 0), Quaternion.identity),
            new Pose(new Vector3(20, 0, 0), Quaternion.identity),
            1
        );

        timeline.PromoteToTime(0.25f);
        checker.Equal(platform.GlobalPosition(), new Vector3(15, 0, 0), 1e-0f);
        actor.ImmediateBlinkTo(new Vector3(10, 0, 0), new Vector3(1, 0, 0));
        timeline.PromoteToTime(0.255f);

        checker.Equal(actor.GlobalPosition(), new Vector3(10, 0, 0));
        checker.Equal(actor.LocalPosition(), new Vector3(10, 0, 0));
        checker.Equal(platform.GlobalPosition(), new Vector3(15, 0, 0), 1e-0f);

        actor.SetMovedWith(new ObjectId("platform"));
        checker.Equal(actor.LocalPosition(), new Vector3(-5, 0, 0), 1e-0f);
        checker.Equal(actor.GlobalPosition(), new Vector3(10, 0, 0), 1e-0f);
        timeline.PromoteToTime(0.26f);
        checker.Equal(actor.LocalPosition(), new Vector3(-5, 0, 0), 1e-0f);
        checker.Equal(actor.GlobalPosition(), new Vector3(10, 0, 0), 1e-0f);
        checker.Equal(platform.GlobalPosition(), new Vector3(15, 0, 0), 1e-0f);

        timeline.PromoteToTime(0.5f);
        checker.Equal(actor.GlobalPosition(), new Vector3(15, 0, 0), 1e-0f);
        checker.Equal(platform.GlobalPosition(), new Vector3(20, 0, 0), 1e-0f);

        timeline.PromoteToTime(0.75f);
        checker.Equal(actor.GlobalPosition(), new Vector3(10, 0, 0), 1e-0f);
        checker.Equal(platform.GlobalPosition(), new Vector3(15, 0, 0), 1e-0f);

        timeline.PromoteToTime(1.0f);
        checker.Equal(actor.GlobalPosition(), new Vector3(5, 0, 0), 1e-0f);
        checker.Equal(platform.GlobalPosition(), new Vector3(10, 0, 0), 1e-0f);
    }

    static public void MoveOnPlatformTest(Checker checker)
    {
        var chronosphere = new ChronoSphere();
        var timeline = chronosphere.CreateEmptyTimeline();
        var actor = timeline.CreateObject<Actor>("actor");
        var platform = timeline.CreateObject<Platform>("platform");

        platform.SetPose(
            new Pose(new Vector3(10, 0, 0), new Quaternion(0, 0.7071068f, 0, 0.7071068f))
        );
        actor.SetMovedWith_WithoutInterrupt(new ObjectId("platform"));

        actor.MoveToCommand(
            new ReferencedPoint(new Vector3(10, 0, 0), "platform"),
            WalkingType.Walk
        );
        timeline.PromoteToTime(100.0f);

        checker.Equal(actor.GlobalPosition(), new Vector3(10, 0, -10), 1e-0f);
    }

    static public void MoveOnPlatformReferncedFrameTest(Checker checker)
    {
        var chronosphere = new ChronoSphere();
        var timeline = chronosphere.CreateEmptyTimeline();
        var actor = timeline.CreateObject<Actor>("actor");
        var platform = timeline.CreateObject<Platform>("platform");

        platform.SetPose(
            new Pose(new Vector3(10, 0, 0), new Quaternion(0, 0.7071068f, 0, 0.7071068f))
        );
        platform.PreEvaluate();
        actor.SetMovedWith_WithoutInterrupt(new ObjectId("platform"));

        checker.Equal(actor.CurrentReferencedPose().Frame.name, "platform");

        actor.PreEvaluate();

        checker.Equal(actor.CurrentReferencedPose().Frame.name, "platform");

        actor.MoveToCommand(
            ReferencedPoint.FromGlobalPosition(
                new Vector3(20, 0, 0),
                new ObjectId("platform"),
                timeline
            ),
            WalkingType.Walk
        );
        timeline.PromoteToTime(0.01f);

        checker.Equal(actor.Animatronics().Count, 1);
        checker.Equal(actor.Animatronics().AsList()[0].GetType(), typeof(MovingAnimatronic));

        checker.Equal(
            (actor.Animatronics().AsList()[0] as MovingAnimatronic).StartPose().Frame.name,
            "platform"
        );

        checker.Equal(
            (actor.Animatronics().AsList()[0] as MovingAnimatronic).FinalPose().Frame.name,
            "platform"
        );

        checker.Equal(
            (actor.Animatronics().AsList()[0] as MovingAnimatronic)
                .FinalPose()
                .GlobalPose(timeline)
                .position,
            new Vector3(20, 0, 0),
            1e-2f
        );
        checker.Equal(
            (actor.Animatronics().AsList()[0] as MovingAnimatronic).FinalPose().LocalPosition(),
            new Vector3(0, 0, 10.0f),
            1e-2f
        );

        timeline.PromoteToTime(0.0f);
        checker.Equal(
            actor.CurrentReferencedPose(),
            new ReferencedPose(new Vector3(0, 0, -10), new Vector3(-1, 0, 0), "platform"),
            1e-2f
        );

        checker.Equal(
            actor.GlobalPosition(),
            new ReferencedPoint(new Vector3(0, 0, -10), "platform").GlobalPosition(timeline),
            1e-0f
        );

        timeline.PromoteToTime(5.0f);
        checker.Equal(
            actor.CurrentReferencedPose(),
            new ReferencedPose(new Vector3(0, 0, -5), new Vector3(0, 0, 1), "platform"),
            1e-2f
        );

        checker.Equal(
            actor.GlobalPosition(),
            new ReferencedPoint(new Vector3(0, 0, -5), "platform").GlobalPosition(timeline),
            1e-0f
        );

        timeline.PromoteToTime(10.0f);
        checker.Equal(
            actor.CurrentReferencedPose(),
            new ReferencedPose(new Vector3(0, 0, 0), new Vector3(0, 0, 1), "platform"),
            1e-2f
        );

        checker.Equal(
            actor.GlobalPosition(),
            new ReferencedPoint(new Vector3(0, 0, 0), "platform").GlobalPosition(timeline),
            1e-0f
        );

        timeline.PromoteToTime(20.0f);
        checker.Equal(
            actor.CurrentReferencedPose(),
            new ReferencedPose(new Vector3(0, 0, 10), new Vector3(0, 0, 1), "platform"),
            1e-2f
        );

        checker.Equal(
            actor.GlobalPosition(),
            new ReferencedPoint(new Vector3(0, 0, 10), "platform").GlobalPosition(timeline),
            1e-0f
        );
    }

    // static public void MoveToPlatformTest(Checker checker)
    // {
    // 	var chronosphere = new ChronoSphere();
    // 	var timeline = chronosphere.CreateEmptyTimeline();
    // 	var actor = timeline.CreateObject<Actor>("actor");
    // 	var platform = timeline.CreateObject<Platform>("platform");

    // 	// platform.StartSinusAnimatronic(
    // 	//     new Pose(new Vector3(10, 0, 0), Quaternion.identity),
    // 	//     new Pose(new Vector3(20, 0, 0), Quaternion.identity),
    // 	//     1
    // 	// );

    // 	timeline.PromoteToTime(0.25f);

    // 	var path = new UnitPath();
    // 	path.AddPassPoint(
    // 		new ReferencedPoint(new Vector3(0, 0, 1), null),
    // 		UnitPathPointType.StandartMesh
    // 	);
    // 	path.AddPassPoint(
    // 		new ReferencedPoint(new Vector3(1, 0, 1), "platform"),
    // 		UnitPathPointType.DownToBraced
    // 	);
    // 	path.AddPassPoint(
    // 		new ReferencedPoint(new Vector3(2, 0, 1), "platform"),
    // 		UnitPathPointType.StandartMesh
    // 	);

    // 	actor.PlanPath(path, WalkingType.Walk);

    // 	checker.Equal(actor.Animatronics().Count, 6);
    // 	checker.Equal(actor.Animatronics().AsList()[0].GetType(), typeof(IdleAnimatronic));
    // 	checker.Equal(actor.Animatronics().AsList()[1].GetType(), typeof(MovingAnimatronic));
    // 	checker.Equal(actor.Animatronics().AsList()[2].GetType(), typeof(UniversalJumpAnimatronic));
    // 	checker.Equal(actor.Animatronics().AsList()[3].GetType(), typeof(UniversalJumpAnimatronic));
    // 	checker.Equal(actor.Animatronics().AsList()[4].GetType(), typeof(UniversalJumpAnimatronic));
    // 	checker.Equal(actor.Animatronics().AsList()[5].GetType(), typeof(MovingAnimatronic));

    // 	checker.Equal(actor.Animatronics().AsList()[0].StartStep, (long)1);
    // 	checker.Equal(actor.Animatronics().AsList()[1].StartStep, (long)60);
    // 	checker.Equal(actor.Animatronics().AsList()[2].StartStep, (long)300);
    // 	checker.Equal(actor.Animatronics().AsList()[3].StartStep, (long)324);
    // 	checker.Equal(actor.Animatronics().AsList()[4].StartStep, (long)360);
    // 	checker.Equal(actor.Animatronics().AsList()[5].StartStep, (long)384);

    // 	checker.Equal(actor.Animatronics().AsList()[0].FinishStep, long.MaxValue);
    // 	checker.Equal(actor.Animatronics().AsList()[1].FinishStep, (long)300);
    // 	checker.Equal(actor.Animatronics().AsList()[2].FinishStep, (long)324);
    // 	checker.Equal(actor.Animatronics().AsList()[3].FinishStep, (long)360);
    // 	checker.Equal(actor.Animatronics().AsList()[4].FinishStep, (long)384);
    // 	checker.Equal(actor.Animatronics().AsList()[5].FinishStep, (long)624);

    // 	checker.Equal(actor.Animatronics().AsList()[0].StartPose(timeline).GlobalPosition(timeline), new Vector3(0, 0, 0));
    // 	checker.Equal(actor.Animatronics().AsList()[1].StartPose(timeline).GlobalPosition(timeline), new Vector3(0, 0, 0));
    // 	checker.Equal(actor.Animatronics().AsList()[2].StartPose(timeline).GlobalPosition(timeline), new Vector3(0,0,1));
    // 	checker.Equal(actor.Animatronics().AsList()[3].StartPose(timeline).GlobalPosition(timeline), new Vector3(0,0,1));
    // 	checker.Equal(actor.Animatronics().AsList()[4].StartPose(timeline).GlobalPosition(timeline), new Vector3(1,0,1));
    // 	checker.Equal(actor.Animatronics().AsList()[5].StartPose(timeline).GlobalPosition(timeline), new Vector3(1,0,1));

    // 	checker.Equal(actor.Animatronics().AsList()[0].FinalPose(timeline).GlobalPosition(timeline), new Vector3(0, 0, 0));
    // 	checker.Equal(actor.Animatronics().AsList()[1].FinalPose(timeline).GlobalPosition(timeline), new Vector3(0, 0, 1));
    // 	checker.Equal(actor.Animatronics().AsList()[2].FinalPose(timeline).GlobalPosition(timeline), new Vector3(0, 0, 1));
    // 	checker.Equal(actor.Animatronics().AsList()[3].FinalPose(timeline).GlobalPosition(timeline), new Vector3(1,0,1));
    // 	checker.Equal(actor.Animatronics().AsList()[4].FinalPose(timeline).GlobalPosition(timeline), new Vector3(1,0,1));
    // 	checker.Equal(actor.Animatronics().AsList()[5].FinalPose(timeline).GlobalPosition(timeline), new Vector3(2, 0, 1));

    // 	checker.Equal(actor.Animatronics().AsList()[0].StartFrame(timeline), (string)null);
    // 	checker.Equal(actor.Animatronics().AsList()[1].StartFrame(timeline), (string)null);
    // 	checker.Equal(actor.Animatronics().AsList()[2].StartFrame(timeline), (string)null);
    // 	checker.Equal(actor.Animatronics().AsList()[3].StartFrame(timeline), (string)null);
    // 	checker.Equal(actor.Animatronics().AsList()[4].StartFrame(timeline), (string)"platform");
    // 	checker.Equal(actor.Animatronics().AsList()[5].StartFrame(timeline), (string)"platform");

    // 	checker.Equal(actor.Animatronics().AsList()[0].FinalFrame(timeline), (string)null);
    // 	checker.Equal(actor.Animatronics().AsList()[1].FinalFrame(timeline), (string)null);
    // 	checker.Equal(actor.Animatronics().AsList()[2].FinalFrame(timeline), (string)null);
    // 	checker.Equal(actor.Animatronics().AsList()[3].FinalFrame(timeline), (string)"platform");
    // 	checker.Equal(actor.Animatronics().AsList()[4].FinalFrame(timeline), (string)"platform");
    // 	checker.Equal(actor.Animatronics().AsList()[5].FinalFrame(timeline), (string)"platform");

    // 	timeline.PromoteToTime(10.0f);
    // }
}
#endif
