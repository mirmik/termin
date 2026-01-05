#if !UNITY_64
public static class MoveToObjectTestClass
{
    public static void MoveToObjectTest(Checker checker)
    {
        ChronoSphere chronosphere = new ChronoSphere();
        var tl = chronosphere.CreateEmptyTimeline();
        var target = tl.CreateObject<Actor>("target");
        var guard = tl.CreateObject<Actor>("guard");
    }

    public static void PulledTest(Checker checker)
    {
        ChronoSphere chronosphere = new ChronoSphere();
        var tl = chronosphere.CreateEmptyTimeline();
        var corpse = tl.CreateObject<Actor>("corpse");
        var guard = tl.CreateObject<Actor>("guard");

        var anim = new MovingAnimatronic(
            AnimationType.CroachWalk,
            new ReferencedPose(
                new Pose(
                    new Vector3(0.0f, 0.0f, 0.0f),
                    Quaternion.LookRotation(new Vector3(1.0f, 0.0f, 0.0f))
                ),
                null
            ),
            new ReferencedPose(
                new Pose(
                    new Vector3(10.0f, 0.0f, 0.0f),
                    Quaternion.LookRotation(new Vector3(1.0f, 0.0f, 0.0f))
                ),
                null
            ),
            0,
            (long)(10.0f * Utility.GAME_GLOBAL_FREQUENCY),
            1.0f
        );

        guard.DisableBehaviour();
        guard.SetNextAnimatronic(anim);

        corpse.DisableBehaviour();
        corpse.SetNextAnimatronic(
            new PulledByAnimatronic(
                0,
                (long)(10.0f * Utility.GAME_GLOBAL_FREQUENCY),
                referenced_animatronic: anim,
                initial_pulled_pose: new ReferencedPose(
                    new Pose(
                        new Vector3(0.0f, 0.0f, 0.0f),
                        Quaternion.LookRotation(new Vector3(1.0f, 0.0f, 0.0f))
                    ),
                    null
                )
            )
        );

        checker.Equal(
            guard.CurrentReferencedPose().GlobalPosition(tl),
            new Vector3(0.0f, 0.0f, 0.0f),
            0.1f
        );
        checker.Equal(
            corpse.CurrentReferencedPose().GlobalPosition(tl),
            new Vector3(0.0f, 0.0f, 0.0f),
            0.1f
        );

        tl.PromoteToTime(1.0f);
        checker.Equal(
            guard.CurrentReferencedPose().GlobalPosition(tl),
            new Vector3(1.0f, 0.0f, 0.0f),
            0.1f
        );
        checker.Equal(
            corpse.CurrentReferencedPose().GlobalPosition(tl),
            new Vector3(0.0f, 0.0f, 0.0f),
            0.1f
        );

        tl.PromoteToTime(2.0f);
        checker.Equal(
            guard.CurrentReferencedPose().GlobalPosition(tl),
            new Vector3(2.0f, 0.0f, 0.0f),
            0.1f
        );
        checker.Equal(
            corpse.CurrentReferencedPose().GlobalPosition(tl),
            new Vector3(1.0f, 0.0f, 0.0f),
            0.1f
        );

        tl.PromoteToTime(3.0f);
        checker.Equal(
            guard.CurrentReferencedPose().GlobalPosition(tl),
            new Vector3(3.0f, 0.0f, 0.0f),
            0.1f
        );
        checker.Equal(
            corpse.CurrentReferencedPose().GlobalPosition(tl),
            new Vector3(2.0f, 0.0f, 0.0f),
            0.1f
        );

        tl.PromoteToTime(10.0f);
        checker.Equal(
            guard.CurrentReferencedPose().GlobalPosition(tl),
            new Vector3(10.0f, 0.0f, 0.0f),
            0.1f
        );
        checker.Equal(
            corpse.CurrentReferencedPose().GlobalPosition(tl),
            new Vector3(9.0f, 0.0f, 0.0f),
            0.1f
        );

        tl.PromoteToTime(3.0f);
        checker.Equal(
            guard.CurrentReferencedPose().GlobalPosition(tl),
            new Vector3(3.0f, 0.0f, 0.0f),
            0.1f
        );
        checker.Equal(
            corpse.CurrentReferencedPose().GlobalPosition(tl),
            new Vector3(2.0f, 0.0f, 0.0f),
            0.1f
        );
    }
}

#endif
