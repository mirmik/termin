#if !UNITY_64
static class ObjectTimeTests
{
    static public void ObjectTimeTest(Checker checker)
    {
        ObjectTime ot = new ObjectTime();
        var hast_modifier = new TimeHast(100, 150, mul: 10);

        ot.AddModifier(hast_modifier);
        ot.Promote(120);

        checker.Equal(ot.NonFinishedOffset, (long)200);
        checker.Equal(ot.Modifiers.Count, 1);
        //checker.Equal(ot.Modifiers.AsListByFinish().Count, 1);

        var ott = new ObjectTime(ot);
        checker.Equal(ott.NonFinishedOffset, (long)200);
        checker.Equal(ott.Modifiers.Count, 1);
        //checker.Equal(ott.Modifiers.AsListByFinish().Count, 1);
    }

    static public void ObjectTimeTest2(Checker checker)
    {
        ObjectTime ot = new ObjectTime();
        ot.Promote(1000);

        checker.Equal(ot.TimelineToLocal(0), (long)0);
        checker.Equal(ot.TimelineToLocal(1000), (long)1000);
        ot.SetReferencePoint(1000, true);

        checker.Equal(ot.TimelineToLocal(1000), (long)1000);
        ot.Promote(0);

        checker.Equal(ot.TimelineToLocal(1000), (long)1000);
        checker.Equal(ot.TimelineToLocal(0), (long)2000);

        ot.SetReferencePoint(0, false);
        checker.Equal(ot.TimelineToLocal(0), (long)2000);
        checker.Equal(ot.TimelineToLocal(1000), (long)3000);

        var start_step = ot.ToBroken(0);
        var finish_step = ot.ToBroken(100);
        ot.AddModifier(new TimeHast(start_step, finish_step, mul: 10));

        ot.Promote(50);
        checker.Equal(ot.NonFinishedOffset, (long)500);
        checker.Equal(ot.FinishedOffset, (long)0);
        checker.Equal(ot.TimelineToLocal(50), (long)2550);

        ot.Promote(150);
        checker.Equal(ot.NonFinishedOffset, (long)0);
        checker.Equal(ot.FinishedOffset, (long)1000);
        checker.Equal(ot.TimelineToLocal(150), (long)3150);
    }

    static public void ObjectTimeTest2_Reversed(Checker checker)
    {
        ObjectTime ot = new ObjectTime();
        ot.Promote(1000);

        checker.Equal(ot.TimelineToLocal(0), (long)0);
        checker.Equal(ot.TimelineToLocal(1000), (long)1000);
        ot.SetReferencePoint(1000, true);

        checker.Equal(ot.TimelineToLocal(1000), (long)1000);
        ot.Promote(0);

        checker.Equal(ot.TimelineToLocal(1000), (long)1000);
        checker.Equal(ot.TimelineToLocal(0), (long)2000);

        var start_step = ot.ToBroken(0);
        var finish_step = start_step + 100;

        checker.Equal(ot.ToBroken(0), (long)2000);
        checker.Equal(ot.ToBroken(-50), (long)2050);
        checker.Equal(ot.ToBroken(-100), (long)2100);

        checker.Equal(ot.NonFinishedOffset, (long)0);
        checker.Equal(ot.FinishedOffset, (long)0);
        ot.AddModifier(new TimeHast(start_step, finish_step, mul: 10));

        ot.Promote(-25);
        checker.Equal(ot.ToBroken(-25), (long)2025);
        checker.Equal(ot.NonFinishedOffset, (long)250);
        checker.Equal(ot.FinishedOffset, (long)0);

        ot.Promote(-50);
        checker.Equal(ot.ToBroken(-50), (long)2050);
        checker.Equal(ot.NonFinishedOffset, (long)500);
        checker.Equal(ot.FinishedOffset, (long)0);

        checker.Equal(ot.TimelineToLocal(-50), (long)2550);

        ot.Promote(-100);
        checker.Equal(ot.NonFinishedOffset, (long)1000);
        checker.Equal(ot.FinishedOffset, (long)0);
        checker.Equal(ot.TimelineToLocal(-100), (long)3100);

        ot.Promote(-150);
        checker.Equal(ot.NonFinishedOffset, (long)0);
        checker.Equal(ot.FinishedOffset, (long)1000);
        checker.Equal(ot.TimelineToLocal(-150), (long)3150);
    }
}
#endif
