#if !UNITY_64
public static class ControllersTestClass
{
    static GameObject CreateGuard(Timeline tc)
    {
        var go = new GameObject("guard1");
        go.AddComponent<ControlableActor>();
        go.AddComponent<AnimateController>();
        go.AddComponent<ObjectController>();
        go.AddComponent<GuardView>();
        go.AddComponent<RigController>();
        go.GetComponent<ObjectController>(); //.CreateObject<Actor>("guard1", tc);
        return go;
    }

    // public static void ControllersInitializationTest(Checker checker)
    // {
    // 	var chronosphere_go = new GameObject();
    // 	ChronosphereController chronos = chronosphere_go.AddComponent<ChronosphereController>();

    // 	var tc = chronos.CreateEmptyTimeline();
    // 	checker.IsNotNull(tc.gameObject);
    // 	checker.IsNotNull(tc.transform);

    // 	var go = CreateGuard(tc.GetTimeline());

    // 	// checker.Equal(
    // 	// 	go.GetComponent<GuardView>().GetGuard(),
    // 	// 	go.GetComponent<ObjectController>().GetActor() as Actor
    // 	// );
    // 	go.transform.parent = tc.transform;
    // 	chronos.InitInstancePool();

    // 	checker.Equal(tc.Objects().Count, 0);
    // 	tc.BindGuard(go.GetComponent<ObjectController>());
    // 	checker.Equal(tc.Objects().Count, 1);
    // 	checker.Equal(tc.GetTimeline().objects().Count, 1);

    // 	checker.Equal(chronos.Timelines().Count, 1);

    // 	foreach (var obj in tc.GetTimeline().objects())
    // 	{
    // 		checker.Equal(obj.Value.ProtoId(), "guard1");
    // 		checker.Equal(obj.Value.Name(), "guard1");
    // 	}

    // 	checker.Equal(go.GetComponent<GuardView>().guard().ProtoId(), "guard1");
    // 	checker.Equal(go.GetComponent<GuardView>().guard().Name(), "guard1");
    // 	chronos.InitChronosphere();
    // 	checker.Equal(chronos.Timelines().Count, 1);
    // 	checker.Equal(tc.Objects().Count, 1);
    // 	checker.Equal(tc.GetTimeline().objects().Count, 1);

    // 	checker.Equal(go.GetComponent<GuardView>().guard().ProtoId(), "guard1");
    // 	checker.Equal(go.GetComponent<GuardView>().guard().Name(), "guard1");

    // 	ChronoSphere cs = chronos.GetChronosphere();
    // 	checker.Equal(tc.GetTimeline().objects().Count, 1);

    // 	checker.IsNotNull(cs);
    // 	checker.Equal(cs.CurrentTimeline(), tc.GetTimeline());
    // 	checker.Equal(cs.Timelines().Count, 1);

    // 	var curtl = cs.CurrentTimeline();
    // 	checker.Equal(curtl.objects().Count, 1);
    // 	checker.Equal(chronos.Timelines()[0].GetGuardControllers().Count, 1);

    // 	var ntl = curtl.Copy();
    // 	checker.Equal(cs.CurrentTimeline(), tc.GetTimeline());
    // 	checker.Equal(cs.Timelines().Count, 1);

    // 	cs.AddTimeline(ntl);
    // 	checker.Equal(cs.Timelines().Count, 2);

    // 	checker.Equal(chronos.Timelines().Count, 2);

    // 	foreach (var tl in chronos.Timelines())
    // 	{
    // 		checker.Equal(tl.GetGuardControllers().Count, 1);
    // 	}
    // }
}
#endif
