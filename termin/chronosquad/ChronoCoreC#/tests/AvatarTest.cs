#if !UNITY_64

using System.Reflection;

static class AvatarTests
{
    static public void AvatarTest(Checker checker)
    {
        ChronoSphere sphere = new ChronoSphere();
        var timeline = sphere.CreateEmptyTimeline();
        var avatar = timeline.CreateObject<Avatar>("avatar");
        avatar.DisableBehaviour();
        var server = timeline.CreateObject<Actor>("server");
        server.DisableBehaviour();

        server.ImmediateBlinkTo(
            new ReferencedPose(
                pose: new Pose(new Vector3(0, 0, 10), new Quaternion(0, 0, 0, 0)),
                frame: null
            )
        );

        server.AddComponent<NetPoint>();
        avatar.ChangeLocation("server");

        timeline.PromoteToTime(1.0f);
        checker.Equal(avatar.Location.name, "server");
        checker.Equal(
            server.CurrentReferencedPose().GlobalPosition(timeline),
            new Vector3(0, 0, 10),
            0.01f
        );
        checker.Equal(
            avatar.CurrentReferencedPose().GlobalPosition(timeline),
            new Vector3(0, 0, 10),
            0.01f
        );
    }

    static public void AvatarMovingTest(Checker checker)
    {
        ChronoSphere sphere = new ChronoSphere();
        var timeline = sphere.CreateEmptyTimeline();
        var avatar = timeline.CreateObject<Avatar>("avatar");
        avatar.DisableBehaviour();
        var server0 = timeline.CreateObject<Actor>("server0");
        var server1 = timeline.CreateObject<Actor>("server1");
        server0.DisableBehaviour();
        server1.DisableBehaviour();

        server0.ImmediateBlinkTo(
            new ReferencedPose(
                pose: new Pose(new Vector3(0, 0, 10), new Quaternion(0, 0, 0, 0)),
                frame: null
            )
        );

        server1.ImmediateBlinkTo(
            new ReferencedPose(
                pose: new Pose(new Vector3(10, 0, 0), new Quaternion(0, 0, 0, 0)),
                frame: null
            )
        );

        server0.AddComponent<NetPoint>();
        server1.AddComponent<NetPoint>();
        avatar.ChangeLocation("server0");

        timeline.PromoteToTime(1.0f);
        checker.Equal(avatar.Location.name, "server0");
        checker.Equal(
            avatar.CurrentReferencedPose().GlobalPosition(timeline),
            new Vector3(0, 0, 10),
            0.01f
        );

        avatar.ChangeLocation("server1");
        checker.Equal(avatar.Location.name, "server0");
        checker.Equal(
            avatar.CurrentReferencedPose().GlobalPosition(timeline),
            new Vector3(0, 0, 10),
            0.01f
        );

        timeline.PromoteToTime(2.0f);
        checker.Equal(avatar.Location.name, "server1");
        checker.Equal(
            avatar.CurrentReferencedPose().GlobalPosition(timeline),
            new Vector3(10, 0, 0),
            0.01f
        );
    }

    static public void PathfindingTest(Checker checker)
    {
        ChronoSphere sphere = new ChronoSphere();
        var timeline = sphere.CreateEmptyTimeline();
        var avatar = timeline.CreateObject<Avatar>("avatar");
        var server0 = timeline.CreateObject<Actor>("server0");
        var server1 = timeline.CreateObject<Actor>("server1");
        var server2 = timeline.CreateObject<Actor>("server2");
        var server3 = timeline.CreateObject<Actor>("server3");
        var server4 = timeline.CreateObject<Actor>("server4");
        var server5 = timeline.CreateObject<Actor>("server5");
        var server6 = timeline.CreateObject<Actor>("server6");
        var server7 = timeline.CreateObject<Actor>("server7");

        var np0 = server0.AddComponent<NetPoint>();
        var np1 = server1.AddComponent<NetPoint>();
        var np2 = server2.AddComponent<NetPoint>();
        var np3 = server3.AddComponent<NetPoint>();
        var np4 = server4.AddComponent<NetPoint>();
        var np5 = server5.AddComponent<NetPoint>();
        var np6 = server6.AddComponent<NetPoint>();
        var np7 = server7.AddComponent<NetPoint>();

        np0.AddConnection(np1);
        np1.AddConnection(np2);
        np2.AddConnection(np3);
        np3.AddConnection(np4);
        np2.AddConnection(np5);
        np5.AddConnection(np6);
        np6.AddConnection(np7);

        timeline.StartPhase();
        var network_map = timeline.GetNetworkMap();
        checker.Equal(network_map.Nodes.Count, 8);
        network_map.MakeConnectionGraphByPoints();
        var path = network_map.PathFinding(np0, np7);
        checker.Equal(path.Count, 6);

        avatar.DisableBehaviour();
        avatar.ChangeLocation("server0");
        timeline.PromoteToTime(1.0f);

        var path2 = avatar.PathFinding(server7.GetComponent<NetPoint>());
        checker.Equal(path2.Count, 6);
    }

    static public void MoveTest(Checker checker)
    {
        ChronoSphere sphere = new ChronoSphere();
        var timeline = sphere.CreateEmptyTimeline();
        var avatar = timeline.CreateObject<Avatar>("avatar");
        var server0 = timeline.CreateObject<Actor>("server0");
        var server1 = timeline.CreateObject<Actor>("server1");
        var server2 = timeline.CreateObject<Actor>("server2");
        var server3 = timeline.CreateObject<Actor>("server3");
        var server4 = timeline.CreateObject<Actor>("server4");
        var server5 = timeline.CreateObject<Actor>("server5");
        var server6 = timeline.CreateObject<Actor>("server6");
        var server7 = timeline.CreateObject<Actor>("server7");

        var np0 = server0.AddComponent<NetPoint>();
        var np1 = server1.AddComponent<NetPoint>();
        var np2 = server2.AddComponent<NetPoint>();
        var np3 = server3.AddComponent<NetPoint>();
        var np4 = server4.AddComponent<NetPoint>();
        var np5 = server5.AddComponent<NetPoint>();
        var np6 = server6.AddComponent<NetPoint>();
        var np7 = server7.AddComponent<NetPoint>();

        np0.AddConnection(np1);
        np1.AddConnection(np2);
        np2.AddConnection(np3);
        np3.AddConnection(np4);
        np2.AddConnection(np5);
        np5.AddConnection(np6);
        np6.AddConnection(np7);

        timeline.StartPhase();
        var network_map = timeline.GetNetworkMap();
        checker.Equal(network_map.Nodes.Count, 8);
        network_map.MakeConnectionGraphByPoints();

        avatar.DisableBehaviour();
        avatar.ChangeLocation("server0");
        timeline.PromoteToTime(1.0f);

        avatar.MoveToNetworkPoint(server7.GetComponent<NetPoint>());
        timeline.PromoteToTime(5.0f);
        checker.Equal(avatar.Location.name, "server7");

        checker.Equal(np7.AvatarOnPoint(avatar.ObjectId()), true);
    }

    static public void NetworkCopy(Checker checker)
    {
        ChronoSphere sphere = new ChronoSphere();
        var timeline = sphere.CreateEmptyTimeline();
        var avatar = timeline.CreateObject<Avatar>("avatar");
        var server0 = timeline.CreateObject<Actor>("server0");
        var server1 = timeline.CreateObject<Actor>("server1");
        var server2 = timeline.CreateObject<Actor>("server2");
        var server3 = timeline.CreateObject<Actor>("server3");
        var server4 = timeline.CreateObject<Actor>("server4");
        var server5 = timeline.CreateObject<Actor>("server5");
        var server6 = timeline.CreateObject<Actor>("server6");
        var server7 = timeline.CreateObject<Actor>("server7");

        var np0 = server0.AddComponent<NetPoint>();
        var np1 = server1.AddComponent<NetPoint>();
        var np2 = server2.AddComponent<NetPoint>();
        var np3 = server3.AddComponent<NetPoint>();
        var np4 = server4.AddComponent<NetPoint>();
        var np5 = server5.AddComponent<NetPoint>();
        var np6 = server6.AddComponent<NetPoint>();
        var np7 = server7.AddComponent<NetPoint>();

        np0.AddConnection(np1);
        np1.AddConnection(np2);
        np2.AddConnection(np3);
        np3.AddConnection(np4);
        np2.AddConnection(np5);
        np5.AddConnection(np6);
        np6.AddConnection(np7);

        timeline.StartPhase();
        var ntc = timeline.Copy();

        var network = ntc.GetNetworkMap();
        checker.Equal(network.Nodes.Count, 8);
    }

    static public void MoveTestInNtc(Checker checker)
    {
        ChronoSphere sphere = new ChronoSphere();
        var timeline = sphere.CreateEmptyTimeline();
        var avatar = timeline.CreateObject<Avatar>("avatar");
        var server0 = timeline.CreateObject<Actor>("server0");
        var server1 = timeline.CreateObject<Actor>("server1");
        var server2 = timeline.CreateObject<Actor>("server2");
        var server3 = timeline.CreateObject<Actor>("server3");
        var server4 = timeline.CreateObject<Actor>("server4");
        var server5 = timeline.CreateObject<Actor>("server5");
        var server6 = timeline.CreateObject<Actor>("server6");
        var server7 = timeline.CreateObject<Actor>("server7");

        var np0 = server0.AddComponent<NetPoint>();
        var np1 = server1.AddComponent<NetPoint>();
        var np2 = server2.AddComponent<NetPoint>();
        var np3 = server3.AddComponent<NetPoint>();
        var np4 = server4.AddComponent<NetPoint>();
        var np5 = server5.AddComponent<NetPoint>();
        var np6 = server6.AddComponent<NetPoint>();
        var np7 = server7.AddComponent<NetPoint>();

        np0.AddConnection(np1);
        np1.AddConnection(np2);
        np2.AddConnection(np3);
        np3.AddConnection(np4);
        np2.AddConnection(np5);
        np5.AddConnection(np6);
        np6.AddConnection(np7);

        timeline.StartPhase();
        var ntc = timeline.Copy();
        avatar = (Avatar)ntc.GetObject("avatar");
        server0 = (Actor)ntc.GetObject("server0");
        server1 = (Actor)ntc.GetObject("server1");
        server2 = (Actor)ntc.GetObject("server2");
        server3 = (Actor)ntc.GetObject("server3");
        server4 = (Actor)ntc.GetObject("server4");
        server5 = (Actor)ntc.GetObject("server5");
        server6 = (Actor)ntc.GetObject("server6");
        server7 = (Actor)ntc.GetObject("server7");
        var network_map = ntc.GetNetworkMap();
        //network_map.MakeConnectionGraphByPoints();
        checker.Equal(network_map.Nodes.Count, 8);

        avatar.DisableBehaviour();
        avatar.ChangeLocation("server0");
        ntc.PromoteToTime(1.0f);

        avatar.MoveToNetworkPoint(server7.GetComponent<NetPoint>());
        checker.Equal(avatar.Location.name, "server0");
        ntc.PromoteToTime(5.0f);
        checker.Equal(avatar.Location.name, "server7");

        checker.Equal(
            server7.GetComponent<NetPoint>().AvatarOnPoint(new ObjectId(avatar.Name())),
            true
        );
    }

    // static public void CircularScanTest(Checker checker)
    // {
    // 	ChronoSphere sphere = new ChronoSphere();
    // 	var timeline = sphere.CreateEmptyTimeline();
    // 	var avatar = timeline.CreateObject<Avatar>("avatar");
    // 	var server0 = timeline.CreateObject<Actor>("server0");
    // 	var server1 = timeline.CreateObject<Actor>("server1");
    // 	var server2 = timeline.CreateObject<Actor>("server2");
    // 	var server3 = timeline.CreateObject<Actor>("server3");
    // 	var server4 = timeline.CreateObject<Actor>("server4");
    // 	var server5 = timeline.CreateObject<Actor>("server5");
    // 	var server6 = timeline.CreateObject<Actor>("server6");
    // 	var server7 = timeline.CreateObject<Actor>("server7");

    // 	var np0 = server0.AddComponent<NetPoint>();
    // 	var np1 = server1.AddComponent<NetPoint>();
    // 	var np2 = server2.AddComponent<NetPoint>();
    // 	var np3 = server3.AddComponent<NetPoint>();
    // 	var np4 = server4.AddComponent<NetPoint>();
    // 	var np5 = server5.AddComponent<NetPoint>();
    // 	var np6 = server6.AddComponent<NetPoint>();
    // 	var np7 = server7.AddComponent<NetPoint>();

    // 	np0.AddConnection(np1);
    // 	np1.AddConnection(np2);
    // 	np2.AddConnection(np3);
    // 	np3.AddConnection(np4);
    // 	np2.AddConnection(np5);
    // 	np5.AddConnection(np6);
    // 	np6.AddConnection(np7);

    // 	var network_map = timeline.GetNetworkMap();
    // 	var r = AStarSolver.CircularScan(network_map.Graph, np0, 3);
    // }
}
#endif
