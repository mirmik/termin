using System.Collections.Generic;
using System.Linq;
using System;
using UnityEngine;

public class NetPointConnection : IAStarEdge
{
    public NetPoint netpoint_a;
    public NetPoint netpoint_b;

    public float Cost => 1.0f;

    public IAStarNode A => netpoint_a;
    public IAStarNode B => netpoint_b;

    public IAStarNode Other(IAStarNode node)
    {
        if (A == node)
        {
            return B;
        }
        else if (B == node)
        {
            return A;
        }
        else
        {
            return null;
        }
    }

    public bool Contains(IAStarNode node)
    {
        return A == node || B == node;
    }
}

public class NetworkPath
{
    MyList<IAStarNode> path = new MyList<IAStarNode>();

    public NetworkPath(MyList<IAStarNode> path)
    {
        this.path = path;
    }

    public MyList<IAStarNode> Nodes => path;
}

public class NetworkMap
{
    Timeline timeline;

    MyList<NetPointConnection> connections = new MyList<NetPointConnection>();
    MyList<IAStarEdge> connections_for_algo = new MyList<IAStarEdge>();
    MyList<IAStarEdge> connections_for_algo_admin_level = new MyList<IAStarEdge>();
    MyList<NetPoint> opposite_netpoints = new MyList<NetPoint>();
    MyList<NetPoint> netpoints = new MyList<NetPoint>();
    MyList<IAStarNode> netpoints_for_algo = new MyList<IAStarNode>();

    public MyList<NetPoint> Nodes => netpoints;

    public MyList<IAStarEdge> Graph => connections_for_algo;
    public MyList<IAStarEdge> Graph_For_Admin => connections_for_algo;

    public NetworkMap(Timeline timeline)
    {
        this.timeline = timeline;
    }

    public void AddNetPoint(NetPoint netpoint)
    {
        netpoints.Add(netpoint);
        netpoints_for_algo.Add(netpoint);
        MakeConnectionGraphByPoints();
    }

    public MyList<IAStarNode> PathFinding(NetPoint start, NetPoint end)
    {
        var path = AStarSolver.Solve(connections_for_algo, start, end);
        return path;
    }

    public MyList<IAStarNode> PathFindingAdmin(NetPoint start, NetPoint end)
    {
        var path = AStarSolver.Solve(connections_for_algo_admin_level, start, end);
        return path;
    }

    public void MakeConnectionGraphByPoints()
    {
        opposite_netpoints.Clear();
        connections.Clear();
        netpoints_for_algo.Clear();
        connections_for_algo.Clear();
        connections_for_algo_admin_level.Clear();

        foreach (var netpoint in netpoints)
        {
            if (netpoint.GetLinks() == null)
            {
                netpoint.InvokeStart();
            }
        }

        foreach (var netpoint in netpoints)
        {
            foreach (var link in netpoint.GetLinks())
            {
                var netpoint_b = netpoints.Find(x => x.Owner.Name() == link.name.name);
                if (netpoint_b != null)
                {
                    var connection = new NetPointConnection();
                    connection.netpoint_a = netpoint;
                    connection.netpoint_b = netpoint_b;
                    connections.Add(connection);
                    opposite_netpoints.Add(netpoint_b);
                    connections_for_algo.Add(connection);
                }
            }
            netpoints_for_algo.Add(netpoint);
        }
    }

    public NetworkMap Copy(Timeline new_timeline)
    {
        var obj = new NetworkMap(new_timeline);
        foreach (var netpoint in netpoints)
        {
            var name = netpoint.Owner.Name();
            var this_object_in_new_timeline = new_timeline.GetObject(name);
            var new_netpoint = this_object_in_new_timeline.GetComponent<NetPoint>();
            obj.AddNetPoint(new_netpoint);
        }
        obj.MakeConnectionGraphByPoints();
        return obj;
    }
}
