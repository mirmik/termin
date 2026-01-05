#if !UNITY_64
public static class MovementTestClass
{
    public static void MovementTest(Checker checker)
    {
        ChronoSphere chronosphere = new ChronoSphere();
        var timeline = chronosphere.CreateEmptyTimeline();
        var obj = timeline.CreateObject<Actor>("obj");
        obj.DisableBehaviour();

        var path = new UnitPath();
        path.AddPassPoint(new Vector3(10, 0, 0), UnitPathPointType.StandartMesh);
        path.AddPassPoint(new Vector3(0, 0, 10), UnitPathPointType.StandartMesh);
        obj.ApplyAnimatronicsList(obj.PlanPath(path, WalkingType.Walk));
        timeline.PromoteToTime(1.0f);

        checker.Equal(obj.Animatronics().Count, 2);
        timeline.PromoteToTime(30.0f);

        checker.Equal(obj.GlobalPosition(), new Vector3(0, 0, 10));
    }

    public static void MovementWithBracedTest(Checker checker)
    {
        ChronoSphere chronosphere = new ChronoSphere();
        var timeline = chronosphere.CreateEmptyTimeline();
        var obj = timeline.CreateObject<Actor>("obj");
        obj.DisableBehaviour();

        var path = new UnitPath();
        path.AddPassPoint(new Vector3(10, 0, 0), UnitPathPointType.StandartMesh);
        path.AddPassPoint(new Vector3(0, 0, 10), UnitPathPointType.StandartMesh);
        path.AddPassPoint(
            new Vector3(0, 0, 11),
            UnitPathPointType.DownToBraced,
            braced_coordinates: new BracedCoordinates(
                target_point: new ReferencedPoint(new Vector3(0, 0, 11), default(ObjectId))
            )
        );
        obj.ApplyAnimatronicsList(obj.PlanPath(path, WalkingType.Walk));
        timeline.PromoteToTime(1.0f);

        checker.Equal(obj.Animatronics().Count, 5);
        timeline.PromoteToTime(30.0f);

        checker.Equal(obj.GlobalPosition(), new Vector3(0, 0, 11));
        //checker.Equal(obj.CurrentAnimatronic().GetType(), typeof(IdleAnimatronic));

        checker.Equal(obj.Animatronics().Count, 5);
        checker.Equal(obj.Animatronics().AsList()[0].GetType(), typeof(MovingAnimatronic));
        checker.Equal(obj.Animatronics().AsList()[1].GetType(), typeof(MovingAnimatronic));
        checker.Equal(obj.Animatronics().AsList()[2].GetType(), typeof(UniversalJumpAnimatronic));
        checker.Equal(obj.Animatronics().AsList()[3].GetType(), typeof(UniversalJumpAnimatronic));
        checker.Equal(obj.Animatronics().AsList()[4].GetType(), typeof(UniversalJumpAnimatronic));
        //checker.Equal(obj.Animatronics().AsList()[5].GetType(), typeof(IdleAnimatronic));
    }
}

#endif
